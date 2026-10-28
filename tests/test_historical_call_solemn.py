"""Solemn negates Call's activation before its targeted monster is Summoned."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

GRACEFUL = 79571449
CALL = 97077563
SOLEMN = 41420027
MYSTICAL_ELF = 15025844
SECOND_DISCARD = 79182538


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("negate", (False, True), ids=("allow", "solemn"))
def test_call_of_the_haunted_activation_answered_by_solemn(tmp_path, negate):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (GRACEFUL, CALL, SOLEMN):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    caller = tmp_path / "caller.ydk"
    caller.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL, CALL, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    defender = tmp_path / "defender.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        SOLEMN, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(caller), str(defender), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert {GRACEFUL, CALL} <= {card.code for card in observation.hand}
        assert SOLEMN in {card.code for card in env.engine.probe.observation(1).hand}
        done = set()
        for _ in range(100):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0:
                if "graceful" not in done:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    if action is not None:
                        done.add("graceful")
                elif "discard" not in done and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {card["code"] for card in
                                   a.parameters["cards"]} == {MYSTICAL_ELF, SECOND_DISCARD}),
                                  None)
                    if action is not None:
                        done.add("discard")
                elif "set_call" not in done:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == CALL), None)
                    if action is not None:
                        done.add("set_call")
            if observation.turn == 2 and observation.acting_player == 1 \
                    and "set_solemn" not in done:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SOLEMN), None)
                if action is not None:
                    done.add("set_solemn")
            if observation.turn == 3 and observation.acting_player == 0:
                if "call" not in done:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == CALL), None)
                    if action is not None:
                        done.add("call")
                elif "target" not in done and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == MYSTICAL_ELF), None)
                    if action is not None:
                        done.add("target")
            if "target" in done and "response" not in done \
                    and observation.acting_player == 1:
                assert [link.card_code for link in observation.chain] == [CALL]
                assert MYSTICAL_ELF in {c.code for c in observation.graveyards[0]}
                assert not any(c.code == MYSTICAL_ELF and c.zone == "monster"
                               for c in observation.field)
                action = next((a for a in actions if a.kind == ("chain" if negate else "pass")
                               and (not negate or a.parameters.get("code") == SOLEMN)), None)
                assert action is not None
                done.add("response")
            if "response" in done and observation.turn == 3 \
                    and observation.acting_player == 0 \
                    and any(a.kind == "end_phase" for a in actions):
                assert {"graceful", "discard", "set_call", "set_solemn", "call", "target"} <= done
                assert (MYSTICAL_ELF in {c.code for c in observation.graveyards[0]}) == negate
                assert (any(c.code == MYSTICAL_ELF and c.zone == "monster"
                            for c in observation.field)) is not negate
                assert (CALL in {c.code for c in observation.graveyards[0]}) == negate
                assert observation.life_points == ((8000, 4000) if negate else (8000, 8000))
                loaded = env.engine.probe.loaded_script_sha256
                assert {f"official/c{code}.lua" for code in (GRACEFUL, CALL, SOLEMN)
                        if code != SOLEMN or negate} <= loaded.keys()
                break
            if action is None:
                action = next((a for a in actions if a.kind in
                               ("select_card", "select_position", "place", "pass", "end_phase")),
                              actions[0])
            observation = env.step(action)
        else:
            pytest.fail(f"Call/Solemn response not reached: {done}, turn={observation.turn}")

        agents = (RandomAgent(101), RandomAgent(102))
        for _ in range(4000):
            if env.is_terminal():
                break
            observation = env.step(agents[observation.acting_player].select_action(
                observation, env.legal_actions()))
        assert env.is_terminal()
        path = tmp_path / f"call_solemn_{int(negate)}.json"
        write_trajectory(path, env.trajectory())
        replay = read_trajectory(path)
        assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(replay.decisions)
        assert audit_trajectory_visibility(replay)["decisions"] == len(replay.decisions)
