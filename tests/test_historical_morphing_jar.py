"""Morphing Jar's simultaneous hand reset preserves private draws."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

MORPHING_JAR = 33508719


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_morphing_jar_discards_both_hands_and_draws_five_privately(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{MORPHING_JAR}.lua").is_file():
        pytest.skip("Morphing Jar script not installed")
    deck = tmp_path / "morphing_jar.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        MORPHING_JAR, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        set_jar = flipped = False
        old_hands = old_deck_counts = None
        for _ in range(33):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 \
                    and not set_jar:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == MORPHING_JAR), None)
                set_jar = action is not None
            if observation.turn == 3 and observation.acting_player == 0 \
                    and not flipped:
                action = next((a for a in actions if a.kind == "flip_summon"
                               and a.parameters.get("code") == MORPHING_JAR), None)
                if action is not None:
                    other = env.engine.probe.observation(1)
                    assert len(observation.hand) == 6
                    assert len(other.hand) == 6
                    assert observation.opponent_hand_count == 6
                    assert other.opponent_hand_count == 6
                    assert observation.known_opponent_cards == ()
                    assert other.known_opponent_cards == ()
                    old_hands = (Counter(c.code for c in observation.hand),
                                 Counter(c.code for c in other.hand))
                    old_deck_counts = observation.deck_counts
                    flipped = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if flipped and len(observation.graveyards[0]) == 6 \
                    and len(observation.graveyards[1]) == 6:
                assert old_hands is not None and old_deck_counts is not None
                own = env.engine.probe.observation(0)
                other = env.engine.probe.observation(1)
                for player in (0, 1):
                    expected = old_hands[player]
                    assert Counter(c.code for c in own.graveyards[player]) == expected
                    assert Counter(c.code for c in other.graveyards[player]) == expected
                assert own.deck_counts == other.deck_counts == (
                    old_deck_counts[0] - 5, old_deck_counts[1] - 5)
                assert len(own.hand) == len(other.hand) == 5
                assert own.opponent_hand_count == other.opponent_hand_count == 5
                assert all(c.controller == 0 for c in own.hand)
                assert all(c.controller == 1 for c in other.hand)
                assert own.private_reveals == other.private_reveals == ()
                assert own.known_opponent_cards == other.known_opponent_cards == ()
                assert any(c.code == MORPHING_JAR and c.position == "faceup"
                           for c in own.field)
                assert "official/c33508719.lua" in env.engine.probe.loaded_script_sha256
                return
    pytest.fail("Morphing Jar did not reset both hands")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_morphing_jar_opponent_new_hand_cannot_change_visible_decision(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{MORPHING_JAR}.lua").is_file():
        pytest.skip("Morphing Jar script not installed")
    own_deck = tmp_path / "morphing_jar.ydk"
    own_deck.write_text("#main\n" + "\n".join(map(str, (
        MORPHING_JAR, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    alternate_cards = list(VANILLA_DECK)
    assert alternate_cards[6] == 69140098
    alternate_cards[6] = 97923414
    other_deck = tmp_path / "alternate.ydk"
    other_deck.write_text("#main\n" + "\n".join(map(str, alternate_cards))
                          + "\n#extra\n!side\n")

    def run(opponent_deck):
        with GoatEnvironment(str(own_deck), str(opponent_deck), seed=3,
                             engine=ExperimentalOcgcoreEngine(root)) as env:
            observation = env.reset()
            set_jar = flipped = False
            before_self = before_other = None
            for _ in range(30):
                actions = env.legal_actions()
                action = None
                if observation.turn == 1 and observation.acting_player == 0 \
                        and not set_jar:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == MORPHING_JAR), None)
                    set_jar = action is not None
                if observation.turn == 3 and observation.acting_player == 0 \
                        and not flipped:
                    action = next((a for a in actions if a.kind == "flip_summon"
                                   and a.parameters.get("code") == MORPHING_JAR), None)
                    if action is not None:
                        before_self = observation
                        before_other = env.engine.probe.observation(1)
                        flipped = True
                if action is None:
                    action = next((a for a in actions if a.kind in (
                        "select_card", "place", "pass", "end_phase")), actions[0])
                observation = env.step(action)
                if flipped and len(observation.graveyards[1]) == 6:
                    assert before_self is not None and before_other is not None
                    return (before_self, before_other,
                            env.engine.probe.observation(0),
                            env.engine.probe.observation(1), env.legal_actions())
        pytest.fail("Morphing Jar did not reach the comparison decision")

    first = run("examples/decks/vanilla_probe.ydk")
    second = run(other_deck)
    assert first[0] == second[0]
    assert Counter(c.code for c in first[1].hand) == Counter(
        c.code for c in second[1].hand)
    assert first[2] == second[2]
    assert first[4] == second[4]
    assert Counter(c.code for c in first[3].hand) != Counter(
        c.code for c in second[3].hand)
    assert first[3].opponent_hand_count == second[3].opponent_hand_count == 5
