"""Automated visible-rule labels must refer to alternatives actually offered."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from goat_ai.actions import Action
from goat_ai.evaluation.replay_review import ReviewCandidate
from goat_ai.observations import CardView, Observation
from goat_ai.replay import DecisionRecord, Trajectory
from goat_ai.replay.preferences import ReviewedPreference
from scripts import derive_visible_rule_preferences as rules

derive = rules.derive


def test_derive_self_target_preference_uses_only_enemy_legal_choices():
    view = Observation(
        viewer=0, acting_player=0, turn=2, phase="main1",
        life_points=(8000, 8000), hand=(), field=(), graveyards=((), ()),
        banished=((), ()), opponent_hand_count=4,
        deck_counts=(35, 35), extra_deck_counts=(0, 0),
    )
    own = Action("own", "select_card", 0, {"location": 4, "controller": 0})
    enemy_a = Action("enemy-a", "select_card", 0,
                     {"location": 4, "controller": 1})
    enemy_b = Action("enemy-b", "select_card", 0,
                     {"location": 4, "controller": 1})
    hand = Action("hand", "select_card", 0, {"location": 2, "controller": 1})
    record = DecisionRecord(view, (own, enemy_a, enemy_b, hand), own)
    replay = Trajectory("goat", ("a.ydk", "b.ydk"), 42, (record,), 1)
    candidate = ReviewCandidate(0, "chaos_sorcerer_targets_itself_with_enemy_option",
                                2, "main1", 0, {"source_card_code": 9596126})
    preferences, counts = derive(replay, (candidate,))
    assert preferences == [{"decision_index": 0,
                            "preferred_action_indices": [1, 2],
                            "disfavored_action_indices": [0]}]
    assert counts == {"chaos_sorcerer_targets_itself_with_enemy_option": 1}


def test_derive_skips_review_flags_without_a_safe_alternative():
    view = Observation(
        viewer=0, acting_player=0, turn=2, phase="main1",
        life_points=(8000, 8000), hand=(), field=(), graveyards=((), ()),
        banished=((), ()), opponent_hand_count=4,
        deck_counts=(35, 35), extra_deck_counts=(0, 0),
    )
    own = Action("own", "select_card", 0, {"location": 4, "controller": 0})
    record = DecisionRecord(view, (own,), own)
    replay = Trajectory("goat", ("a.ydk", "b.ydk"), 42, (record,), 1)
    candidate = ReviewCandidate(0, "chaos_sorcerer_targets_itself_with_enemy_option",
                                2, "main1", 0, {})
    assert derive(replay, (candidate,)) == ([], {})


def test_automated_labels_must_match_recomputed_visible_rule(monkeypatch):
    view = Observation(
        viewer=0, acting_player=0, turn=2, phase="main1",
        life_points=(8000, 8000), hand=(), field=(), graveyards=((), ()),
        banished=((), ()), opponent_hand_count=4,
        deck_counts=(35, 35), extra_deck_counts=(0, 0),
    )
    own = Action("own", "select_card", 0, {"location": 4, "controller": 0})
    enemy = Action("enemy", "select_card", 0, {"location": 4, "controller": 1})
    hand = Action("hand", "select_card", 0, {"location": 2, "controller": 1})
    record = DecisionRecord(view, (own, enemy, hand), own)
    replay = Trajectory("goat", ("a.ydk", "b.ydk"), 42, (record,), 1)
    candidate = ReviewCandidate(0, "chaos_sorcerer_targets_itself_with_enemy_option",
                                2, "main1", 0, {})
    monkeypatch.setattr(rules, "review_candidates", lambda *args, **kwargs: (candidate,))
    valid = SimpleNamespace(preferences=(ReviewedPreference(0, (1,), (0,)),))
    rules.validate_automated_preferences(replay, valid, {})
    edited = SimpleNamespace(preferences=(ReviewedPreference(0, (2,), (0,)),))
    with pytest.raises(ValueError, match="do not match visible_audit_v1"):
        rules.validate_automated_preferences(replay, edited, {})


def test_v2_nobleman_preference_uses_offered_phase_transition():
    observation = Observation(
        viewer=0, acting_player=0, turn=3, phase="main1",
        life_points=(8000, 8000), hand=(), field=(), graveyards=((), ()),
        banished=((), ()), opponent_hand_count=4,
        deck_counts=(35, 35), extra_deck_counts=(0, 0))
    nobleman = Action("nobleman", "activate", 0, {"code": 504700116})
    battle = Action("battle", "battle_phase", 0, {})
    end = Action("end", "end_phase", 0, {})
    record = DecisionRecord(observation, (nobleman, battle, end), nobleman)
    replay = Trajectory("goat", ("a.ydk", "b.ydk"), 42, (record,), 1)
    candidate = ReviewCandidate(0, "nobleman_only_own_set_monster",
                                3, "main1", 0, {})
    assert derive(replay, (candidate,)) == ([], {})
    preferences, counts = derive(replay, (candidate,), rule_set_id=rules.RULE_SET_V2)
    assert preferences == [{"decision_index": 0,
                            "preferred_action_indices": [1],
                            "disfavored_action_indices": [0]}]
    assert counts == {"nobleman_only_own_set_monster": 1}


def test_v2_raigeki_break_preference_excludes_own_and_nonfield_choices():
    observation = Observation(
        viewer=1, acting_player=1, turn=4, phase="main1",
        life_points=(8000, 8000), hand=(), field=(), graveyards=((), ()),
        banished=((), ()), opponent_hand_count=4,
        deck_counts=(35, 35), extra_deck_counts=(0, 0))
    own = Action("own", "select_card", 1, {"controller": 1, "location": 8})
    enemy_monster = Action("monster", "select_card", 1,
                           {"controller": 0, "location": 4})
    enemy_spell = Action("spell", "select_card", 1,
                         {"controller": 0, "location": 8})
    enemy_hand = Action("hand", "select_card", 1,
                        {"controller": 0, "location": 2})
    record = DecisionRecord(observation,
                            (own, enemy_monster, enemy_spell, enemy_hand), own)
    replay = Trajectory("goat", ("a.ydk", "b.ydk"), 42, (record,), 1)
    candidate = ReviewCandidate(0, "raigeki_break_targets_own_card_with_enemy_option",
                                4, "main1", 1, {})
    preferences, _ = derive(replay, (candidate,), rule_set_id=rules.RULE_SET_V2)
    assert preferences == [{"decision_index": 0,
                            "preferred_action_indices": [1, 2],
                            "disfavored_action_indices": [0]}]


def test_v3_resource_pairs_use_visible_legal_options_and_recorded_safe_choice():
    own_set = CardView(0, "monster", "facedown", 31560081, 0, "defense")
    own_spell = CardView(0, "spell_trap", "facedown", 45986603, 1)
    enemy_spell = CardView(1, "spell_trap", "facedown", None, 0)
    observation = Observation(
        viewer=0, acting_player=0, turn=3, phase="main1",
        life_points=(8000, 8000), hand=(), field=(own_set, own_spell),
        graveyards=((), ()), banished=((), ()), opponent_hand_count=4,
        deck_counts=(35, 35), extra_deck_counts=(0, 0), turn_player=0)
    nobleman = Action("nobleman", "activate", 0, {"code": 504700116})
    storm = Action("storm", "activate", 0, {"code": 19613556})
    set_spell = Action("set", "set_spell_trap", 0, {"code": 14087893})
    battle = Action("battle", "battle_phase", 0)
    legal = (nobleman, storm, set_spell, battle)
    safe = DecisionRecord(observation, legal, set_spell)
    bad = DecisionRecord(observation, legal, nobleman)
    replay = Trajectory("goat", ("a.ydk", "b.ydk"), 42, (safe, bad, safe), 1,
                        source="self_play_rl", skill_metadata={"learner_seat": 0})
    preferences, counts = derive(replay, (), rule_set_id=rules.RULE_SET_V3)
    assert preferences == [
        {"decision_index": 0, "preferred_action_indices": [2],
         "disfavored_action_indices": [0, 1]},
        {"decision_index": 1, "preferred_action_indices": [3],
         "disfavored_action_indices": [0, 1]},
    ]
    assert counts == {"nobleman_only_own_set_monster": 2,
                      "heavy_storm_negative_visible_trade": 2}
    # Even a public opponent backrow identity cannot affect a count rule.
    visible_enemy_a = replace(enemy_spell, position="faceup", code=12345)
    visible_enemy_b = replace(enemy_spell, position="faceup", code=54321)
    with_enemy = replace(replay, decisions=(replace(safe, observation=replace(
        observation, field=(*observation.field, visible_enemy_a))),))
    with_visible_enemy = replace(with_enemy, decisions=(replace(safe, observation=replace(
        observation, field=(*observation.field, visible_enemy_b))),))
    assert derive(with_enemy, (), rule_set_id=rules.RULE_SET_V3) == derive(
        with_visible_enemy, (), rule_set_id=rules.RULE_SET_V3)
    # One opposing Set card makes Storm an even trade when no own backrow exists.
    even = replace(safe, observation=replace(
        observation, field=(own_set, enemy_spell)))
    only_nobleman, _ = derive(replace(replay, decisions=(even,)), (),
                             rule_set_id=rules.RULE_SET_V3)
    assert only_nobleman[0]["disfavored_action_indices"] == [0]


def test_v3_set_heavy_storm_does_not_count_itself_as_collateral():
    source = CardView(0, "spell_trap", "facedown", 19613556, 0)
    enemy = CardView(1, "spell_trap", "facedown", None, 0)
    observation = Observation(
        viewer=0, acting_player=0, turn=3, phase="main2",
        life_points=(8000, 8000), hand=(), field=(source, enemy),
        graveyards=((), ()), banished=((), ()), opponent_hand_count=4,
        deck_counts=(35, 35), extra_deck_counts=(0, 0), turn_player=0)
    storm = Action("storm", "activate", 0,
                   {"code": 19613556, "location": 8, "sequence": 0})
    end = Action("end", "end_phase", 0)
    record = DecisionRecord(observation, (storm, end), storm)
    replay = Trajectory("goat", ("a.ydk", "b.ydk"), 42, (record,), 1,
                        source="self_play_rl", skill_metadata={"learner_seat": 0})
    assert derive(replay, (), rule_set_id=rules.RULE_SET_V3) == ([], {})
    losing = replace(record, observation=replace(observation, field=(source,)))
    preferences, _ = derive(replace(replay, decisions=(losing,)), (),
                            rule_set_id=rules.RULE_SET_V3)
    assert preferences[0]["preferred_action_indices"] == [1]


def test_v3_automated_comparison_rejects_edited_action_group():
    own_set = CardView(0, "monster", "facedown", 31560081, 0, "defense")
    observation = Observation(
        viewer=0, acting_player=0, turn=3, phase="main1",
        life_points=(8000, 8000), hand=(), field=(own_set,),
        graveyards=((), ()), banished=((), ()), opponent_hand_count=4,
        deck_counts=(35, 35), extra_deck_counts=(0, 0), turn_player=0)
    nobleman = Action("nobleman", "activate", 0, {"code": 504700116})
    battle = Action("battle", "battle_phase", 0)
    record = DecisionRecord(observation, (nobleman, battle), battle)
    replay = Trajectory("goat", ("a.ydk", "b.ydk"), 42, (record,), 1,
                        source="self_play_rl", skill_metadata={"learner_seat": 0})
    valid = SimpleNamespace(
        rule_set_id=rules.RULE_SET_V3,
        preferences=(ReviewedPreference(0, (1,), (0,)),))
    rules.validate_automated_preferences(replay, valid, {})
    edited = SimpleNamespace(
        rule_set_id=rules.RULE_SET_V3,
        preferences=(ReviewedPreference(0, (0,), (1,)),))
    with pytest.raises(ValueError, match="do not match visible_resource_v3"):
        rules.validate_automated_preferences(replay, edited, {})
