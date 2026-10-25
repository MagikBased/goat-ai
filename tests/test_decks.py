import os
import sqlite3
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.engine.decks import (
    Decklist,
    main_deck_composition_sha256,
    read_goat_whitelist,
    read_ydk,
    validate_goat_deck,
)
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.engine.protocol import RulesProfile
from goat_ai.environments import GoatEnvironment
from scripts.audit_card_pool import audit

# Independently transcribed April 2005 limits from
# https://www.goatformat.com/cardpool.html for cards appearing in at least
# four of the five sourced tournament Main Deck examples below. Cards absent
# from that page's Forbidden/Limited/Semi-Limited lists may use three copies.
HISTORICAL_STAPLES = {
    71413901: ("Breaker the Magical Warrior", 1),
    44763025: ("Delinquent Duo", 1),
    45986603: ("Snatch Steal", 1),
    55144522: ("Pot of Greed", 1),
    504700116: ("Nobleman of Crossout", 2),
    14087893: ("Book of Moon", 3),
    504700118: ("Black Luster Soldier - Envoy of the Beginning", 1),
    19613556: ("Heavy Storm", 1),
    511000824: ("Ring of Destruction", 1),
    79571449: ("Graceful Charity", 1),
    64697231: ("Trap Dustshoot", 3),
    504700178: ("Sangan", 1),
    44095762: ("Mirror Force", 1),
    7572887: ("D.D. Warrior Lady", 1),
    87621407: ("Dekoichi the Battlechanted Locomotive", 3),
    53582587: ("Torrential Tribute", 1),
    9596126: ("Chaos Sorcerer", 3),
    5318639: ("Mystical Space Typhoon", 1),
}

SOURCED_TOURNAMENT_MAIN_DECKS = (
    "goat_control_lolmarcus_2020.ydk",
    "chaos_turbo_riclar_2020.ydk",
    "warrior_montague_clash.ydk",
    "chaos_control_insids_worlds_2022.ydk",
    "chaos_return_dingosig_worlds_2022.ydk",
)

BAZOO_RETURN_WORLD_DECK = Path("examples/decks/bazoo_return_weirdchamp_worlds.ydk")

SHARED_STAPLE_IDS = frozenset({
    71413901, 44763025, 45986603, 55144522, 504700116,
    14087893, 504700118, 19613556, 511000824, 79571449,
})


@pytest.mark.skipif(not Path(".cache/goat-ai/banlist/GOAT.lflist.conf").exists(),
                    reason="native assets not installed")
def test_sourced_staple_limits_match_independent_april_2005_list():
    limits = read_goat_whitelist(Path(".cache/goat-ai/banlist/GOAT.lflist.conf"))
    deck_dir = Path("examples/decks")
    main_sets = [set(read_ydk(deck_dir / name).main)
                 for name in SOURCED_TOURNAMENT_MAIN_DECKS]
    deck_counts = Counter(code for cards in main_sets for code in cards)
    assert {code for code, count in deck_counts.items() if count == 5} \
        == SHARED_STAPLE_IDS
    assert {code for code, count in deck_counts.items() if count >= 4} \
        == HISTORICAL_STAPLES.keys()
    assert {code: limits.get(code) for code in HISTORICAL_STAPLES} == {
        code: expected_limit for code, (_, expected_limit) in HISTORICAL_STAPLES.items()}

    with sqlite3.connect(".cache/goat-ai/database/cards.cdb") as database:
        database.execute("ATTACH DATABASE ? AS goat",
                         (".cache/goat-ai/database/goat-entries.cdb",))
        database.execute("ATTACH DATABASE ? AS unofficial",
                         (".cache/goat-ai/database/cards-unofficial.cdb",))
        for code, (expected_name, _) in HISTORICAL_STAPLES.items():
            names = [row[0] for schema in ("goat", "main", "unofficial")
                     if (row := database.execute(
                         f"SELECT name FROM {schema}.texts WHERE id=?", (code,)).fetchone())]
            assert len(names) == 1
            assert names[0].removesuffix(" (GOAT)").removesuffix(" (Pre-Errata)") \
                == expected_name


def test_ydk_sections_and_errors(tmp_path):
    path = tmp_path / "sample.ydk"
    path.write_text("#created by player\n#main\n123\n#extra\n456\n!side\n789\n")
    assert read_ydk(path) == Decklist((123,), (456,), (789,))
    path.write_text("#main\nnot-a-card\n")
    with pytest.raises(ValueError, match="line 2"):
        read_ydk(path)


def test_main_deck_fingerprint_ignores_order_comments_and_side(tmp_path):
    first = tmp_path / "first.ydk"
    second = tmp_path / "second.ydk"
    first.write_text("#main\n123\n456\n123\n#extra\n777\n!side\n888\n")
    second.write_text("#changed comment\n#main\n456\n123\n123\n#extra\n999\n!side\n666\n")
    expected = main_deck_composition_sha256(read_ydk(first))
    assert expected == main_deck_composition_sha256(read_ydk(second))
    second.write_text("#main\n456\n123\n456\n")
    assert expected != main_deck_composition_sha256(read_ydk(second))


@pytest.mark.skipif(not Path(".cache/goat-ai/banlist/GOAT.lflist.conf").exists(),
                    reason="native assets not installed")
def test_sourced_bazoo_return_deck_matches_published_counts_and_is_legal():
    root = Path(".cache/goat-ai")
    deck = read_ydk(BAZOO_RETURN_WORLD_DECK)
    assert len(deck.main) == 40
    assert deck.extra == deck.side == ()
    assert Counter(deck.main)[40133511] == 3  # Bazoo the Soul-Eater
    assert Counter(deck.main)[27174286] == 3  # Return from the Different Dimension
    assert Counter(deck.main)[504700054] == 3  # GOAT Thunder Dragon
    validate_goat_deck(deck, read_goat_whitelist(root / "banlist/GOAT.lflist.conf"),
                       root / "database/cards.cdb", root / "database/goat-entries.cdb",
                       root / "database/cards-unofficial.cdb")


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


