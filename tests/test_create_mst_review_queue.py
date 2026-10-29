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


def test_opportunity_selection_includes_selected_and_unused_mst():
    candidates = [
        {"trajectory": f"{i}.json", "decision_index": i,
         "visible_backrow_distribution": context, "selected_mst": chosen}
        for i, (context, chosen) in enumerate((
            ("own_only", True), ("own_only", False),
            ("enemy_only", True), ("enemy_only", False),
            ("mixed", True), ("mixed", False)))
    ]
    selected = select_mst_items(candidates, 6, 1, balance_opportunities=True)
    assert [(x["visible_backrow_distribution"], x["selected_mst"])
            for x in selected] == [
                ("own_only", True), ("own_only", False),
                ("enemy_only", True), ("enemy_only", False),
                ("mixed", True), ("mixed", False)]
