"""Visible own-card loss summaries must keep their denominator and scope clear."""

from types import SimpleNamespace

from goat_ai.actions import Action
from goat_ai.observations import CardView, Observation
from goat_ai.replay import DecisionRecord
from scripts.audit_policy_replays import (
    own_card_activation_opportunities,
    summarize_visible_own_card_losses,
)


def test_summary_counts_only_policy_review_flags() -> None:
    reports = [
        {"verified_policy_choices": 400,
         "candidates": [{"category": "nobleman_only_own_set_monster"},
                        {"category": "weak_flip_normal_summon_with_set_available"}]},
        {"verified_policy_choices": 600,
         "candidates": [{"category": "heavy_storm_only_own_backrow"},
                        {"category": "breaker_targets_only_own_backrow"}]},
    ]
    result = summarize_visible_own_card_losses(reports)
    assert result["available"] is True
    assert result["verified_policy_choices"] == 1000
    assert result["flagged_instances"] == 3
    assert result["flagged_instances_per_1000_policy_choices"] == 3
    assert result["category_counts"] == {
        "breaker_targets_only_own_backrow": 1,
        "heavy_storm_only_own_backrow": 1,
        "nobleman_only_own_set_monster": 1,
    }
    assert result["flagged_per_activation_opportunity"] == {
        "nobleman_only_own_set_monster": None,
        "heavy_storm_only_own_backrow": None,
    }


def test_summary_does_not_blend_sampled_replays_into_greedy_rate() -> None:
    result = summarize_visible_own_card_losses([
        {"verified_decisions": 100,
         "candidates": [{"category": "nobleman_only_own_set_monster"}]},
    ])
    assert result["available"] is False


def test_activation_opportunities_deduplicate_revisited_priority_prompts() -> None:
    own_set_monster = CardView(0, "monster", "facedown", 123, 0)
    own_set_storm = CardView(0, "spell_trap", "facedown", 19613556, 0)
    own_other_backrow = CardView(0, "spell_trap", "facedown", 456, 1)
    enemy_set_monster = CardView(1, "monster", "facedown", None, 0)
    nobleman = Action("nobleman", "activate", 0, {"code": 504700116})
    storm = Action("storm", "activate", 0,
                   {"code": 19613556, "location": 8, "sequence": 0})

    def decision(cards, turn=1):
        observation = Observation(
            viewer=0, acting_player=0, turn=turn, phase="main1",
            life_points=(8000, 8000), hand=(), field=cards,
            graveyards=((), ()), banished=((), ()), opponent_hand_count=5,
            deck_counts=(35, 35), extra_deck_counts=(0, 0), turn_player=0,
        )
        return DecisionRecord(observation, (nobleman, storm), nobleman)

    trajectory = SimpleNamespace(decisions=(
        decision((own_set_monster, own_set_storm, own_other_backrow)),
        decision((own_set_monster, own_set_storm, own_other_backrow)),
        decision((own_set_monster, own_set_storm, own_other_backrow), turn=2),
        decision((own_set_monster, enemy_set_monster, own_set_storm)),
    ))
    assert own_card_activation_opportunities(trajectory, 0) == {
        "heavy_storm_only_own_backrow": 2,
        "nobleman_only_own_set_monster": 2,
    }
    assert own_card_activation_opportunities(
        SimpleNamespace(decisions=(trajectory.decisions[-1],)), 0) == {}
