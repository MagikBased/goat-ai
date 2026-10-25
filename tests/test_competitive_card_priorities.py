"""The priority report distinguishes Main Deck presence from fixture mentions."""

from scripts.report_competitive_card_priorities import priority_rows


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
