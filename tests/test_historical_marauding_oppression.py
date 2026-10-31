"""Archived Royal Oppression FAQ: Marauding Captain's trigger can be negated.

Source: https://www.goatformat.com/rulings6.html (Royal Oppression Example 1).
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

MARAUDING = 2460565
OPPRESSION = 93016201
MYSTICAL_ELF = 15025844


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
@pytest.mark.parametrize("negate_trigger", [False, True])
def test_faceup_oppression_answers_marauding_captain_trigger(tmp_path,
                                                             negate_trigger):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (MARAUDING, OPPRESSION)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    captain_deck = tmp_path / "captain.ydk"
    opposition_deck = tmp_path / "oppression.ydk"
    captain_deck.write_text("#main\n" + "\n".join(map(str, (
        MARAUDING, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    opposition_deck.write_text("#main\n" + "\n".join(map(str, (
        OPPRESSION, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(captain_deck), str(opposition_deck), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {MARAUDING, MYSTICAL_ELF} <= {card.code for card in obs.hand}
        assert OPPRESSION in {card.code for card in
                              env.engine.probe.observation(1).hand}
        set_oppression = faceup_oppression = summoned = triggered = responded = False
        checked = False
        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"captain_oppression_{negate_trigger}.json"
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

            if not checked and obs.turn == 2 and obs.acting_player == 1 \
                    and not set_oppression:
                action = choose("set_spell_trap", OPPRESSION)
                set_oppression |= action is not None
            if not checked and obs.turn == 3 and obs.acting_player == 1 \
                    and set_oppression and not faceup_oppression:
                action = choose("chain", OPPRESSION)
                faceup_oppression |= action is not None
            if not checked and obs.turn == 3 and obs.acting_player == 0 \
                    and faceup_oppression and not summoned and not obs.chain:
                action = choose("normal_summon", MARAUDING)
                summoned |= action is not None
                if action is not None:
                    assert any(card.code == OPPRESSION and card.position == "faceup"
                               for card in obs.field)
            if summoned and not triggered:
                action = choose("yes", MARAUDING) or action
                triggered |= action is not None and action.kind == "yes"
            if triggered and not responded and obs.acting_player == 1 \
                    and [(link.index, link.card_code) for link in obs.chain] == [
                        (1, MARAUDING)]:
                response = choose("chain", OPPRESSION)
                assert response is not None
                if negate_trigger:
                    action = response
                responded = True
            if responded and not checked and not negate_trigger \
                    and actions[0].kind == "select_card":
                action = choose("select_card", MYSTICAL_ELF)
                assert action is not None
            if action is None:
                action = (agents[obs.acting_player].select_action(obs, actions)
                          if checked else next((candidate for candidate in actions
                                                if candidate.kind in (
                                                    "place", "pass", "end_phase")),
                                               actions[0]))
            obs = env.step(action)
            if responded and not checked and not obs.chain:
                field = {card.code for card in obs.field if card.controller == 0
                         and card.zone == "monster"}
                if negate_trigger and MARAUDING in {card.code for card in
                                                    obs.graveyards[0]}:
                    assert not field
                    assert obs.life_points[1] == 7200
                    checked = True
                elif not negate_trigger and {MARAUDING, MYSTICAL_ELF} <= field:
                    assert obs.life_points[1] == 8000
                    checked = True
    pytest.fail("Marauding/Oppression fixture did not reach a verified terminal duel")
