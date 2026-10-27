"""The 2010 deck validator never infers release eligibility from the banlist."""

import os
import sqlite3
from pathlib import Path

import pytest

from goat_ai.engine.decks import Decklist, read_advanced_restrictions
from goat_ai.engine.edison_decks import validate_edison_deck
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.engine.protocol import RulesProfile
from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine


@pytest.fixture
def card_database(tmp_path: Path) -> tuple[Path, set[int]]:
    database = tmp_path / "cards.cdb"
    rows = [(code, 0, 17) for code in range(1, 81)]
    rows += [(81, 1, 17), (100, 0, 0x40), (101, 0, 0x2000),
             (102, 0, 0x800000), (103, 0, 0x4000),
             (104, 0, 0x1000000), (105, 0, 0x4000000)]
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE datas (id INTEGER PRIMARY KEY, alias INTEGER, type INTEGER)")
        connection.executemany("INSERT INTO datas VALUES (?, ?, ?)", rows)
    return database, {row[0] for row in rows}


def test_edison_accepts_2009_main_extra_side_sizes_and_synchros(card_database):
    database, eligible = card_database
    deck = Decklist(tuple(range(1, 61)), (100, 101), tuple(range(61, 76)))
    validate_edison_deck(deck, eligible, {1: 1, 100: 1}, database)


@pytest.mark.parametrize("deck, message", [
    (Decklist(tuple(range(1, 40))), "40 to 60"),
    (Decklist(tuple(range(1, 62))), "40 to 60"),
    (Decklist(tuple(range(1, 41)), (100,) * 16), "cannot exceed 15"),
    (Decklist(tuple(range(1, 41)), side=tuple(range(41, 57))), "cannot exceed 15"),
    (Decklist(tuple(range(1, 41)), (1,)), "not a Fusion or Synchro"),
    (Decklist(tuple(range(1, 40)) + (100,)), "cannot be in Main"),
])
def test_edison_rejects_wrong_deck_size_and_zone(card_database, deck, message):
    database, eligible = card_database
    with pytest.raises(ValueError, match=message):
        validate_edison_deck(deck, eligible, {}, database)


@pytest.mark.parametrize("future_id", (102, 103, 104, 105))
def test_edison_rejects_future_types_even_if_candidate_pool_contains_them(
    card_database, future_id,
):
    database, eligible = card_database
    deck = Decklist(tuple(range(1, 40)) + (future_id,))
    with pytest.raises(ValueError, match="type unavailable in Edison"):
        validate_edison_deck(deck, eligible, {}, database)


def test_edison_requires_separate_release_pool_and_known_database_ids(card_database):
    database, eligible = card_database
    deck = Decklist(tuple(range(1, 41)))
    with pytest.raises(ValueError, match="nonempty audited"):
        validate_edison_deck(deck, set(), {}, database)
    with pytest.raises(ValueError, match="outside the audited Edison pool"):
        validate_edison_deck(deck, eligible - {40}, {}, database)
    with pytest.raises(ValueError, match="absent from the pinned database"):
        validate_edison_deck(Decklist(tuple(range(1, 40)) + (999,)),
                             eligible | {999}, {}, database)


def test_edison_applies_forbidden_and_shared_alias_caps_across_zones(card_database):
    database, eligible = card_database
    deck = Decklist(tuple(range(1, 41)))
    with pytest.raises(ValueError, match="copy limit 0"):
        validate_edison_deck(deck, eligible, {1: 0}, database)
    alias_deck = Decklist(tuple(range(1, 41)), side=(81,))
    with pytest.raises(ValueError, match="copy limit 1"):
        validate_edison_deck(alias_deck, eligible, {1: 1}, database)
    with pytest.raises(ValueError, match="copy limit 3"):
        validate_edison_deck(Decklist(tuple(range(1, 40)) + (40,),
                                      side=(40, 40, 40)), eligible, {}, database)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_edison_constraints_against_pinned_metadata_and_official_limits():
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    database = root / "database/cards.cdb"
    limits = read_advanced_restrictions(
        Path(__file__).resolve().parents[1]
        / "configs/historical/edison_2010_03_01_advanced_limits.tsv")
    stardust, black_rose = 44508094, 73580471
    eligible = set(VANILLA_DECK) | {stardust, black_rose}
    validate_edison_deck(Decklist(VANILLA_DECK, (stardust, black_rose)),
                         eligible, limits, database)
    with pytest.raises(ValueError, match="copy limit 1"):
        validate_edison_deck(Decklist(VANILLA_DECK, (black_rose, black_rose)),
                             eligible, limits, database)


@pytest.mark.parametrize("engine", (RestrictedOcgcoreEngine, ExperimentalOcgcoreEngine))
def test_goat_native_engines_reject_edison_profile(engine, tmp_path):
    with pytest.raises(ValueError, match="native GOAT adapter"):
        engine(tmp_path, RulesProfile(name="tcg-edison-2010-04-20"))
