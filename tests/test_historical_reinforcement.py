"""GOAT Reinforcement of the Army search and addressed card reveal."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.engine.decks import read_ydk
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

ROOT = Path(__file__).resolve().parent.parent
WARRIOR = ROOT / "examples/decks/warrior_montague_clash.ydk"
REINFORCEMENT = 504700055
MYSTIC_SWORDSMAN = 504700077
POT_OF_GREED = 55144522


def _reach_search(env):
    observation = env.reset()
    for _ in range(20):
        actions = env.legal_actions()
        if actions[0].kind == "select_card":
            return observation, actions
        action = next((a for a in actions if a.kind == "activate"
                       and a.parameters.get("code") == REINFORCEMENT), None)
        if action is None:
            action = next((a for a in actions if a.kind == "pass"), actions[0])
        observation = env.step(action)
    pytest.fail("Reinforcement did not reach its Deck search")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_reinforcement_search_hides_deck_order_and_reveals_chosen_warrior(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/goat/c{REINFORCEMENT}.lua").is_file():
        pytest.skip("GOAT Reinforcement script not installed")
    cards = list(read_ydk(WARRIOR).main)
    swapped = cards.copy()
    swapped[0], swapped[1] = swapped[1], swapped[0]
    changed = tmp_path / "same_cards_different_order.ydk"
    changed.write_text("#main\n" + "\n".join(map(str, swapped)) + "\n#extra\n!side\n")

    with GoatEnvironment(str(WARRIOR), "examples/decks/vanilla_probe.ydk", seed=2,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation, actions = _reach_search(env)
        assert observation.acting_player == observation.viewer == 0
        assert Counter(a.parameters["code"] for a in actions) == {
            39507162: 3, 4041838: 1, MYSTIC_SWORDSMAN: 2,
            504700152: 1, 74131780: 1, 7572887: 1,
        }
        assert all(a.parameters["location"] == 1 and "sequence" not in a.parameters
                   for a in actions)
        assert not env.engine.probe.observation(1).private_reveals
        raw_sequences = tuple(c.sequence for c in env.engine._choices)

        with GoatEnvironment(str(changed), "examples/decks/vanilla_probe.ydk", seed=2,
                             engine=ExperimentalOcgcoreEngine(root)) as other:
            changed_observation, changed_actions = _reach_search(other)
            assert changed_observation == observation
            assert changed_actions == actions
            assert tuple(c.sequence for c in other.engine._choices) != raw_sequences

        before_hand = len(observation.hand)
        before_deck = observation.deck_counts[0]
        action = next(a for a in actions if a.parameters["code"] == MYSTIC_SWORDSMAN)
        observation = env.step(action)
        assert len(observation.hand) == before_hand + 1
        assert observation.deck_counts[0] == before_deck - 1
        assert any(c.code == MYSTIC_SWORDSMAN for c in observation.hand)
        opponent = env.engine.probe.observation(1)
        assert len(opponent.private_reveals) == 1
        reveal = opponent.private_reveals[0]
        assert reveal.recipient == 1
        assert [(c.code, c.controller, c.location) for c in reveal.cards] == [
            (MYSTIC_SWORDSMAN, 0, 2)]
        assert not observation.private_reveals
        assert f"goat/c{REINFORCEMENT}.lua" in env.engine.probe.loaded_script_sha256


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_reinforcement_empty_search_shows_only_opponent_the_deck(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/goat/c{REINFORCEMENT}.lua").is_file():
        pytest.skip("GOAT Reinforcement script not installed")
    non_warriors = tuple(code for code in VANILLA_DECK if code != 11321183)
    deck = tmp_path / "no_warriors.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        REINFORCEMENT, REINFORCEMENT, POT_OF_GREED, *non_warriors)))
        + "\n#extra\n!side\n")
    assert len(read_ydk(deck).main) == 40
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        activated = False
        before_hand = before_deck = None
        for _ in range(20):
            actions = env.legal_actions()
            action = None
            if not activated:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == REINFORCEMENT), None)
                activated |= action is not None
                if activated:
                    before_hand = len(observation.hand)
                    before_deck = observation.deck_counts[0]
            if action is None:
                action = next((a for a in actions if a.kind == "pass"), actions[0])
            observation = env.step(action)
            opponent = env.engine.probe.observation(1)
            if opponent.private_reveals:
                assert activated
                assert len(env.engine.probe.observation(0).hand) == before_hand - 1
                assert observation.deck_counts[0] == before_deck
                assert not observation.private_reveals
                assert len(opponent.private_reveals) == 1
                reveal = opponent.private_reveals[0]
                assert reveal.recipient == 1
                assert len(reveal.cards) == observation.deck_counts[0]
                assert Counter(c.code for c in reveal.cards) == Counter(
                    c.code for c in env.engine.probe._query_location(0, 1))
                assert all(c.controller == 0 and c.location == 1 for c in reveal.cards)
                assert f"goat/c{REINFORCEMENT}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail(f"empty Reinforcement search did not show Deck to opponent: "
                f"activated={activated}, turn={observation.turn}")
