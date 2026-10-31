"""A face-up Royal Oppression may negate Call of the Haunted's revival.

Archived FAQ: https://www.goatformat.com/rulings6.html (Royal Oppression).
"""

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
OPPRESSION = 93016201
MYSTICAL_ELF = 15025844
MAD_DOG = 79182538


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
@pytest.mark.parametrize("negate_call", [False, True])
def test_faceup_oppression_can_negate_call_revival(tmp_path, negate_call):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (GRACEFUL, CALL, OPPRESSION)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    caller = tmp_path / "caller.ydk"
    responder = tmp_path / "oppression.ydk"
    caller.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL, CALL, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    responder.write_text("#main\n" + "\n".join(map(str, (
        OPPRESSION, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(caller), str(responder), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        graceful = discarded = call_set = oppression_set = oppression_up = False
        call_started = target_chosen = responded = checked = False
        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"call_oppression_{negate_call}.json"
                write_trajectory(path, env.trajectory())
                replay = read_trajectory(path)
                assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(
                    replay.decisions)
                audit_trajectory_visibility(replay)
                assert scripts <= set(env.engine.probe.loaded_script_sha256)
                return
            actions = env.legal_actions()
            action = None

            def choose(kind, code=None):
                return next((candidate for candidate in actions
                             if candidate.kind == kind and (code is None or
                                candidate.parameters.get("code") == code)), None)

            if not checked and obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = choose("activate", GRACEFUL)
                    graceful |= action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((candidate for candidate in actions
                                   if {card["code"] for card in
                                       candidate.parameters["cards"]} ==
                                   {MYSTICAL_ELF, MAD_DOG}), None)
                    discarded |= action is not None
                if discarded and not call_set and action is None:
                    action = choose("set_spell_trap", CALL)
                    call_set |= action is not None
            if not checked and obs.turn == 2 and obs.acting_player == 1 \
                    and not oppression_set:
                action = choose("set_spell_trap", OPPRESSION)
                oppression_set |= action is not None
            if not checked and obs.turn == 3 and obs.acting_player == 1 \
                    and oppression_set and not oppression_up:
                action = choose("chain", OPPRESSION)
                oppression_up |= action is not None
            if not checked and obs.turn == 3 and obs.acting_player == 0 \
                    and oppression_up and not call_started and not obs.chain:
                action = choose("activate", CALL)
                call_started |= action is not None
                if action is not None:
                    assert any(card.code == OPPRESSION and card.position == "faceup"
                               for card in obs.field)
            if call_started and not target_chosen and actions[0].kind == "select_card":
                action = choose("select_card", MYSTICAL_ELF)
                target_chosen |= action is not None
            if target_chosen and not responded and obs.acting_player == 1 \
                    and [(link.index, link.card_code) for link in obs.chain] == [(1, CALL)]:
                response = choose("chain", OPPRESSION)
                assert response is not None
                if negate_call:
                    action = response
                responded = True
            if action is None:
                action = (agents[obs.acting_player].select_action(obs, actions)
                          if checked else next((candidate for candidate in actions
                                                if candidate.kind in (
                                                    "place", "pass", "end_phase")),
                                               actions[0]))
            obs = env.step(action)
            if responded and not checked and not obs.chain:
                revived = any(card.code == MYSTICAL_ELF and card.zone == "monster"
                              for card in obs.field)
                if negate_call:
                    assert not revived
                    assert MYSTICAL_ELF in {card.code for card in obs.graveyards[0]}
                    assert obs.life_points[1] == 7200
                else:
                    assert revived
                    assert obs.life_points[1] == 8000
                checked = True
    pytest.fail("Call/Oppression fixture did not reach a verified terminal duel")
