"""Pot of Greed draws must not disclose the identities drawn to the opponent."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

POT_OF_GREED = 55144522


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
def test_pot_private_draw_swap_preserves_opponent_decisions(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{POT_OF_GREED}.lua").is_file():
        pytest.skip("Pot of Greed script not installed")
    cards = [POT_OF_GREED, *VANILLA_DECK[1:]]
    swapped = cards.copy()
    swapped[2], swapped[39] = swapped[39], swapped[2]
    assert sorted(cards) == sorted(swapped)

    def run(label, main):
        deck = tmp_path / f"{label}.ydk"
        deck.write_text("#main\n" + "\n".join(map(str, main))
                        + "\n#extra\n!side\n")
        with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk",
                             seed=52, engine=ExperimentalOcgcoreEngine(root)) as env:
            observation = env.reset()
            opening = observation
            assert POT_OF_GREED in {card.code for card in opening.hand}
            activated = False
            drawn = None
            opponent_after_draw = None
            for _ in range(40):
                actions = env.legal_actions()
                if (drawn is not None and observation.turn == 2
                        and observation.acting_player == 1
                        and observation.phase == "main1"):
                    assert f"official/c{POT_OF_GREED}.lua" in (
                        env.engine.probe.loaded_script_sha256)
                    return (opening, drawn, opponent_after_draw,
                            observation, actions)
                action = None
                if not activated:
                    action = next((candidate for candidate in actions
                                   if candidate.kind == "activate" and
                                   candidate.parameters.get("code") == POT_OF_GREED), None)
                    activated = action is not None
                if action is None:
                    action = next((candidate for candidate in actions
                                   if candidate.kind in ("place", "pass", "end_phase")),
                                  actions[0])
                observation = env.step(action)
                if activated and drawn is None and POT_OF_GREED in {
                        card.code for card in observation.graveyards[0]}:
                    assert len(observation.hand) == len(opening.hand) + 1
                    assert observation.deck_counts[0] == opening.deck_counts[0] - 2
                    drawn = tuple(sorted(card.code for card in observation.hand))
                    opponent_after_draw = env.engine.probe.observation(1)
                    assert opponent_after_draw.opponent_hand_count == len(drawn)
                    assert not opponent_after_draw.private_reveals
            pytest.fail("opponent's next Main Phase decision not reached")

    original = run("original", cards)
    reordered = run("reordered", swapped)
    assert original[0] == reordered[0]
    assert original[1] != reordered[1]  # The hidden draw actually changed.
    assert original[2:] == reordered[2:]  # Full view and legal actions agree.
