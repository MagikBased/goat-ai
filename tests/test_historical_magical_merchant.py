"""Magical Merchant reveals excavated cards and a kept Spell to both players."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

MAGICAL_MERCHANT = 32362575
POT_OF_GREED = 55144522


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
        set_merchant = flipped = False
        deck_before = hand_before = None
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
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if flipped and POT_OF_GREED in {c.code for c in obs.hand}:
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
                return
    pytest.fail("Magical Merchant did not excavate and keep Pot of Greed")


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
