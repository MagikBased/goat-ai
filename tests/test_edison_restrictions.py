from pathlib import Path

import pytest

from goat_ai.engine.decks import read_advanced_restrictions

TABLE = Path(__file__).resolve().parents[1] / "configs/historical/edison_2010_03_01_advanced_limits.tsv"


def test_official_march_2010_restrictions_are_complete_and_distinct() -> None:
    limits = read_advanced_restrictions(TABLE)
    assert len(limits) == 135
    assert [list(limits.values()).count(cap) for cap in (0, 1, 2)] == [45, 70, 20]
    assert limits[72989439] == 0  # Black Luster Soldier
    assert limits[31560081] == 0  # Magician of Faith
    assert limits[32646477] == 0  # Dark Strike Fighter
    assert limits[73580471] == 1  # Black Rose Dragon
    assert limits[70095154] == 2  # Cyber Dragon
    assert limits[70583986] == 2  # Dewloren: listed, but released after Edison
    assert 44508094 not in limits  # Stardust Dragon: unrestricted by this list


@pytest.mark.parametrize("body", [
    "card_id\tmax_copies\tcard_name\n123\t3\tBad cap\n",
    "card_id\tmax_copies\tcard_name\n123\t1\tA\n123\t2\tA\n",
    "card_id\tmax_copies\tcard_name\n123\t1\t\n",
])
def test_invalid_restriction_table_fails_closed(tmp_path: Path, body: str) -> None:
    table = tmp_path / "bad.tsv"
    table.write_text(body)
    with pytest.raises(ValueError):
        read_advanced_restrictions(table)
