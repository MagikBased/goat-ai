"""The priority report distinguishes Main Deck presence from fixture mentions."""

from pathlib import Path

from goat_ai.evaluation.competitive_corpus import TOURNAMENT_MAIN_DECKS
from scripts.report_competitive_card_priorities import priority_rows


def test_tournament_priority_corpus_excludes_guide_and_includes_bazoo():
    assert len(TOURNAMENT_MAIN_DECKS) == 6
    assert "bazoo_return_weirdchamp_worlds.ydk" in TOURNAMENT_MAIN_DECKS
    assert "flip_control_goatformat_guide.ydk" not in TOURNAMENT_MAIN_DECKS
    root = Path(__file__).resolve().parent.parent / "examples/decks"
    rows = priority_rows(tuple(root / name for name in TOURNAMENT_MAIN_DECKS),
                         (), {})
    by_code = {row["code"]: row for row in rows}
    assert (by_code[14087893]["main_deck_count"],
            by_code[14087893]["main_copies"]) == (6, 14)  # Book of Moon
    assert (by_code[87621407]["main_deck_count"],
            by_code[87621407]["main_copies"]) == (5, 13)  # Dekoichi


def test_priority_rows_uses_main_decks_and_exact_card_ids(tmp_path):
    first = tmp_path / "first.ydk"
    first.write_text("#main\n123\n123\n456\n#extra\n999\n!side\n888\n")
    second = tmp_path / "second.ydk"
    second.write_text("#main\n123\n456\n#extra\n!side\n999\n")
    fixture = tmp_path / "test_historical_one.py"
    fixture.write_text("CARD = 123\nOTHER = 1234\n")
    rows = priority_rows((first, second), (fixture,), {123: "One", 456: "Two"})
    assert [(row["code"], row["main_deck_count"], row["main_copies"])
            for row in rows] == [(123, 2, 3), (456, 2, 2)]
    assert rows[0]["fixture_references"] == [str(fixture)]
    assert rows[1]["fixture_references"] == []
