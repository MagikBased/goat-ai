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
MYSTICAL_SPACE_TYPHOON = 5318639
SOLEMN_JUDGMENT = 41420027


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
        assert opponent.known_opponent_hand_cards == (MYSTIC_SWORDSMAN,)
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
                assert opponent.known_opponent_hand_cards == ()
                assert f"goat/c{REINFORCEMENT}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail(f"empty Reinforcement search did not show Deck to opponent: "
                f"activated={activated}, turn={observation.turn}")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_mst_chained_to_reinforcement_does_not_stop_warrior_search(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{REINFORCEMENT}.lua",
                     f"official/c{MYSTICAL_SPACE_TYPHOON}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    mst_deck = tmp_path / "mst.ydk"
    mst_deck.write_text("#main\n" + "\n".join(map(str, (
        MYSTICAL_SPACE_TYPHOON, *VANILLA_DECK[1:])))
                        + "\n#extra\n!side\n")
    with GoatEnvironment(str(WARRIOR), str(mst_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert REINFORCEMENT in {c.code for c in obs.hand}
        assert MYSTICAL_SPACE_TYPHOON in {
            c.code for c in env.engine.probe.observation(1).hand}
        mst_set = reinforcement_used = mst_chained = targeted_spell = searched = False
        before_deck = None
        for _ in range(65):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1 and not mst_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == MYSTICAL_SPACE_TYPHOON), None)
                mst_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not reinforcement_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == REINFORCEMENT), None)
                if action is not None:
                    before_deck = obs.deck_counts[0]
                    reinforcement_used = True
            if reinforcement_used and obs.acting_player == 1 and not mst_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == MYSTICAL_SPACE_TYPHOON), action)
                mst_chained |= action is not None and action.kind == "chain"
            if mst_chained and not targeted_spell and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == REINFORCEMENT and a.parameters.get("controller") == 0),
                              action)
                targeted_spell |= action is not None and action.kind == "select_card"
            if targeted_spell and not searched and actions[0].kind == "select_card":
                options = {a.parameters.get("code") for a in actions}
                if MYSTIC_SWORDSMAN in options:
                    assert all(a.parameters.get("location") == 1
                               and "sequence" not in a.parameters for a in actions)
                    action = next(a for a in actions
                                  if a.parameters.get("code") == MYSTIC_SWORDSMAN)
                    searched = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if searched and obs.chain == () and any(
                    c.code == REINFORCEMENT for c in obs.graveyards[0]):
                assert mst_set and reinforcement_used and mst_chained and targeted_spell
                assert obs.deck_counts[0] == before_deck - 1
                assert MYSTIC_SWORDSMAN in {c.code for c in obs.hand}
                assert MYSTICAL_SPACE_TYPHOON in {c.code for c in obs.graveyards[1]}
                opponent = env.engine.probe.observation(1)
                assert opponent.known_opponent_hand_cards == (MYSTIC_SWORDSMAN,)
                assert [(event.recipient, [c.code for c in event.cards])
                        for event in opponent.private_reveals] == [
                            (1, [MYSTIC_SWORDSMAN])]
                assert {f"goat/c{REINFORCEMENT}.lua",
                        f"official/c{MYSTICAL_SPACE_TYPHOON}.lua"}.issubset(
                            env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("MST/Reinforcement chain did not search a Warrior")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_solemn_negates_reinforcement_before_warrior_search(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{REINFORCEMENT}.lua",
                     f"official/c{SOLEMN_JUDGMENT}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    solemn_deck = tmp_path / "solemn.ydk"
    solemn_deck.write_text("#main\n" + "\n".join(map(str, (
        SOLEMN_JUDGMENT, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(WARRIOR), str(solemn_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert REINFORCEMENT in {c.code for c in obs.hand}
        assert SOLEMN_JUDGMENT in {
            c.code for c in env.engine.probe.observation(1).hand}
        trap_set = reinforcement_used = solemn_chained = False
        before_deck = before_hand = None
        for _ in range(65):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1 and not trap_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SOLEMN_JUDGMENT), None)
                trap_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not reinforcement_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == REINFORCEMENT), None)
                if action is not None:
                    before_deck = obs.deck_counts[0]
                    before_hand = len(obs.hand)
                    reinforcement_used = True
            if reinforcement_used and obs.acting_player == 1 and not solemn_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SOLEMN_JUDGMENT), action)
                solemn_chained |= action is not None and action.kind == "chain"
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if solemn_chained and {REINFORCEMENT, SOLEMN_JUDGMENT}.issubset(
                    {c.code for pile in obs.graveyards for c in pile}):
                assert trap_set and reinforcement_used
                assert obs.chain == () and obs.life_points == (8000, 4000)
                assert obs.deck_counts[0] == before_deck
                assert len(env.engine.probe.observation(0).hand) == before_hand - 1
                opponent = env.engine.probe.observation(1)
                assert not opponent.private_reveals
                assert not opponent.known_opponent_hand_cards
                assert {f"goat/c{REINFORCEMENT}.lua",
                        f"official/c{SOLEMN_JUDGMENT}.lua"}.issubset(
                            env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Solemn/Reinforcement chain did not negate the search")
