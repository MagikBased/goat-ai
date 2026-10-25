"""Soul Exchange cannot pay Metamorphosis with an opposing Set monster."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.ocgcore_probe import UPSTREAM_METAMORPHOSIS_SHA256
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SOUL_EXCHANGE = 68005187
METAMORPHOSIS = 46411259
DARK_MIMIC_LV1 = 504700129
RESTRICT = 504700102


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("opponent_set", [False, True])
def test_soul_exchange_metamorphosis_opponent_position(tmp_path, opponent_set):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{SOUL_EXCHANGE}.lua", f"official/c{METAMORPHOSIS}.lua",
               f"goat/c{DARK_MIMIC_LV1}.lua", f"goat/c{RESTRICT}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card scripts not installed")
    attacker = tmp_path / "soul_meta.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        *([SOUL_EXCHANGE] * 3), *([METAMORPHOSIS] * 3), *VANILLA_DECK[6:])))
        + f"\n#extra\n{RESTRICT}\n!side\n")
    defender = tmp_path / "mimic.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        *([DARK_MIMIC_LV1] * 3), *VANILLA_DECK[3:])))
        + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {SOUL_EXCHANGE, METAMORPHOSIS} <= {card.code for card in obs.hand}
        assert DARK_MIMIC_LV1 in {card.code for card in
                                  env.engine.probe.observation(1).hand}
        summoned = soul_used = soul_targeted = checked = False
        meta_used = meta_cost = fusion_chosen = False
        for _ in range(100):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1 and not summoned:
                kind = "set_monster" if opponent_set else "normal_summon"
                action = next((a for a in actions if a.kind == kind
                               and a.parameters.get("code") == DARK_MIMIC_LV1), None)
                summoned |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and summoned:
                if not soul_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == SOUL_EXCHANGE), None)
                    soul_used |= action is not None
                elif (soul_targeted and not checked and not obs.chain
                      and any(a.kind == "end_phase" for a in actions)):
                    own_monsters = [c for c in obs.field if c.controller == 0
                                    and c.zone == "monster"]
                    assert not own_monsters
                    assert SOUL_EXCHANGE in {c.code for c in obs.graveyards[0]}
                    option = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == METAMORPHOSIS), None)
                    assert (option is not None) == (not opponent_set)
                    assert METAMORPHOSIS in {c.code for c in obs.hand}
                    assert obs.extra_deck_counts[0] == 1
                    checked = True
                    if not opponent_set:
                        action = option
                        meta_used = True
            if soul_used and not soul_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 4), None)
                assert action is not None
                if opponent_set:
                    assert "code" not in action.parameters
                soul_targeted = True
            if meta_used and not meta_cost and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("code") == DARK_MIMIC_LV1), None)
                meta_cost = action is not None
            if meta_cost and not fusion_chosen and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == RESTRICT),
                              None)
                fusion_chosen = action is not None
            if action is None:
                action = next((a for a in actions if a.kind in ("place", "pass",
                               "end_phase")), actions[0])
            obs = env.step(action)
            if checked and (opponent_set or fusion_chosen and RESTRICT in {
                    c.code for c in obs.field}):
                assert soul_used and soul_targeted
                assert scripts - {f"official/c{METAMORPHOSIS}.lua",
                                  f"goat/c{RESTRICT}.lua"} <= (
                                      env.engine.probe.loaded_script_sha256.keys())
                assert env.engine.probe.loaded_script_sha256[
                    f"official/c{METAMORPHOSIS}.lua"] != UPSTREAM_METAMORPHOSIS_SHA256
                if opponent_set:
                    assert not meta_used
                    assert any(c.controller == 1 and c.zone == "monster"
                               and c.position == "facedown" for c in obs.field)
                    assert DARK_MIMIC_LV1 not in {c.code for c in obs.graveyards[1]}
                else:
                    assert meta_used and meta_cost and fusion_chosen
                    assert DARK_MIMIC_LV1 in {c.code for c in obs.graveyards[1]}
                    assert METAMORPHOSIS in {c.code for c in obs.graveyards[0]}
                    assert obs.extra_deck_counts[0] == 0
                agents = (RandomAgent(15), RandomAgent(16))
                for _ in range(3000):
                    if env.is_terminal():
                        break
                    obs = env.step(agents[obs.acting_player].select_action(
                        obs, env.legal_actions()))
                assert env.is_terminal()
                path = tmp_path / f"soul_meta_{opponent_set}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                                             env.trajectory().decisions)
                return
    pytest.fail(f"Soul Exchange / Metamorphosis stalled: turn={obs.turn} "
                f"phase={obs.phase} setup={summoned}/{soul_used}/{soul_targeted} "
                f"checked={checked} meta={meta_used}/{meta_cost}/{fusion_chosen}")
