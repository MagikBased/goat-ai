"""Magical Merchant reveals excavated cards and a kept Spell to both players."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

MAGICAL_MERCHANT = 32362575
POT_OF_GREED = 55144522
BOOK_OF_MOON = 14087893


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_magical_merchant_excavates_monsters_and_reveals_kept_pot(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (MAGICAL_MERCHANT, POT_OF_GREED):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    deck = tmp_path / "merchant.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        MAGICAL_MERCHANT, MAGICAL_MERCHANT, MAGICAL_MERCHANT,
        POT_OF_GREED, *VANILLA_DECK[4:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=10,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert MAGICAL_MERCHANT in {c.code for c in obs.hand}
        assert POT_OF_GREED not in {c.code for c in obs.hand}
        set_merchant = flipped = merchant_checked = pot_used = False
        deck_before = hand_before = None
        pot_deck_before = pot_hand_before = None
        grave_before = Counter()
        for _ in range(55):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not set_merchant:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == MAGICAL_MERCHANT), None)
                set_merchant = action is not None
            if obs.turn == 3 and obs.acting_player == 0 and set_merchant and not flipped:
                action = next((a for a in actions if a.kind == "flip_summon"
                               and a.parameters.get("code") == MAGICAL_MERCHANT), None)
                if action is not None:
                    deck_before = obs.deck_counts[0]
                    hand_before = len(obs.hand)
                    grave_before = Counter(c.code for c in obs.graveyards[0])
                    flipped = True
            if merchant_checked and not pot_used and obs.acting_player == 0:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == POT_OF_GREED), action)
                if action is not None and action.parameters.get("code") == POT_OF_GREED:
                    pot_deck_before = obs.deck_counts[0]
                    pot_hand_before = len(obs.hand)
                    pot_used = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if flipped and not merchant_checked and POT_OF_GREED in {
                    c.code for c in obs.hand}:
                opponent = env.engine.probe.observation(1)
                milled = Counter(c.code for c in obs.graveyards[0]) - grave_before
                excavated = [event for event in obs.public_reveals
                             if event.player == 0 and event.zone == "deck_top"
                             and POT_OF_GREED in event.codes]
                assert len(excavated) == 1
                assert Counter(excavated[0].codes) == milled + Counter((POT_OF_GREED,))
                assert sum(milled.values()) == 2
                assert obs.deck_counts[0] == deck_before - len(excavated[0].codes)
                assert len(obs.hand) == hand_before + 1
                assert opponent.public_reveals == obs.public_reveals
                assert opponent.known_opponent_hand_cards == (POT_OF_GREED,)
                assert opponent.opponent_hand_count == len(obs.hand)
                assert [[c.code for c in event.cards]
                        for event in opponent.private_reveals] == [[POT_OF_GREED]]
                assert not obs.private_reveals
                assert f"official/c{MAGICAL_MERCHANT}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                merchant_checked = True
            if pot_used and POT_OF_GREED in {c.code for c in obs.graveyards[0]} \
                    and not obs.chain:
                opponent = env.engine.probe.observation(1)
                assert obs.deck_counts[0] == pot_deck_before - 2
                assert len(obs.hand) == pot_hand_before + 1
                assert opponent.opponent_hand_count == len(obs.hand)
                assert not opponent.known_opponent_hand_cards
                assert [[c.code for c in event.cards]
                        for event in opponent.private_reveals] == [[POT_OF_GREED]]
                assert f"official/c{POT_OF_GREED}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                agents = (RandomAgent(10), RandomAgent(11))
                for _ in range(3000):
                    if env.is_terminal():
                        break
                    obs = env.step(agents[obs.acting_player].select_action(
                        obs, env.legal_actions()))
                else:
                    pytest.fail("Magical Merchant/Pot duel did not terminate")
                trajectory = env.trajectory()
                path = tmp_path / "merchant_pot.json"
                write_trajectory(path, trajectory)
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) \
                    == len(trajectory.decisions)
                return
    pytest.fail("Magical Merchant did not excavate and reuse Pot of Greed")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_magical_merchant_without_spell_reveals_deck_and_adds_nothing(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{MAGICAL_MERCHANT}.lua").is_file():
        pytest.skip("Magical Merchant script not installed")
    deck = tmp_path / "monster_only.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        MAGICAL_MERCHANT, MAGICAL_MERCHANT, MAGICAL_MERCHANT,
        *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=10,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert MAGICAL_MERCHANT in {c.code for c in obs.hand}
        set_merchant = flipped = False
        deck_before = hand_before = None
        for _ in range(55):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not set_merchant:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == MAGICAL_MERCHANT), None)
                set_merchant = action is not None
            if obs.turn == 3 and obs.acting_player == 0 and set_merchant and not flipped:
                action = next((a for a in actions if a.kind == "flip_summon"
                               and a.parameters.get("code") == MAGICAL_MERCHANT), None)
                if action is not None:
                    deck_before = obs.deck_counts[0]
                    hand_before = len(obs.hand)
                    flipped = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if flipped and any(event.player == 0 and event.zone == "deck_top"
                               for event in obs.public_reveals):
                opponent = env.engine.probe.observation(1)
                reveal = next(event for event in obs.public_reveals
                              if event.player == 0 and event.zone == "deck_top")
                assert len(reveal.codes) == deck_before
                assert obs.deck_counts[0] == deck_before
                assert len(obs.hand) == hand_before
                assert not obs.graveyards[0]
                assert opponent.public_reveals == obs.public_reveals
                assert not opponent.known_opponent_hand_cards
                assert not opponent.private_reveals
                assert f"official/c{MAGICAL_MERCHANT}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Magical Merchant did not reveal its Spell-free Deck")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_battle_destroyed_merchant_still_resolves_flip_effect(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (MAGICAL_MERCHANT, POT_OF_GREED):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    deck = tmp_path / "merchant_battle.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        MAGICAL_MERCHANT, MAGICAL_MERCHANT, MAGICAL_MERCHANT,
        POT_OF_GREED, *VANILLA_DECK[4:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=10,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert MAGICAL_MERCHANT in {card.code for card in obs.hand}
        assert POT_OF_GREED not in {card.code for card in obs.hand}
        merchant_set = attacker_summoned = attacked = effect_checked = checked = False
        deck_before = hand_before = None
        grave_before = Counter()
        agents = (RandomAgent(10), RandomAgent(11))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / "merchant_battle.json"
                write_trajectory(path, env.trajectory())
                replay = read_trajectory(path)
                assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) \
                    == len(replay.decisions)
                audit_trajectory_visibility(replay)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not merchant_set:
                action = next((candidate for candidate in actions
                               if candidate.kind == "set_monster"
                               and candidate.parameters.get("code") == MAGICAL_MERCHANT), None)
                merchant_set = action is not None
            if obs.turn == 2 and obs.acting_player == 1 and merchant_set:
                if obs.phase == "main1" and not attacker_summoned:
                    action = next((candidate for candidate in actions
                                   if candidate.kind == "normal_summon"), None)
                    attacker_summoned = action is not None
                elif obs.phase == "main1" and attacker_summoned:
                    action = next((candidate for candidate in actions
                                   if candidate.kind == "battle_phase"), None)
                elif obs.phase == "battle_start" and not attacked:
                    action = next((candidate for candidate in actions
                                   if candidate.kind == "attack"), None)
                    if action is not None:
                        deck_before = obs.deck_counts[0]
                        hand_before = obs.opponent_hand_count
                        grave_before = Counter(card.code for card in obs.graveyards[0])
                        attacked = True
                elif attacked and actions[0].kind == "select_card":
                    action = next((candidate for candidate in actions
                                   if candidate.parameters.get("controller") == 0
                                   and candidate.parameters.get("location") == 4), None)
                    if action is not None:
                        assert "code" not in action.parameters
            if action is None and not checked:
                action = next((candidate for candidate in actions
                               if candidate.kind in ("place", "pass", "end_phase")),
                              actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if attacked and not effect_checked and POT_OF_GREED in {
                    card.code for card in env.engine.probe.observation(0).hand}:
                owner = env.engine.probe.observation(0)
                opponent = env.engine.probe.observation(1)
                milled = Counter(card.code for card in owner.graveyards[0]) - grave_before
                # Flip effects resolve after damage calculation, while the
                # battle-destroyed monster has not yet reached the Graveyard.
                assert milled[MAGICAL_MERCHANT] == 0
                reveal = next(event for event in owner.public_reveals
                              if event.player == 0 and event.zone == "deck_top"
                              and POT_OF_GREED in event.codes)
                assert Counter(reveal.codes) == milled + Counter((POT_OF_GREED,))
                assert owner.deck_counts[0] == deck_before - len(reveal.codes)
                assert len(owner.hand) == hand_before + 1
                assert opponent.known_opponent_hand_cards == (POT_OF_GREED,)
                assert any(card.code == MAGICAL_MERCHANT for card in owner.field)
                assert f"official/c{MAGICAL_MERCHANT}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                effect_checked = True
            if effect_checked and not checked and MAGICAL_MERCHANT in {
                    card.code for card in obs.graveyards[0]}:
                assert all(card.code != MAGICAL_MERCHANT for card in
                           env.engine.probe.observation(0).field)
                checked = True
    pytest.fail("battle-destroyed Magical Merchant effect did not resolve")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_book", [False, True])
def test_book_chained_to_merchant_flip_preserves_public_excavation(tmp_path, chain_book):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (
        MAGICAL_MERCHANT, POT_OF_GREED, BOOK_OF_MOON)}
    if any(not (root / "scripts" / relative).is_file() for relative in scripts):
        pytest.skip("required card script not installed")
    merchant_deck = tmp_path / "merchant_book_owner.ydk"
    merchant_deck.write_text("#main\n" + "\n".join(map(str, (
        MAGICAL_MERCHANT, MAGICAL_MERCHANT, MAGICAL_MERCHANT,
        POT_OF_GREED, *VANILLA_DECK[4:]))) + "\n#extra\n!side\n")
    book_deck = tmp_path / "merchant_book_opponent.ydk"
    book_deck.write_text("#main\n" + "\n".join(map(str, (
        BOOK_OF_MOON, BOOK_OF_MOON, BOOK_OF_MOON,
        *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(merchant_deck), str(book_deck), seed=11,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert MAGICAL_MERCHANT in {card.code for card in obs.hand}
        assert POT_OF_GREED not in {card.code for card in obs.hand}
        assert BOOK_OF_MOON in {card.code for card in env.engine.probe.observation(1).hand}
        merchant_set = book_set = flipped = responded = targeted = checked = False
        deck_before = hand_before = None
        grave_before = Counter()
        agents = (RandomAgent(110), RandomAgent(111))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"merchant_book_{chain_book}.json"
                write_trajectory(path, env.trajectory())
                replay = read_trajectory(path)
                assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(
                    replay.decisions)
                audit_trajectory_visibility(replay)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not merchant_set:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == MAGICAL_MERCHANT), None)
                merchant_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not book_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == BOOK_OF_MOON), None)
                book_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not flipped:
                action = next((a for a in actions if a.kind == "flip_summon"
                               and a.parameters.get("code") == MAGICAL_MERCHANT), None)
                if action is not None:
                    deck_before = obs.deck_counts[0]
                    hand_before = len(obs.hand)
                    grave_before = Counter(card.code for card in obs.graveyards[0])
                    flipped = True
            if flipped and obs.acting_player == 1 and not responded and obs.chain:
                assert [link.card_code for link in obs.chain] == [MAGICAL_MERCHANT]
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK_OF_MOON), None)
                assert option is not None
                action = option if chain_book else next(a for a in actions if a.kind == "pass")
                responded = True
            if chain_book and responded and not targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == MAGICAL_MERCHANT and a.parameters.get("controller") == 0),
                              None)
                targeted |= action is not None
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if responded and not checked and obs.turn == 3 and obs.phase == "main1" \
                    and obs.acting_player == 0 and not obs.chain \
                    and POT_OF_GREED in {card.code for card in obs.hand}:
                owner = env.engine.probe.observation(0)
                opponent = env.engine.probe.observation(1)
                reveal = next(event for event in owner.public_reveals
                              if event.player == 0 and event.zone == "deck_top"
                              and POT_OF_GREED in event.codes)
                milled = Counter(card.code for card in owner.graveyards[0]) - grave_before
                assert Counter(reveal.codes) == milled + Counter((POT_OF_GREED,))
                assert len(reveal.codes) == 19 and reveal.codes[-1] == POT_OF_GREED
                assert owner.deck_counts[0] == deck_before - len(reveal.codes)
                assert len(owner.hand) == hand_before + 1
                assert opponent.public_reveals == owner.public_reveals
                assert opponent.known_opponent_hand_cards == (POT_OF_GREED,)
                merchant = next(card for card in owner.field
                                if card.controller == 0 and card.code == MAGICAL_MERCHANT)
                if chain_book:
                    assert targeted
                    assert merchant.position == "facedown"
                    assert BOOK_OF_MOON in {card.code for card in owner.graveyards[1]}
                    hidden = next(card for card in opponent.field
                                  if card.controller == 0 and card.sequence == merchant.sequence)
                    assert hidden.code is None and hidden.position == "facedown"
                    assert any(card.code == MAGICAL_MERCHANT
                               and card.sequence == merchant.sequence
                               for card in opponent.known_opponent_field_cards)
                else:
                    assert merchant.position == "faceup"
                    assert BOOK_OF_MOON not in {card.code for card in owner.graveyards[1]}
                loaded = env.engine.probe.loaded_script_sha256
                assert f"official/c{MAGICAL_MERCHANT}.lua" in loaded
                if chain_book:
                    assert f"official/c{BOOK_OF_MOON}.lua" in loaded
                checked = True
        pytest.fail("Magical Merchant / Book chain duel did not terminate")
