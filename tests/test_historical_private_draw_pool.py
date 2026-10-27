"""An opponent's private draw cannot change the other player's decision inputs."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.decks import read_ydk
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.competitive_corpus import TOURNAMENT_MAIN_DECKS

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
def test_tournament_card_private_draw_preserves_other_players_views(tmp_path):
    """Vary one turn-two draw while both players take the same public actions."""
    native_root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    own_deck = ROOT / "examples/decks/vanilla_probe.ydk"
    source_cards = set().union(*(
        set(read_ydk(ROOT / "examples/decks" / name).main)
        for name in TOURNAMENT_MAIN_DECKS))
    candidates = sorted(source_cards - set(VANILLA_DECK))
    assert len(candidates) >= 50
    baseline = None
    baseline_opening_hand = None
    baseline_drawn_hand = None

    for code in candidates:
        opponent_deck = tmp_path / f"private_draw_{code}.ydk"
        cards = list(VANILLA_DECK)
        cards[19] = code  # Seed 52 draws this slot on player 1's second turn.
        opponent_deck.write_text(
            "#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
        with GoatEnvironment(str(own_deck), str(opponent_deck), seed=52,
                             engine=ExperimentalOcgcoreEngine(native_root)) as env:
            observation = env.reset()
            opening_hand = tuple(sorted(
                card.code for card in env.engine.probe.observation(1).hand))
            assert code not in opening_hand
            if baseline_opening_hand is None:
                baseline_opening_hand = opening_hand
            else:
                assert opening_hand == baseline_opening_hand
            private_draw = None
            own_decisions = []
            for _ in range(60):
                actions = env.legal_actions()
                if observation.acting_player == 0:
                    own_decisions.append((observation, actions))
                if (observation.turn == 2 and observation.acting_player == 1
                        and observation.phase == "main1"):
                    private_draw = tuple(sorted(
                        card.code for card in env.engine.probe.observation(1).hand))
                    assert code in private_draw
                if (observation.turn == 3 and observation.acting_player == 0
                        and observation.phase == "main1"):
                    break
                action = next((candidate for candidate in actions
                               if candidate.kind in ("pass", "end_phase", "place", "no")),
                              actions[0])
                observation = env.step(action)
            else:
                pytest.fail(f"player 0 turn-three Main Phase not reached for {code}")
            assert private_draw is not None
            assert len(own_decisions) > 1
            if baseline is None:
                baseline = own_decisions
                baseline_drawn_hand = private_draw
            else:
                assert private_draw != baseline_drawn_hand
                assert own_decisions == baseline, code
