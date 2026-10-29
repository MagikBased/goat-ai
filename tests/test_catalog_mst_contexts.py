"""The removal catalog describes only public and acting-player-visible cards."""

from dataclasses import replace

from goat_ai.actions import Action
from goat_ai.observations import CardView, Observation
from goat_ai.replay import DecisionRecord, Trajectory
from scripts.catalog_mst_contexts import catalog_opportunities, catalog_trajectory


def test_mst_catalog_preserves_hidden_opponent_backrow_and_excludes_source():
    source = CardView(0, "spell_trap", "facedown", 5318639, 0)
    own = CardView(0, "spell_trap", "faceup", 72302403, 1)
    unknown = CardView(1, "spell_trap", "facedown", None, 0)
    view = Observation(
        viewer=0, acting_player=0, turn=2, phase="main1",
        life_points=(8000, 8000), hand=(), field=(source, own, unknown),
        graveyards=((), ()), banished=((), ()), opponent_hand_count=4,
        deck_counts=(35, 35), extra_deck_counts=(0, 0), turn_player=0)
    mst = Action("mst", "chain", 0,
                 {"code": 5318639, "location": 8, "sequence": 0})
    passing = Action("pass", "pass", 0)
    record = DecisionRecord(view, (mst, passing), mst)
    replay = Trajectory("goat", ("a.ydk", "b.ydk"), 7, (record,), 1,
                        source="policy_evaluation",
                        skill_metadata={"demonstrator_seat": 0})
    row, = catalog_trajectory(replay, {72302403: (2, 0, 0)})
    assert row["visible_backrow_distribution"] == "mixed"
    assert row["pass_offered"] is True
    assert row["backrow"] == [
        {"relative_controller": "own", "position": "faceup",
         "code": 72302403, "printed_type": 2},
        {"relative_controller": "opponent", "position": "facedown",
         "code": None, "printed_type": None},
    ]
    enemy_only = replace(replay, decisions=(replace(
        record, observation=replace(view, field=(source, unknown))),))
    assert catalog_trajectory(enemy_only, {})[0]["visible_backrow_distribution"] == (
        "enemy_only")
    passed = replace(replay, decisions=(replace(record, selected_action=passing),))
    opportunity, = catalog_opportunities(passed, {72302403: (2, 0, 0)})
    assert opportunity["selected_mst"] is False
    assert opportunity["selected_action_kind"] == "pass"
    assert opportunity["visible_backrow_distribution"] == "mixed"
