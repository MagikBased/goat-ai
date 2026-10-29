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
         "verified_multi_action_policy_choices": 200,
         "candidates": [{"category": "nobleman_only_own_set_monster"},
                        {"category": "ring_targets_own_with_safe_enemy_option"},
                        {"category": "weak_flip_normal_summon_with_set_available"}]},
        {"verified_policy_choices": 600,
         "verified_multi_action_policy_choices": 300,
         "candidates": [{"category": "heavy_storm_only_own_backrow"},
                        {"category": "heavy_storm_negative_visible_trade"},
                        {"category": "breaker_targets_only_own_backrow"}]},
    ]
    result = summarize_visible_own_card_losses(reports)
    assert result["available"] is True
    assert result["verified_policy_choices"] == 1000
    assert result["verified_multi_action_policy_choices"] == 500
    assert result["flagged_instances"] == 4
    assert result["flagged_instances_per_1000_policy_choices"] == 4
    assert result["flagged_instances_per_1000_multi_action_choices"] == 8
    assert result["category_counts"] == {
        "heavy_storm_only_own_backrow": 1,
        "heavy_storm_negative_visible_trade": 1,
        "nobleman_only_own_set_monster": 1,
        "ring_targets_own_with_safe_enemy_option": 1,
    }
    assert result["flagged_per_activation_opportunity"] == {
        "nobleman_only_own_set_monster": None,
        "heavy_storm_only_own_backrow": None,
        "mst_idle_only_own_backrow": None,
        "raigeki_break_idle_only_own_field": None,
        "ring_idle_only_own_faceup": None,
        "breaker_activates_with_only_own_backrow": None,
        "owned_chaos_boss_activates_without_enemy_monster": None,
    }


def test_summary_does_not_blend_sampled_replays_into_greedy_rate() -> None:
    result = summarize_visible_own_card_losses([
        {"verified_decisions": 100,
         "candidates": [{"category": "nobleman_only_own_set_monster"}]},
    ])
    assert result["available"] is False


def test_summary_omits_multi_action_rate_for_legacy_or_mixed_reports() -> None:
    result = summarize_visible_own_card_losses([
        {"verified_policy_choices": 4,
         "verified_multi_action_policy_choices": 2,
         "candidates": [{"category": "nobleman_only_own_set_monster"}]},
        {"verified_policy_choices": 6,
         "candidates": []},
    ])
    assert result["verified_policy_choices"] == 10
    assert result["flagged_instances_per_1000_policy_choices"] == 100
    assert result["verified_multi_action_policy_choices"] is None
    assert result["flagged_instances_per_1000_multi_action_choices"] is None


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


def test_idle_own_only_removal_opportunity_excludes_its_set_source() -> None:
    own_mst = CardView(0, "spell_trap", "facedown", 5318639, 0)
    own_other = CardView(0, "spell_trap", "facedown", 456, 1)
    own_monster = CardView(0, "monster", "faceup", 123, 0)
    enemy_set = CardView(1, "spell_trap", "facedown", None, 0)
    mst = Action("mst", "chain", 0,
                 {"code": 5318639, "location": 8, "sequence": 0})
    break_card = Action("break", "chain", 0,
                        {"code": 4178474, "location": 2, "sequence": 0})
    decline = Action("pass", "pass", 0)

    def decision(cards):
        obs = Observation(viewer=0, acting_player=0, turn=2, phase="main1",
                          life_points=(8000, 8000), hand=(), field=cards,
                          graveyards=((), ()), banished=((), ()),
                          opponent_hand_count=5, deck_counts=(35, 35),
                          extra_deck_counts=(0, 0), turn_player=0)
        return DecisionRecord(obs, (mst, break_card, decline), mst)

    trajectory = SimpleNamespace(decisions=(
        decision((own_mst, own_other, own_monster)),
        decision((own_mst, own_other, own_monster)),
        decision((own_mst, enemy_set, own_monster)),
    ))
    assert own_card_activation_opportunities(trajectory, 0) == {
        "mst_idle_only_own_backrow": 1,
        "raigeki_break_idle_only_own_field": 1,
    }


def test_idle_own_ring_opportunity_uses_visible_nonlethal_condition() -> None:
    own = CardView(0, "monster", "faceup", 123, 0, "attack", 1900, 1000)
    enemy = CardView(1, "monster", "faceup", 456, 0, "attack", 1200, 1000)
    ring = Action("ring", "activate", 0, {"code": 511000824})
    pass_action = Action("pass", "pass", 0)

    def decision(cards, opponent_lp=8000, turn=1):
        obs = Observation(viewer=0, acting_player=0, turn=turn, phase="main1",
                          life_points=(8000, opponent_lp), hand=(), field=cards,
                          graveyards=((), ()), banished=((), ()),
                          opponent_hand_count=5, deck_counts=(35, 35),
                          extra_deck_counts=(0, 0), turn_player=0)
        return DecisionRecord(obs, (ring, pass_action), pass_action)

    trajectory = SimpleNamespace(decisions=(
        decision((own,)), decision((own,)),
        decision((own,), opponent_lp=1000), decision((own, enemy)),
        decision((own,), turn=2),
    ))
    assert own_card_activation_opportunities(trajectory, 0) == {
        "ring_idle_only_own_faceup": 2,
    }


def test_own_only_ability_opportunities_count_upstream_prompt() -> None:
    breaker = 71413901
    bls = 504700118
    own_set = CardView(0, "spell_trap", "facedown", 123, 0)
    own_breaker = CardView(0, "monster", "faceup", breaker, 0, owner=0)
    own_bls = CardView(0, "monster", "faceup", bls, 1, owner=0)
    enemy_set = CardView(1, "spell_trap", "facedown", None, 0)
    enemy_monster = CardView(1, "monster", "facedown", None, 0)
    breaker_action = Action("breaker", "chain", 0,
                            {"code": breaker, "sequence": 0})
    boss_action = Action("boss", "chain", 0,
                         {"code": bls, "sequence": 1})
    wait = Action("wait", "pass", 0)

    def decision(cards):
        obs = Observation(viewer=0, acting_player=0, turn=1, phase="main1",
                          life_points=(8000, 8000), hand=(), field=cards,
                          graveyards=((), ()), banished=((), ()),
                          opponent_hand_count=5, deck_counts=(35, 35),
                          extra_deck_counts=(0, 0), turn_player=0)
        return DecisionRecord(obs, (breaker_action, boss_action, wait), wait)

    trajectory = SimpleNamespace(decisions=(
        decision((own_breaker, own_bls, own_set)),
        decision((own_breaker, own_bls, own_set)),
        decision((own_breaker, own_bls, own_set, enemy_set, enemy_monster)),
    ))
    assert own_card_activation_opportunities(trajectory, 0) == {
        "breaker_activates_with_only_own_backrow": 1,
        "owned_chaos_boss_activates_without_enemy_monster": 1,
    }
