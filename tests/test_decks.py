from pathlib import Path

import pytest

from goat_ai.engine.decks import Decklist, read_goat_whitelist, read_ydk, validate_goat_deck
from goat_ai.engine.probe_deck import VANILLA_DECK


def test_ydk_sections_and_errors(tmp_path):
    path = tmp_path / "sample.ydk"
    path.write_text("#created by player\n#main\n123\n#extra\n456\n!side\n789\n")
    assert read_ydk(path) == Decklist((123,), (456,), (789,))
    path.write_text("#main\nnot-a-card\n")
    with pytest.raises(ValueError, match="line 2"):
        read_ydk(path)


def test_whitelist_parsing(tmp_path):
    path = tmp_path / "GOAT.lflist.conf"
    path.write_text("!GOAT\n$whitelist\n123 1 -- card\n123 1 -- duplicate\n456 0\n")
    assert read_goat_whitelist(path) == {123: 1, 456: 0}
    path.write_text("$whitelist\n123 1\n123 2\n")
    with pytest.raises(ValueError, match="duplicate"):
        read_goat_whitelist(path)


@pytest.mark.skipif(not Path(".cache/goat-ai/banlist/GOAT.lflist.conf").exists(),
                    reason="native assets not installed")
def test_pinned_goat_fixture_legality():
    root = Path(".cache/goat-ai")
    limits = read_goat_whitelist(root / "banlist/GOAT.lflist.conf")
    database = root / "database/cards.cdb"
    validate_goat_deck(Decklist(VANILLA_DECK), limits, database)
    with pytest.raises(ValueError, match="forbidden"):
        validate_goat_deck(Decklist(VANILLA_DECK[:-1] + (12580477,)), limits, database)
    with pytest.raises(ValueError, match="copy limit"):
        validate_goat_deck(Decklist((VANILLA_DECK[0],) * 40), limits, database)
    with pytest.raises(ValueError, match="Fusion monster"):
        validate_goat_deck(Decklist(VANILLA_DECK, extra=(VANILLA_DECK[0],)),
                           limits, database)
