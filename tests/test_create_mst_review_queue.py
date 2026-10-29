"""MST review selection keeps contexts diverse without declaring a best play."""

import pytest

from scripts.create_mst_review_queue import select_mst_items


def test_select_mst_items_prioritizes_own_context_and_spreads_replays():
    candidates = [
        {"trajectory": "a.json", "decision_index": 9,
         "visible_backrow_distribution": "enemy_only"},
        {"trajectory": "a.json", "decision_index": 4,
         "visible_backrow_distribution": "own_only"},
        {"trajectory": "a.json", "decision_index": 5,
         "visible_backrow_distribution": "own_only"},
        {"trajectory": "b.json", "decision_index": 2,
         "visible_backrow_distribution": "mixed"},
    ]
    selected = select_mst_items(candidates, limit=3, per_replay=1)
    assert [(item["trajectory"], item["decision_index"]) for item in selected] == [
        ("a.json", 4), ("b.json", 2)]
    with pytest.raises(ValueError, match="positive"):
        select_mst_items(candidates, limit=0, per_replay=1)
