"""Book sets a public Faith; Nobleman removes it and Deck copies without a Flip Effect."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

BOOK = 14087893
NOBLEMAN = 504700116
FAITH = 31560081
POT = 55144522


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_book_sets_faith_then_nobleman_removes_field_and_deck_copies(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"official/c{BOOK}.lua", f"goat/c{NOBLEMAN}.lua",
               f"official/c{FAITH}.lua")
    for relative in scripts:
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    attacker = tmp_path / "book_nobleman.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        BOOK, NOBLEMAN, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    defender = tmp_path / "faith.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        *([FAITH] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {BOOK, NOBLEMAN}.issubset(c.code for c in obs.hand)
        assert FAITH in {c.code for c in env.engine.probe.observation(1).hand}
        faith_summoned = book_used = book_targeted = nobleman_used = False
        nobleman_targeted = False
        faith_in_deck_before = sum(c.code == FAITH for c in
                                   env.engine.probe._query_location(1, 1))
        assert faith_in_deck_before > 0
        defender_deck_before = obs.deck_counts[1]
        for _ in range(80):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1 and not faith_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == FAITH), None)
                faith_summoned |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 \
                    and obs.phase == "main1" and faith_summoned:
                if not book_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == BOOK), None)
                    book_used |= action is not None
                elif book_targeted and not nobleman_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == NOBLEMAN), None)
                    nobleman_used |= action is not None
            if book_used and not book_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == FAITH), None)
                book_targeted |= action is not None
            if nobleman_used and not nobleman_targeted and actions[0].kind == "select_card":
                assert any(c.controller == 1 and c.zone == "monster"
                           and c.position == "facedown" and c.code is None
                           for c in obs.field)
                assert any(c.controller == 1 and c.code == FAITH
                           for c in obs.known_opponent_field_cards)
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 4
                               and "code" not in a.parameters), None)
                nobleman_targeted |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind == "pass"), None)
            if action is None:
                action = next((a for a in actions if a.kind == "end_phase"), actions[0])
            obs = env.step(action)
            if nobleman_targeted and any(c.code == FAITH for c in obs.banished[1]):
                assert sum(c.code == FAITH for c in obs.banished[1]) \
                    == faith_in_deck_before + 1
                assert obs.deck_counts[1] == defender_deck_before - 1 \
                    - faith_in_deck_before
                assert FAITH not in {c.code for c in obs.graveyards[1]}
                assert not any(c.code == FAITH for c in obs.field)
                assert not any(link.card_code == FAITH for link in obs.chain)
                own = env.engine.probe.observation(0)
                other = env.engine.probe.observation(1)
                assert own.known_opponent_field_cards == ()
                assert own.known_opponent_hand_cards == ()
                assert all(event.recipient == 0 for event in own.private_reveals)
                assert all(event.recipient == 1 for event in other.private_reveals)
                assert len(own.private_reveals) == len(other.private_reveals) == 1
                assert set(scripts).issubset(env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Book / Nobleman / Faith line did not resolve")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_nobleman_stops_reuse_after_faith_recovers_pot(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"official/c{BOOK}.lua", f"goat/c{NOBLEMAN}.lua",
               f"official/c{FAITH}.lua", f"official/c{POT}.lua")
    for relative in scripts:
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    attacker = tmp_path / "book_nobleman.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        BOOK, NOBLEMAN, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    defender = tmp_path / "faith_pot.ydk"
    defender_cards = [*([FAITH] * 3), *VANILLA_DECK[3:]]
    defender_cards[6] = POT
    defender.write_text("#main\n" + "\n".join(map(str, defender_cards))
                        + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {BOOK, NOBLEMAN} <= {c.code for c in obs.hand}
        assert {POT, FAITH} <= {c.code for c in env.engine.probe.observation(1).hand}
        attacker_summoned = pot_used = faith_set = faith_flipped = pot_recovered = False
        book_used = book_targeted = nobleman_used = nobleman_targeted = False
        faith_in_deck_before = defender_deck_before = None
        for _ in range(100):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not attacker_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") not in (BOOK, NOBLEMAN)), None)
                attacker_summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not pot_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == POT), None)
                    pot_used |= action is not None
                elif not faith_set:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == FAITH), None)
                    faith_set |= action is not None
            if obs.turn == 4 and obs.acting_player == 1:
                if not faith_flipped:
                    action = next((a for a in actions if a.kind == "flip_summon"
                                   and a.parameters.get("code") == FAITH), None)
                    faith_flipped |= action is not None
                if faith_flipped and not pot_recovered \
                        and actions[0].kind == "select_card":
                    assert tuple(link.card_code for link in obs.chain) == (FAITH,)
                    action = next((a for a in actions if a.parameters.get("code") == POT
                                   and a.parameters.get("location") == 16), None)
                    pot_recovered |= action is not None
            if obs.turn == 5 and obs.acting_player == 0 and pot_recovered:
                if not book_used:
                    assert obs.known_opponent_hand_cards == (POT,)
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == BOOK), None)
                    book_used |= action is not None
                elif book_targeted and not nobleman_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == NOBLEMAN), None)
                    if action is not None:
                        nobleman_used = True
                        defender_deck_before = obs.deck_counts[1]
                        faith_in_deck_before = sum(c.code == FAITH for c in
                            env.engine.probe._query_location(1, 1))
                        assert faith_in_deck_before > 0
            if book_used and not book_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == FAITH
                               and a.parameters.get("controller") == 1), None)
                book_targeted |= action is not None
            if nobleman_used and not nobleman_targeted \
                    and actions[0].kind == "select_card":
                assert obs.known_opponent_hand_cards == (POT,)
                assert any(c.code == FAITH for c in obs.known_opponent_field_cards)
                assert any(c.controller == 1 and c.zone == "monster"
                           and c.position == "facedown" and c.code is None
                           for c in obs.field)
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 4
                               and "code" not in a.parameters), None)
                nobleman_targeted |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind == "pass"), None)
            if action is None:
                action = next((a for a in actions if a.kind == "end_phase"), actions[0])
            obs = env.step(action)
            if nobleman_targeted and FAITH in {c.code for c in obs.banished[1]}:
                assert sum(c.code == FAITH for c in obs.banished[1]) \
                    == faith_in_deck_before + 1
                assert obs.deck_counts[1] == defender_deck_before - faith_in_deck_before
                assert FAITH not in {c.code for c in obs.graveyards[1]}
                assert not any(link.card_code == FAITH for link in obs.chain)
                assert obs.known_opponent_field_cards == ()
                assert obs.known_opponent_hand_cards == (POT,)
                assert POT in {c.code for c in env.engine.probe.observation(1).hand}
                assert any(tuple(c.code for c in event.cards) == (POT,)
                           for event in obs.private_reveals)
                assert set(scripts) <= env.engine.probe.loaded_script_sha256.keys()
                return
    pytest.fail(f"Faith/Pot/Book/Nobleman stalled: Pot={pot_used}, "
                f"Faith={faith_set}/{faith_flipped}/{pot_recovered}, "
                f"Book={book_used}/{book_targeted}, "
                f"Nobleman={nobleman_used}/{nobleman_targeted}, "
                f"turn={obs.turn}, phase={obs.phase}")
