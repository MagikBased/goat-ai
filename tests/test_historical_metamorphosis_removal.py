"""Destroying activated Metamorphosis does not cancel its Fusion Summon."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SCAPEGOAT = 504700123
METAMORPHOSIS = 46411259
MST = 5318639
RAIGEKI_BREAK = 4178474
RESTRICT = 504700102
SHEEP = {73915052, 73915053, 73915054, 73915055}


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("removal", (MST, RAIGEKI_BREAK), ids=("mst", "raigeki_break"))
@pytest.mark.parametrize("chain_removal", (False, True), ids=("pass", "chain"))
def test_destroying_metamorphosis_does_not_stop_fusion(tmp_path, removal, chain_removal):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{SCAPEGOAT}.lua", f"official/c{METAMORPHOSIS}.lua",
               f"official/c{removal}.lua", f"goat/c{RESTRICT}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card scripts not installed")
    attacker = tmp_path / "goat_meta.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        *((SCAPEGOAT, METAMORPHOSIS) * 3), *VANILLA_DECK[6:])))
        + f"\n#extra\n{RESTRICT}\n!side\n")
    defender = tmp_path / "removal.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        removal, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {SCAPEGOAT, METAMORPHOSIS} <= {c.code for c in obs.hand}
        assert removal in {c.code for c in env.engine.probe.observation(1).hand}
        goat = removal_set = meta = token_paid = responded = removal_targeted = False
        discarded_code = None
        fusion_chosen = False
        for _ in range(90):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not goat:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                goat |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not removal_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == removal), None)
                removal_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not meta:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == METAMORPHOSIS), None)
                meta |= action is not None
            if meta and not token_paid and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") in SHEEP),
                              None)
                token_paid |= action is not None
            if token_paid and obs.acting_player == 1 and not responded:
                removal_action = next((a for a in actions if a.kind == "chain"
                                       and a.parameters.get("code") == removal), None)
                if removal_action is not None:
                    assert tuple(link.card_code for link in obs.chain) == (METAMORPHOSIS,)
                    assert sum(c.code in SHEEP for c in obs.field) == 3
                    action = (removal_action if chain_removal else next(
                        a for a in actions if a.kind == "pass"))
                    responded = True
            if (responded and chain_removal and removal == RAIGEKI_BREAK
                    and discarded_code is None and actions[0].kind == "select_card"):
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("location") == 2
                               and a.parameters.get("controller") == 1), None)
                if action is not None:
                    discarded_code = action.parameters["code"]
            if responded and chain_removal and not removal_targeted \
                    and actions[0].kind == "select_card":
                target = next((a for a in actions if a.parameters.get("code")
                               == METAMORPHOSIS and a.parameters.get("controller") == 0),
                              None)
                if target is not None:
                    action = target
                    removal_targeted = True
            if responded and not fusion_chosen and actions[0].kind == "select_card":
                option = next((a for a in actions if a.parameters.get("code") == RESTRICT),
                              None)
                if option is not None:
                    action = option
                    fusion_chosen = True
            if responded and fusion_chosen and obs.turn == 3 \
                    and obs.acting_player == 0 and obs.phase == "main1" \
                    and any(a.kind == "end_phase" for a in actions):
                assert removal_targeted == chain_removal
                assert sum(c.code in SHEEP for c in obs.field) == 3
                assert any(c.code == RESTRICT and c.controller == 0
                           and c.zone == "monster" for c in obs.field)
                assert METAMORPHOSIS in {c.code for c in obs.graveyards[0]}
                assert (removal in {c.code for c in obs.graveyards[1]}) == chain_removal
                if removal == RAIGEKI_BREAK:
                    assert (discarded_code is not None) == chain_removal
                    if chain_removal:
                        assert discarded_code in {c.code for c in obs.graveyards[1]}
                assert obs.extra_deck_counts[0] == 0
                assert obs.life_points == (8000, 8000)
                assert not any(c.code in SHEEP for pile in obs.graveyards for c in pile)
                loaded = env.engine.probe.loaded_script_sha256
                assert scripts - {f"official/c{removal}.lua"} <= loaded.keys()
                if chain_removal:
                    assert f"official/c{removal}.lua" in loaded
                agents = (RandomAgent(52), RandomAgent(53))
                for _ in range(3000):
                    if env.is_terminal():
                        break
                    obs = env.step(agents[obs.acting_player].select_action(
                        obs, env.legal_actions()))
                assert env.is_terminal()
                path = tmp_path / f"metamorphosis_{removal}_{chain_removal}.json"
                write_trajectory(path, env.trajectory())
                trajectory = read_trajectory(path)
                assert audit_trajectory_visibility(trajectory)["decisions"] == len(
                    trajectory.decisions)
                assert verify_trajectory(trajectory,
                                         ExperimentalOcgcoreEngine(root)) == len(
                                             trajectory.decisions)
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
    pytest.fail(f"Metamorphosis / removal did not resolve: turn={obs.turn} "
                f"phase={obs.phase} setup={goat}/{removal_set}/{meta}/{token_paid} "
                f"response={responded}/{removal_targeted}/{fusion_chosen}")
