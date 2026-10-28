"""Fruits of Kozaky's Studies reveals and reorders three Deck-top cards."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_decision_visibility
from goat_ai.replay import DecisionRecord

FRUITS = 49998907


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_fruits_sort_choice_changes_own_deck_top_without_public_reveal(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{FRUITS}.lua").is_file():
        pytest.skip("Fruits of Kozaky's Studies script not installed")
    deck = tmp_path / "fruits.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (FRUITS, *VANILLA_DECK[1:])))
                    + "\n#extra\n!side\n")
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        for _ in range(20):
            actions = env.legal_actions()
            if actions[0].kind == "sort_cards":
                assert observation.acting_player == 0
                assert len(actions) == 6
                original = [card["code"] for card in actions[0].parameters["cards"]]
                assert len(set(original)) == 3
                assert {tuple(card["code"] for card in action.parameters["cards"])
                        for action in actions} == {
                            tuple(original[index] for index in order)
                            for order in ((0, 1, 2), (0, 2, 1), (1, 0, 2),
                                          (1, 2, 0), (2, 0, 1), (2, 1, 0))}
                opposing_view = env.engine.probe.observation(1)
                assert not opposing_view.public_reveals
                assert not opposing_view.private_reveals
                reverse = next(action for action in actions
                               if [card["code"] for card in action.parameters["cards"]]
                               == list(reversed(original)))
                assert audit_decision_visibility(DecisionRecord(
                    observation, actions, reverse)) == {}
                observation = env.step(reverse)
                # Native Deck query is used only by this regression, never by an agent.
                deck_after = [card.code for card in env.engine.probe._query_location(0, 1)]
                assert deck_after[-3:] == original
                assert env.legal_actions()
                return
            action = next((choice for choice in actions
                           if choice.kind in ("set_spell_trap", "chain")
                           and choice.parameters.get("code") == FRUITS), None)
            if action is None:
                action = next((choice for choice in actions
                               if choice.kind in ("place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
    pytest.fail("Fruits did not reach a Deck-order choice")
