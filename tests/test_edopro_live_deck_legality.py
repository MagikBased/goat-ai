"""Recorded EDOPro decks must be GOAT legal before confirmed-choice training."""

from pathlib import Path

import pytest

from goat_ai.engine.decks import read_ydk
from goat_ai.replay.edopro_container import ReplayDeck
from goat_ai.replay.edopro_live_verify import goat_replay_deck_legality


NATIVE = Path(".cache/goat-ai")


@pytest.mark.skipif(not (NATIVE / "database/cards.cdb").exists(),
                    reason="native assets not installed")
def test_recorded_main_and_extra_decks_must_pass_goat_whitelist():
    source = read_ydk("examples/decks/warrior_montague_clash.ydk")
    legal = ReplayDeck(source.main, source.extra)
    assert goat_replay_deck_legality((legal, legal), NATIVE) == (True, None)

    banned = ReplayDeck((123456789, *source.main[1:]), source.extra)
    allowed, reason = goat_replay_deck_legality((legal, banned), NATIVE)
    assert not allowed and "player 2 Deck" in reason

    wrong_extra = ReplayDeck(source.main, (source.main[0],))
    allowed, reason = goat_replay_deck_legality((legal, wrong_extra), NATIVE)
    assert not allowed and "Fusion" in reason
