"""Torrential responding to Tsukuyomi's mandatory Summon trigger."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

TSUKUYOMI = 34853266
TORRENTIAL = 53582587


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("respond", [False, True])
def test_torrential_on_tsukuyomi_summon_destroys_trigger_source_and_target(
        tmp_path, respond):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (TSUKUYOMI, TORRENTIAL)}
    if any(not (root / "scripts" / relative).is_file() for relative in scripts):
        pytest.skip("required official scripts not installed")
    paths = []
    for name, code in (("tsukuyomi", TSUKUYOMI), ("torrential", TORRENTIAL)):
        path = tmp_path / f"{name}.ydk"
        cards = (*([code] * 3), *VANILLA_DECK[3:]) if code == TSUKUYOMI else (
            code, *VANILLA_DECK[1:])
        path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
        paths.append(path)

    with GoatEnvironment(*(str(path) for path in paths), seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert TSUKUYOMI in {c.code for c in obs.hand}
        assert TORRENTIAL in {c.code for c in env.engine.probe.observation(1).hand}
        normal_summoned = trap_set = tsuk_summoned = targeted = response_seen = False
        checked = False
        normal_code = None
        agents = (RandomAgent(15), RandomAgent(16))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"tsukuyomi_torrential_{respond}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                                             env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not normal_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") != TSUKUYOMI), None)
                if action is not None:
                    normal_code = action.parameters["code"]
                    normal_summoned = True
            if obs.turn == 2 and obs.acting_player == 1 and not trap_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == TORRENTIAL), None)
                trap_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and trap_set \
                    and not tsuk_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == TSUKUYOMI), None)
                tsuk_summoned |= action is not None
            if tsuk_summoned and not targeted and actions[0].kind == "select_card":
                assert [link.card_code for link in obs.chain] == [TSUKUYOMI]
                action = next((a for a in actions if a.parameters.get("code") == normal_code
                               and a.parameters.get("controller") == 0), None)
                assert action is not None
                targeted = True
            if targeted and obs.acting_player == 1 and not response_seen:
                torrential = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == TORRENTIAL), None)
                if torrential is not None:
                    assert [link.card_code for link in obs.chain] == [TSUKUYOMI]
                    action = torrential if respond else next(
                        (a for a in actions if a.kind == "pass"), None)
                    assert action is not None
                    response_seen = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if response_seen and not checked and obs.turn >= 4:
                owner = env.engine.probe.observation(0)
                assert normal_summoned and trap_set and tsuk_summoned and targeted
                assert obs.life_points == (8000, 8000)
                if respond:
                    assert {TSUKUYOMI, normal_code} <= {
                        c.code for c in owner.graveyards[0]}
                    assert TORRENTIAL in {c.code for c in owner.graveyards[1]}
                    assert not any(c.controller == 0 and c.zone == "monster"
                                   for c in owner.field)
                    assert TSUKUYOMI not in {c.code for c in owner.hand}
                else:
                    assert any(c.code == normal_code and c.position == "facedown"
                               for c in owner.field)
                    assert TSUKUYOMI in {c.code for c in owner.hand}
                    assert TORRENTIAL not in {c.code for c in owner.graveyards[1]}
                    assert not any(c.code == TSUKUYOMI for c in owner.graveyards[0])
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail("Tsukuyomi / Torrential duel did not complete")
