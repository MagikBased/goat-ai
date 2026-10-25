"""Trap Dustshoot's opponent-hand reveal and monster return stay player-scoped."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

DUSTSHOOT = 64697231
BOOK_OF_MOON = 14087893
MYSTICAL_SPACE_TYPHOON = 5318639
NONMONSTER_CARDS = (12607053, BOOK_OF_MOON, 4178474, 56120475, 60082869)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_trap_dustshoot_reveals_hand_only_to_chooser_and_returns_monster(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{DUSTSHOOT}.lua").is_file():
        pytest.skip("Trap Dustshoot script not installed")
    own = tmp_path / "dustshoot.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        *([DUSTSHOOT] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(own), "examples/decks/vanilla_probe.ydk", seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        set_trap = activated = selected = False
        chosen_code = before_count = before_deck_count = None
        before_hand = None
        revealed_hand = None
        for _ in range(35):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not set_trap:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                set_trap |= action is not None
            if set_trap and not activated and observation.turn == 2 \
                    and observation.acting_player == 0:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                if action is not None:
                    assert observation.opponent_hand_count >= 4
                    assert not observation.private_reveals
                    other = env.engine.probe.observation(1)
                    assert any(c.controller == 0 and c.zone == "spell_trap"
                               and c.position == "facedown" and c.code is None
                               for c in other.field)
                    before_count = observation.opponent_hand_count
                    before_deck_count = observation.deck_counts[1]
                    activated = True
            if activated and not selected and actions[0].kind == "select_card":
                assert observation.acting_player == observation.viewer == 0
                assert observation.chain[0].card_code == DUSTSHOOT
                revealed = [card.code for event in observation.private_reveals
                            if event.recipient == 0 for card in event.cards
                            if card.controller == 1 and card.location == 2]
                assert Counter(a.parameters["code"] for a in actions) == Counter(revealed)
                assert len(revealed) == before_count
                revealed_hand = Counter(revealed)
                assert Counter(observation.known_opponent_hand_cards) == revealed_hand
                assert all(a.parameters["location"] == 2
                           and "sequence" not in a.parameters for a in actions)
                other = env.engine.probe.observation(1)
                assert not other.private_reveals
                before_hand = Counter(c.code for c in other.hand)
                action = actions[0]
                chosen_code = action.parameters["code"]
                selected = True
            if selected and observation.deck_counts[1] == before_deck_count + 1:
                other = env.engine.probe.observation(1)
                assert len(other.hand) == before_count - 1
                assert before_hand - Counter(c.code for c in other.hand) == {
                    chosen_code: 1}
                remaining = revealed_hand - Counter((chosen_code,))
                assert Counter(env.engine.probe.observation(0)
                               .known_opponent_hand_cards) == remaining
                assert not other.known_opponent_hand_cards
                assert f"official/c{DUSTSHOOT}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                agents = (RandomAgent(3), RandomAgent(4))
                for _ in range(5000):
                    action = agents[observation.acting_player].select_action(
                        observation, env.legal_actions())
                    observation = env.step(action)
                    if env.is_terminal():
                        trajectory = env.trajectory()
                        assert trajectory.schema_version == 22
                        assert chosen_code is not None
                        path = tmp_path / "dustshoot.json"
                        write_trajectory(path, trajectory)
                        assert verify_trajectory(read_trajectory(path),
                                                 ExperimentalOcgcoreEngine(root)) == len(
                                                     trajectory.decisions)
                        return
                pytest.fail("Trap Dustshoot duel did not finish")
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
    pytest.fail("Trap Dustshoot did not return an opponent monster to the Deck")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_dustshoot_requires_at_least_four_opponent_hand_cards(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{DUSTSHOOT}.lua").is_file():
        pytest.skip("Trap Dustshoot script not installed")
    own = tmp_path / "dustshoot.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        *([DUSTSHOOT] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    opposing = tmp_path / "books.ydk"
    opposing.write_text("#main\n" + "\n".join(map(str, (
        *([BOOK_OF_MOON] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(own), str(opposing), seed=28,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        set_trap = summoned = False
        books_set = 0
        saw_three = False
        for _ in range(65):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not set_trap:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                set_trap |= action is not None
            if observation.turn == 2 and observation.acting_player == 1:
                if not summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    summoned |= action is not None
                if action is None and books_set < 2:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOOK_OF_MOON), None)
                    books_set += action is not None
            if set_trap and observation.acting_player == 0 and books_set == 2:
                if observation.opponent_hand_count == 3:
                    saw_three = True
                    assert not any(a.kind == "chain" and a.parameters.get("code")
                                   == DUSTSHOOT for a in actions)
                if observation.turn == 4 and observation.opponent_hand_count == 4:
                    assert saw_three and summoned
                    assert any(a.kind == "chain" and a.parameters.get("code")
                               == DUSTSHOOT for a in actions)
                    return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
    pytest.fail("Dustshoot hand-size threshold was not exercised")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_dustshoot_reveals_nonmonster_hand_without_return_target(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{DUSTSHOOT}.lua").is_file():
        pytest.skip("Trap Dustshoot script not installed")
    own = tmp_path / "dustshoot.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        *([DUSTSHOOT] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    opposing = tmp_path / "nonmonsters.ydk"
    opposing.write_text("#main\n" + "\n".join(map(str, (
        *(code for code in NONMONSTER_CARDS for _ in range(3)),
        *VANILLA_DECK[:25]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(opposing), seed=2078,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert DUSTSHOOT in {c.code for c in observation.hand}
        set_trap = activated = False
        before_deck = None
        for _ in range(35):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 \
                    and not set_trap:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                set_trap |= action is not None
            if set_trap and observation.turn == 2 and observation.acting_player == 0 \
                    and not activated:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                if action is not None:
                    assert observation.opponent_hand_count == 6
                    own_hand = env.engine.probe.observation(1).hand
                    assert len(own_hand) == 6
                    assert all(c.code in NONMONSTER_CARDS for c in own_hand)
                    before_deck = observation.deck_counts[1]
                    activated = True
            if activated:
                assert actions[0].kind != "select_card"
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if activated and any(c.code == DUSTSHOOT for c in observation.graveyards[0]):
                chooser = env.engine.probe.observation(0)
                opponent = env.engine.probe.observation(1)
                assert chooser.opponent_hand_count == 6
                assert chooser.deck_counts[1] == before_deck
                assert Counter(c.code for event in chooser.private_reveals
                               for c in event.cards) == Counter(c.code for c in opponent.hand)
                assert all(event.recipient == 0 for event in chooser.private_reveals)
                assert not opponent.private_reveals
                assert Counter(chooser.known_opponent_hand_cards) == Counter(
                    c.code for c in opponent.hand)
                assert not opponent.known_opponent_hand_cards
                assert f"official/c{DUSTSHOOT}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Dustshoot did not finish resolving against a nonmonster hand")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_dustshoot_still_resolves_after_book_reduces_hand_below_four(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (DUSTSHOOT, BOOK_OF_MOON):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    own = tmp_path / "dustshoot.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        *([DUSTSHOOT] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    opposing = tmp_path / "books.ydk"
    opposing.write_text("#main\n" + "\n".join(map(str, (
        *([BOOK_OF_MOON] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(opposing), seed=28,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        trap_set = monster_summoned = book_set = dust_activated = False
        book_chained = book_targeted = target_selected = False
        summoned_code = None
        before_deck = None
        for _ in range(75):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 \
                    and not trap_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                trap_set |= action is not None
            if observation.turn == 2 and observation.acting_player == 1:
                if not monster_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        summoned_code = action.parameters["code"]
                        monster_summoned = True
                if monster_summoned and action is None and not book_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOOK_OF_MOON), None)
                    book_set |= action is not None
            if book_set and observation.acting_player == 0 and not dust_activated:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                if action is not None:
                    assert observation.opponent_hand_count == 4
                    before_deck = observation.deck_counts[1]
                    dust_activated = True
            if dust_activated and observation.acting_player == 1 and not book_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK_OF_MOON
                               and a.parameters.get("location") == 2), None)
                book_chained |= action is not None
            if book_chained and not book_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("controller") == 1
                               and a.parameters.get("code") == summoned_code), None)
                book_targeted |= action is not None
            if book_targeted and not target_selected and observation.acting_player == 0 \
                    and actions[0].kind == "select_card":
                assert observation.acting_player == observation.viewer == 0
                assert observation.opponent_hand_count == 3
                revealed = [c.code for event in observation.private_reveals
                            for c in event.cards if c.controller == 1]
                assert len(revealed) == 3
                assert Counter(a.parameters["code"] for a in actions) == Counter(revealed)
                assert not env.engine.probe.observation(1).private_reveals
                action = actions[0]
                target_selected = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if target_selected and observation.deck_counts[1] == before_deck + 1:
                assert len(env.engine.probe.observation(1).hand) == 2
                assert env.engine.probe.observation(0).opponent_hand_count == 2
                assert observation.life_points == (8000, 8000)
                assert BOOK_OF_MOON in {c.code for c in observation.graveyards[1]}
                assert any(c.controller == 1 and c.zone == "monster"
                           and c.position == "facedown" for c in observation.field)
                loaded = env.engine.probe.loaded_script_sha256
                assert {f"official/c{DUSTSHOOT}.lua",
                        f"official/c{BOOK_OF_MOON}.lua"}.issubset(loaded)
                return
    pytest.fail("Dustshoot did not resolve after Book reduced the hand to three")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_dustshoot_resolves_after_chained_mst_destroys_it(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (DUSTSHOOT, MYSTICAL_SPACE_TYPHOON):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    own = tmp_path / "dustshoot.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        *([DUSTSHOOT] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    opposing = tmp_path / "mst_book.ydk"
    opposing.write_text("#main\n" + "\n".join(map(str, (
        *([BOOK_OF_MOON] * 3), MYSTICAL_SPACE_TYPHOON,
        *VANILLA_DECK[4:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(opposing), seed=157,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        trap_set = monster_summoned = book_set = dust_activated = False
        mst_chained = mst_targeted = selected = False
        before_deck = None
        for _ in range(75):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 \
                    and not trap_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                trap_set |= action is not None
            if observation.turn == 2 and observation.acting_player == 1:
                if not monster_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    monster_summoned |= action is not None
                if monster_summoned and action is None and not book_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOOK_OF_MOON), None)
                    book_set |= action is not None
            if book_set and observation.acting_player == 0 and not dust_activated:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                if action is not None:
                    assert observation.opponent_hand_count == 4
                    before_deck = observation.deck_counts[1]
                    dust_activated = True
            if dust_activated and observation.acting_player == 1 and not mst_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == MYSTICAL_SPACE_TYPHOON
                               and a.parameters.get("location") == 2), None)
                mst_chained |= action is not None
            if mst_chained and not mst_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("controller") == 0
                               and a.parameters.get("code") == DUSTSHOOT), None)
                mst_targeted |= action is not None
            if mst_targeted and not selected and observation.acting_player == 0 \
                    and actions[0].kind == "select_card":
                assert observation.opponent_hand_count == 3
                assert DUSTSHOOT in {c.code for c in observation.graveyards[0]}
                assert len([c for event in observation.private_reveals
                            for c in event.cards if c.controller == 1]) == 3
                assert not env.engine.probe.observation(1).private_reveals
                action = actions[0]
                selected = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if selected and observation.deck_counts[1] == before_deck + 1:
                assert env.engine.probe.observation(0).opponent_hand_count == 2
                assert MYSTICAL_SPACE_TYPHOON in {
                    c.code for c in observation.graveyards[1]}
                assert observation.life_points == (8000, 8000)
                loaded = env.engine.probe.loaded_script_sha256
                assert {f"official/c{DUSTSHOOT}.lua",
                        f"official/c{MYSTICAL_SPACE_TYPHOON}.lua"}.issubset(loaded)
                return
    pytest.fail("Dustshoot did not resolve after chained MST destroyed it")
