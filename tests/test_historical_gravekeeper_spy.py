"""GOAT Gravekeeper's Spy recruits while Deck order stays private."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory
from goat_ai.replay.fingerprint import sha256_file

SPY = 504700044  # GOAT variant
GUARD = 37101832
NECROVALLEY = 511002998  # pre-errata variant
BASE_DECK = (*([SPY] * 3), *([GUARD] * 3), *VANILLA_DECK[6:])


def _write_deck(path, cards):
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


def _reach_spy_search(env):
    observation = env.reset()
    set_spy = flipped = False
    for _ in range(35):
        actions = env.legal_actions()
        action = None
        if observation.turn == 1 and observation.acting_player == 0 and not set_spy:
            action = next((a for a in actions if a.kind == "set_monster"
                           and a.parameters.get("code") == SPY), None)
            set_spy |= action is not None
        if observation.turn == 3 and observation.acting_player == 0 and not flipped:
            action = next((a for a in actions if a.kind == "flip_summon"
                           and a.parameters.get("code") == SPY), None)
            flipped |= action is not None
        if flipped and actions[0].kind == "select_card":
            return observation, actions
        if action is None:
            action = next((a for a in actions if a.kind in (
                "place", "select_position", "pass", "end_phase")), actions[0])
        observation = env.step(action)
    pytest.fail("Spy did not reach its Deck search")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_spy_deck_search_hides_native_order_and_recruits_guard(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/goat/c{SPY}.lua").is_file():
        pytest.skip("GOAT Spy script not installed")
    if not (root / f"scripts/official/c{GUARD}.lua").is_file():
        pytest.skip("Guard script not installed")
    base = _write_deck(tmp_path / "base.ydk", BASE_DECK)
    swapped = list(BASE_DECK)
    swapped[1], swapped[6] = swapped[6], swapped[1]
    changed = _write_deck(tmp_path / "swapped.ydk", swapped)
    with GoatEnvironment(base, "examples/decks/vanilla_probe.ydk", seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation, actions = _reach_spy_search(env)
        assert observation.acting_player == observation.viewer == 0
        assert observation.deck_counts[0] == 33
        assert Counter(a.parameters["code"] for a in actions) == {GUARD: 2, SPY: 1}
        assert [a.parameters["code"] for a in actions] == [GUARD, GUARD, SPY]
        assert all(a.parameters["location"] == 1 and "sequence" not in a.parameters
                   for a in actions)
        opponent = env.engine.probe.observation(1)
        assert any(c.code == SPY and c.position == "faceup" for c in opponent.field)
        assert not any(c.code == GUARD for c in opponent.field)
        assert GUARD not in opponent.known_opponent_cards
        assert not opponent.private_reveals
        raw_sequences = tuple(c.sequence for c in env.engine._choices)

        with GoatEnvironment(changed, "examples/decks/vanilla_probe.ydk", seed=3,
                             engine=ExperimentalOcgcoreEngine(root)) as other:
            changed_observation, changed_actions = _reach_spy_search(other)
            assert changed_observation == observation
            assert changed_actions == actions
            assert tuple(c.sequence for c in other.engine._choices) != raw_sequences

        action = actions[0]
        assert action.parameters["code"] == GUARD
        before = observation.deck_counts[0]
        observation = env.step(action)
        for _ in range(12):
            if observation.deck_counts[0] == before - 1 and any(
                    c.code == GUARD and c.controller == 0 for c in observation.field):
                assert sum(c.code == SPY for c in observation.field) == 1
                assert not observation.graveyards[0]
                assert any(c.code == GUARD and c.position == "faceup"
                           for c in env.engine.probe.observation(1).field)
                assert f"goat/c{SPY}.lua" in env.engine.probe.loaded_script_sha256
                agents = (RandomAgent(3), RandomAgent(4))
                for _ in range(5000):
                    action = agents[observation.acting_player].select_action(
                        observation, env.legal_actions())
                    observation = env.step(action)
                    if env.is_terminal():
                        trajectory = env.trajectory()
                        assert trajectory.schema_version == 22
                        path = tmp_path / "spy.json"
                        write_trajectory(path, trajectory)
                        assert verify_trajectory(read_trajectory(path),
                                                 ExperimentalOcgcoreEngine(root)) == len(
                                                     trajectory.decisions)
                        return
                pytest.fail("Spy duel did not reach terminal state within 5000 decisions")
            options = env.legal_actions()
            next_action = next((a for a in options if a.kind in (
                "place", "select_position", "pass")), options[0])
            observation = env.step(next_action)
    pytest.fail("Spy's selected Guard did not reach the field")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_spy_can_recruit_another_spy_with_necrovalley_active(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not all((root / path).is_file() for path in (
            f"scripts/goat/c{SPY}.lua",
            f"scripts/pre-errata/c{NECROVALLEY}.lua")):
        pytest.skip("GOAT Spy or pre-errata Necrovalley script not installed")
    cards = (*([SPY] * 3), *([GUARD] * 3), *([NECROVALLEY] * 3),
             *VANILLA_DECK[9:])
    deck = _write_deck(tmp_path / "spy_necrovalley.ydk", cards)
    with GoatEnvironment(deck, "examples/decks/vanilla_probe.ydk", seed=4,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        activated = set_spy = flipped = selected = False
        for _ in range(45):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not activated:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == NECROVALLEY), None)
                activated |= action is not None
            if activated and observation.turn == 1 and observation.acting_player == 0 \
                    and not set_spy and action is None:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == SPY), None)
                set_spy |= action is not None
            if observation.turn == 3 and observation.acting_player == 0 and not flipped:
                action = next((a for a in actions if a.kind == "flip_summon"
                               and a.parameters.get("code") == SPY), None)
                flipped |= action is not None
            if flipped and not selected and actions[0].kind == "select_card":
                assert any(c.code == NECROVALLEY and c.zone == "spell_trap"
                           for c in observation.field)
                assert any(c.code == SPY and c.attack == 1700 and c.defense == 2500
                           for c in observation.field)
                assert Counter(a.parameters["code"] for a in actions) == {
                    GUARD: 2, SPY: 2}
                assert all(a.parameters.get("location") == 1
                           and "sequence" not in a.parameters for a in actions)
                action = next(a for a in actions if a.parameters["code"] == SPY)
                selected = True
            if selected and sum(c.code == SPY for c in observation.field) == 2:
                assert sum(c.code == SPY and c.attack == 1700 and c.defense == 2500
                           and c.position == "faceup" for c in observation.field) == 2
                assert observation.deck_counts[0] == 32
                assert f"goat/c{SPY}.lua" in env.engine.probe.loaded_script_sha256
                assert f"pre-errata/c{NECROVALLEY}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            observation = env.step(action)
    pytest.fail("Spy did not recruit another Spy under pre-errata Necrovalley")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_spy_empty_search_verifies_deck_only_to_opponent(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/goat/c{SPY}.lua").is_file():
        pytest.skip("GOAT Spy script not installed")
    deck = _write_deck(tmp_path / "only_spy.ydk", (SPY, *VANILLA_DECK[1:]))
    with GoatEnvironment(deck, "examples/decks/vanilla_probe.ydk", seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        set_spy = flipped = False
        assert not env.engine.probe.observation(1).private_reveals
        for _ in range(35):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not set_spy:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == SPY), None)
                set_spy |= action is not None
            if observation.turn == 3 and observation.acting_player == 0 and not flipped:
                action = next((a for a in actions if a.kind == "flip_summon"
                               and a.parameters.get("code") == SPY), None)
                flipped |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            owner_view = env.engine.probe.observation(0)
            opponent_view = env.engine.probe.observation(1)
            if opponent_view.private_reveals:
                assert flipped
                assert not owner_view.private_reveals
                assert len(opponent_view.private_reveals) == 1
                reveal = opponent_view.private_reveals[0]
                assert reveal.recipient == 1 and reveal.turn == 3
                assert len(reveal.cards) == owner_view.deck_counts[0] == 33
                assert all(c.controller == 0 and c.location == 1 for c in reveal.cards)
                native_deck = env.engine.probe._query_location(0, 1)
                assert Counter(c.code for c in reveal.cards) == Counter(
                    c.code for c in native_deck)
                assert sum(c.code == SPY for c in owner_view.field) == 1
                assert not any(c.code == SPY for c in owner_view.graveyards[0])
                assert env.engine.probe.loaded_script_sha256["utility.lua"] != (
                    sha256_file(root / "scripts/utility.lua"))
                return
    pytest.fail("empty Spy search did not reveal its Deck to the opponent")