@pytest.mark.skipif(not Path(".cache/goat-ai/database/goat-entries.cdb").exists(),
                    reason="GOAT variant database not installed")
def test_pinned_goat_variant_uses_historical_id_and_copy_limit():
    root = Path(".cache/goat-ai")
    limits = read_goat_whitelist(root / "banlist/GOAT.lflist.conf")
    database = root / "database/cards.cdb"
    variants = root / "database/goat-entries.cdb"
    nobleman = 504700116
    assert limits[nobleman] == 2
    validate_goat_deck(Decklist((nobleman,) + VANILLA_DECK[1:]),
                       limits, database, variants)
    with pytest.raises(ValueError, match="copy limit"):
        validate_goat_deck(Decklist((nobleman,) * 3 + VANILLA_DECK[3:]),
                           limits, database, variants)
    with pytest.raises(ValueError, match="whitelist"):
        validate_goat_deck(Decklist((71044499,) + VANILLA_DECK[1:]),
                           limits, database, variants)


@pytest.mark.skipif(not Path(".cache/goat-ai/database/cards-unofficial.cdb").exists(),
                    reason="all pinned card databases not installed")
def test_every_allowed_goat_id_has_pinned_metadata():
    root = Path(".cache/goat-ai")
    limits = read_goat_whitelist(root / "banlist/GOAT.lflist.conf")
    with sqlite3.connect(root / "database/cards.cdb") as connection:
        connection.execute("ATTACH DATABASE ? AS goat",
                           (str(root / "database/goat-entries.cdb"),))
        connection.execute("ATTACH DATABASE ? AS unofficial",
                           (str(root / "database/cards-unofficial.cdb"),))
        missing = [code for code, limit in limits.items() if limit > 0 and not any(
            connection.execute(f"SELECT 1 FROM {schema}.datas WHERE id=?", (code,)).fetchone()
            for schema in ("goat", "main", "unofficial")
        )]
    assert len([code for code, limit in limits.items() if limit > 0]) == 1685
    assert missing == []
    validate_goat_deck(Decklist((511001039,) + VANILLA_DECK[1:]), limits,
                       root / "database/cards.cdb", root / "database/goat-entries.cdb",
                       root / "database/cards-unofficial.cdb")


@pytest.mark.skipif(not Path(".cache/goat-ai/database/cards-unofficial.cdb").exists(),
                    reason="all pinned card databases not installed")
def test_pinned_goat_card_script_path_inventory():
    result = audit(Path(".cache/goat-ai"))
    assert result["allowed_ids"] == 1685
    assert result["missing_metadata"] == []
    assert result["missing_script_path"] == []
    assert result["direct_script_paths"] + result["alias_script_paths"] == 1339


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_historical_main_deck_has_no_60_card_maximum(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    limits = read_goat_whitelist(root / "banlist/GOAT.lflist.conf")
    with sqlite3.connect(root / "database/cards.cdb") as connection:
        additional = tuple(code for (code,) in connection.execute(
            "SELECT id FROM datas WHERE type=17 ORDER BY id")
            if limits.get(code, 0) > 0 and code not in VANILLA_DECK)[:21]
    assert len(additional) == 21
    main = VANILLA_DECK + additional
    validate_goat_deck(Decklist(main), limits, root / "database/cards.cdb")
    with pytest.raises(ValueError, match="at least 40"):
        validate_goat_deck(Decklist(main[:39]), limits, root / "database/cards.cdb")
    deck = tmp_path / "61_cards.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, main)) + "\n")
    with GoatEnvironment(str(deck), str(deck), 42,
                         ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert observation.deck_counts == (55, 56)
        assert len(observation.hand) == 6


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_historical_side_deck_size_and_community_exception(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    limits = read_goat_whitelist(root / "banlist/GOAT.lflist.conf")
    deck = Decklist(VANILLA_DECK, side=(39507162,))
    with pytest.raises(ValueError, match="0 or 15"):
        validate_goat_deck(deck, limits, root / "database/cards.cdb")
    validate_goat_deck(deck, limits, root / "database/cards.cdb",
                       side_deck_policy="community")
    with sqlite3.connect(root / "database/cards.cdb") as connection:
        side_cards = tuple(code for (code,) in connection.execute(
            "SELECT id FROM datas WHERE type=17 ORDER BY id")
            if limits.get(code, 0) > 0 and code not in VANILLA_DECK)[:15]
    assert len(side_cards) == 15
    validate_goat_deck(Decklist(VANILLA_DECK, side=side_cards), limits,
                       root / "database/cards.cdb")
    with pytest.raises(ValueError, match="exceeds 15"):
        validate_goat_deck(Decklist(VANILLA_DECK, side=side_cards + (39507162,)),
                           limits, root / "database/cards.cdb",
                           side_deck_policy="community")
    path = tmp_path / "short_side.ydk"
    path.write_text("#main\n" + "\n".join(map(str, deck.main))
                    + "\n!side\n39507162\n")
    with pytest.raises(ValueError, match="0 or 15"):
        ExperimentalOcgcoreEngine(root)._load_deck(str(path))
    community = RulesProfile(side_deck_policy="community")
    with GoatEnvironment(str(path), str(path), 42,
                         ExperimentalOcgcoreEngine(root, community)) as env:
        assert len(env.reset().hand) == 6
