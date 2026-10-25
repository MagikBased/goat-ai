"""Typhoon destroys an activated Scapegoat without negating its Tokens."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SCAPEGOAT = 504700123
MST = 5318639
SHEEP_CODES = {73915052, 73915053, 73915054, 73915055}


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_mst", [False, True])
def test_typhoon_chained_to_scapegoat_does_not_stop_tokens(tmp_path, chain_mst):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{SCAPEGOAT}.lua", f"official/c{MST}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    attacker = tmp_path / "goat.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        SCAPEGOAT, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    defender = tmp_path / "typhoon.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        MST, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert SCAPEGOAT in {c.code for c in obs.hand}
        assert MST in {c.code for c in env.engine.probe.observation(1).hand}
        mst_set = goat_used = responded = mst_targeted = checked = False
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"scapegoat_mst_{chain_mst}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1 and not mst_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == MST), None)
                mst_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and mst_set and not goat_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SCAPEGOAT), action)
                goat_used |= action is not None and action.kind == "activate" \
                    and action.parameters.get("code") == SCAPEGOAT
            if goat_used and obs.acting_player == 1 and not responded:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == MST), None)
                if option is not None:
                    assert [link.card_code for link in obs.chain] == [SCAPEGOAT]
                    action = option if chain_mst else next(a for a in actions
                                                            if a.kind == "pass")
                    responded = True
            if responded and chain_mst and not mst_targeted \
                    and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == SCAPEGOAT
                               and a.parameters.get("controller") == 0), None)
                mst_targeted |= action is not None
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if responded and not checked and not obs.chain \
                    and SCAPEGOAT in {c.code for c in obs.graveyards[0]}:
                assert mst_targeted == chain_mst
                assert (MST in {c.code for c in obs.graveyards[1]}) == chain_mst
                tokens = [c for c in obs.field if c.controller == 0
                          and c.code in SHEEP_CODES]
                assert {c.code for c in tokens} == SHEEP_CODES
                assert all(c.position == "faceup" and c.orientation == "defense"
                           for c in tokens)
                assert obs.life_points == (8000, 8000)
                loaded = env.engine.probe.loaded_script_sha256
                assert f"goat/c{SCAPEGOAT}.lua" in loaded
                if chain_mst:
                    assert f"official/c{MST}.lua" in loaded
                checked = True
    pytest.fail("Scapegoat / Typhoon response did not complete")
