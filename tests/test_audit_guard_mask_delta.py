"""The fixed-state audit distinguishes removed Ring and MST decisions."""

from goat_ai.actions import Action
from goat_ai.observations import CardView, ChainLinkView, Observation
from goat_ai.replay import DecisionRecord, Trajectory
from scripts.audit_guard_mask_delta import count_mask_delta


def test_v5_marginal_mask_counts_recorded_ring_and_one_shot_mst():
    base = {"viewer": 0, "acting_player": 0, "turn": 2, "phase": "main1",
            "life_points": (8000, 8000), "hand": (), "graveyards": ((), ()),
            "banished": ((), ()), "opponent_hand_count": 4,
            "deck_counts": (34, 34), "extra_deck_counts": (0, 0), "turn_player": 0}
    ring_view = Observation(**base, field=(CardView(
        0, "monster", "faceup", 71413901, 0, attack=1600, defense=1000),))
    ring = Action("ring", "chain", 0, {"code": 511000824})
    pass_action = Action("pass", "pass", 0)
    ring_record = DecisionRecord(ring_view, (ring, pass_action), ring)
    mst_view = Observation(**base, field=(CardView(
        1, "spell_trap", "faceup", 55144522, 0),),
        chain=(ChainLinkView(1, 55144522, 1, 8, 0),))
    mst = Action("mst", "chain", 0, {"code": 5318639})
    mst_record = DecisionRecord(mst_view, (mst, pass_action), mst)
    replay = Trajectory("goat", ("a.ydk", "b.ydk"), 42,
                        (ring_record, mst_record), 1, source="policy_evaluation",
                        skill_metadata={"demonstrator_seat": 0,
                                        "policy_inference": "greedy_own_loss_guard_v1"})
    counts = count_mask_delta(replay, {55144522: (2, 0, 0)})
    assert counts == {
        "multi_action_policy_decisions": 2,
        "narrowed_decisions": 2,
        "additional_removed_actions": 2,
        "recorded_choices_removed_by_v5": 2,
        "recorded_one_shot_mst_responses_removed": 1,
        "recorded_idle_own_ring_activations_removed": 1,
    }
