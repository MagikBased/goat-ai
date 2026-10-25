"""Historical Thunder Dragon search cardinality and opponent verification."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

THUNDER_DRAGON = 504700054  # GOAT variant permits searching for zero copies.


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_thunder_dragon_may_choose_zero_with_copies_remaining(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/goat/c{THUNDER_DRAGON}.lua").is_file():
        pytest.skip("GOAT Thunder Dragon script not installed")
    deck = tmp_path / "thunder_zero.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        *([THUNDER_DRAGON] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=4,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        activated = selected_zero = False
        for _ in range(12):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not activated:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == THUNDER_DRAGON), None)
                activated |= action is not None
            if activated and any(a.kind == "select_cards" for a in actions):
                assert any(len(a.parameters.get("cards", ())) == 2
                           for a in actions if a.kind == "select_cards")
                action = next(a for a in actions if a.kind == "select_cards"
                              and not a.parameters.get("cards"))
                selected_zero = True
            if action is None:
                action = next((a for a in actions if a.kind == "pass"), actions[0])
            obs = env.step(action)
            if selected_zero and sum(c.code == THUNDER_DRAGON
                                     for c in obs.graveyards[0]) == 1:
                own = env.engine.probe.observation(0)
                other = env.engine.probe.observation(1)
                assert own.deck_counts[0] == 34
                assert len(own.hand) == 5
                assert not other.private_reveals
                return
    pytest.fail("Thunder Dragon zero-copy option did not resolve")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_thunder_dragon_two_then_zero_and_opponent_verification(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/goat/c{THUNDER_DRAGON}.lua").is_file():
        pytest.skip("GOAT Thunder Dragon script not installed")
    deck = tmp_path / "thunder_dragon.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        *([THUNDER_DRAGON] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=4,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        searches = 0
        selected_two = False
        for _ in range(30):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and searches < 2:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == THUNDER_DRAGON), None)
                if action is not None:
                    searches += 1
            if any(a.kind == "select_cards" for a in actions) \
                    and searches == 1 and not selected_two:
                action = next((a for a in actions if a.kind == "select_cards"
                               and len(a.parameters.get("cards", ())) == 2), None)
                assert action is not None
                selected_two = True
            if searches == 2 and not any(a.kind == "select_cards" for a in actions):
                # With no copies left in Deck, the core resolves the zero choice directly.
                assert all(a.kind != "select_card" or
                           a.parameters.get("location") != 1 for a in actions)
            if action is None:
                action = next((a for a in actions if a.kind in ("pass", "end_phase")), actions[0])
            obs = env.step(action)
            own = env.engine.probe.observation(0)
            other = env.engine.probe.observation(1)
            if searches == 2 and len(other.private_reveals) == 2:
                assert selected_two
                assert sum(c.code == THUNDER_DRAGON
                           for c in own.graveyards[0]) == 2
                assert len([c for c in own.hand if c.code == THUNDER_DRAGON]) == 1
                assert own.deck_counts[0] == 32
                assert other.opponent_hand_count == len(own.hand)
                assert [len(reveal.cards) for reveal in other.private_reveals] == [2, 32]
                assert all(card.code == THUNDER_DRAGON
                           for card in other.private_reveals[0].cards)
                assert all(card.code != THUNDER_DRAGON
                           for card in other.private_reveals[1].cards)
                assert not own.private_reveals
                assert f"goat/c{THUNDER_DRAGON}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Thunder Dragon two-copy and zero-copy searches did not resolve")
