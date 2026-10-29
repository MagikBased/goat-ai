"""Automated visible-rule labels must refer to alternatives actually offered."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from goat_ai.actions import Action
from goat_ai.evaluation.replay_review import ReviewCandidate
from goat_ai.observations import CardView, ChainLinkView, Observation
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


def test_derive_staged_thunder_search_prefers_offered_deck_copy():
    thunder = 504700054
    observation = Observation(
        viewer=0, acting_player=0, turn=2, phase="main1",
        life_points=(8000, 8000), hand=(), field=(), graveyards=((), ()),
        banished=((), ()), opponent_hand_count=4,
        deck_counts=(35, 35), extra_deck_counts=(0, 0),
        chain=(ChainLinkView(1, thunder, 0, 2, 0),))
    empty = Action("empty", "select_cards", 0)
    choose = Action("choose", "select_card", 0,
                    {"code": thunder, "location": 1, "controller": 0})
    other_zone = Action("other", "select_card", 0,
                        {"code": thunder, "location": 2, "controller": 0})
    record = DecisionRecord(observation, (empty, choose, other_zone), empty)
    replay = Trajectory("goat", ("a.ydk", "b.ydk"), 42, (record,), 1)
    candidate = ReviewCandidate(0, "thunder_empty_search_with_copies_available",
                                2, "main1", 0, {"maximum_selectable_copies": 1})
    assert derive(replay, (candidate,)) == (
        [{"decision_index": 0, "preferred_action_indices": [1],
          "disfavored_action_indices": [0]}],
        {"thunder_empty_search_with_copies_available": 1})


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


def test_v12_labels_selected_mst_with_only_own_faceup_spell():
    swords = CardView(0, "spell_trap", "faceup", 72302403, 0)
    view = Observation(
        viewer=0, acting_player=0, turn=1, phase="main1",
        life_points=(8000, 8000), hand=(), field=(swords,),
        graveyards=((), ()), banished=((), ()), opponent_hand_count=5,
        deck_counts=(35, 35), extra_deck_counts=(0, 0), turn_player=0)
    mst = Action("mst", "chain", 0, {"code": 5318639, "location": 2})
    passing = Action("pass", "pass", 0)
    record = DecisionRecord(view, (mst, passing), mst)
    replay = Trajectory("goat", ("a.ydk", "b.ydk"), 42, (record,), 1,
                        source="policy_evaluation",
                        skill_metadata={"demonstrator_seat": 0})
    expected = ([{"decision_index": 0, "preferred_action_indices": [1],
                  "disfavored_action_indices": [0]}],
                {"selected_own_loss": 0, "selected_ring_or_mst_response": 0,
                 "selected_own_faceup_mst": 1})
    facts = {72302403: (2, 0, 0)}
    assert derive(replay, (), rule_set_id=rules.RULE_SET_V12,
                  card_facts=facts) == expected
    own_set = replace(swords, position="facedown")
    assert derive(replace(replay, decisions=(replace(record, observation=replace(
        view, field=(own_set,))),)), (), rule_set_id=rules.RULE_SET_V12,
        card_facts=facts)[0] == []
    enemy_set = CardView(1, "spell_trap", "facedown", None, 0)
    assert derive(replace(replay, decisions=(replace(record, observation=replace(
        view, field=(swords, enemy_set))),)), (), rule_set_id=rules.RULE_SET_V12,
        card_facts=facts)[0] == []


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


def test_v4_ranks_boss_self_banish_below_enemy_target_from_visible_field():
    boss = CardView(0, "monster", "faceup", 504700118, 0, owner=0)
    enemy = CardView(1, "monster", "faceup", 123, 2, owner=1)
    view = Observation(
        viewer=0, acting_player=0, turn=3, phase="main1",
        life_points=(8000, 8000), hand=(), field=(boss, enemy),
        graveyards=((), ()), banished=((), ()), opponent_hand_count=4,
        deck_counts=(35, 35), extra_deck_counts=(0, 0), turn_player=0,
        chain=(ChainLinkView(1, 504700118, 0, 4, 0),))
    own = Action("self", "select_card", 0,
                 {"code": 504700118, "controller": 0, "location": 4,
                  "sequence": 0})
    other = Action("enemy", "select_card", 0,
                   {"controller": 1, "location": 4, "sequence": 2})
    record = DecisionRecord(view, (own, other), own)
    replay = Trajectory("goat", ("a.ydk", "b.ydk"), 42, (record,), 1,
                        source="self_play_rl", skill_metadata={"learner_seat": 0})
    expected = [{"decision_index": 0, "preferred_action_indices": [1],
                 "disfavored_action_indices": [0]}]
    assert derive(replay, (), rule_set_id=rules.RULE_SET_V4)[0] == expected
    safe = replace(replay, decisions=(replace(record, selected_action=other),))
    assert derive(safe, (), rule_set_id=rules.RULE_SET_V4)[0] == expected
    stolen = replace(replay, decisions=(replace(record, observation=replace(
        view, field=(replace(boss, owner=1), enemy))),))
    assert derive(stolen, (), rule_set_id=rules.RULE_SET_V4) == ([], {})


def test_v4_tribe_type_choice_counts_visible_friendly_and_enemy_monsters():
    own = CardView(0, "monster", "faceup", 33184167, 0, race=8)
    enemy = CardView(1, "monster", "faceup", 123, 0, race=16)
    hidden = CardView(1, "monster", "facedown", None, 1)
    view = Observation(
        viewer=0, acting_player=0, turn=3, phase="main1",
        life_points=(8000, 8000), hand=(), field=(own, enemy, hidden),
        graveyards=((), ()), banished=((), ()), opponent_hand_count=4,
        deck_counts=(35, 35), extra_deck_counts=(0, 0), turn_player=0,
        chain=(ChainLinkView(1, 33184167, 0, 4, 0),))
    own_race = Action("own", "announce_race", 0, {"race": 8})
    enemy_race = Action("enemy", "announce_race", 0, {"race": 16})
    empty_race = Action("empty", "announce_race", 0, {"race": 32})
    record = DecisionRecord(view, (own_race, enemy_race, empty_race), own_race)
    replay = Trajectory("goat", ("a.ydk", "b.ydk"), 42, (record,), 1,
                        source="self_play_rl", skill_metadata={"learner_seat": 0})
    expected = [{"decision_index": 0, "preferred_action_indices": [1],
                 "disfavored_action_indices": [0]}]
    assert derive(replay, (), rule_set_id=rules.RULE_SET_V4)[0] == expected
    assert hidden.code is None  # An opponent's Set monster supplies no Type.


def test_v4_recomputed_comparison_rejects_edited_target_group():
    boss = CardView(0, "monster", "faceup", 9596126, 0, owner=0)
    enemy = CardView(1, "monster", "faceup", 123, 1, owner=1)
    observation = Observation(
        viewer=0, acting_player=0, turn=3, phase="main1",
        life_points=(8000, 8000), hand=(), field=(boss, enemy),
        graveyards=((), ()), banished=((), ()), opponent_hand_count=4,
        deck_counts=(35, 35), extra_deck_counts=(0, 0), turn_player=0,
        chain=(ChainLinkView(1, 9596126, 0, 4, 0),))
    own = Action("self", "select_card", 0,
                 {"controller": 0, "location": 4, "sequence": 0})
    other = Action("enemy", "select_card", 0,
                   {"controller": 1, "location": 4, "sequence": 1})
    record = DecisionRecord(observation, (own, other), own)
    replay = Trajectory("goat", ("a.ydk", "b.ydk"), 42, (record,), 1,
                        source="self_play_rl", skill_metadata={"learner_seat": 0})
    valid = SimpleNamespace(rule_set_id=rules.RULE_SET_V4,
                            preferences=(ReviewedPreference(0, (1,), (0,)),))
    rules.validate_automated_preferences(replay, valid, {})
    edited = SimpleNamespace(rule_set_id=rules.RULE_SET_V4,
                             preferences=(ReviewedPreference(0, (0,), (1,)),))
    with pytest.raises(ValueError, match="do not match visible_material_choices_v4"):
        rules.validate_automated_preferences(replay, edited, {})


def test_v5_compares_bad_activation_with_all_other_legal_actions():
    own_set = CardView(0, "monster", "facedown", 31560081, 0, "defense")
    own_spell = CardView(0, "spell_trap", "facedown", 45986603, 1)
    observation = Observation(
        viewer=0, acting_player=0, turn=3, phase="main1",
        life_points=(8000, 8000), hand=(), field=(own_set, own_spell),
        graveyards=((), ()), banished=((), ()), opponent_hand_count=4,
        deck_counts=(35, 35), extra_deck_counts=(0, 0), turn_player=0)
    nobleman = Action("nobleman", "activate", 0, {"code": 504700116})
    storm = Action("storm", "activate", 0, {"code": 19613556})
    set_spell = Action("set", "set_spell_trap", 0, {"code": 14087893})
    battle = Action("battle", "battle_phase", 0)
    record = DecisionRecord(observation, (nobleman, storm, set_spell, battle),
                            nobleman)
    replay = Trajectory("goat", ("a.ydk", "b.ydk"), 42, (record,), 1,
                        source="self_play_rl", skill_metadata={"learner_seat": 0})
    expected = [{"decision_index": 0, "preferred_action_indices": [2, 3],
                 "disfavored_action_indices": [0, 1]}]
    assert derive(replay, (), rule_set_id=rules.RULE_SET_V5)[0] == expected
    chosen_safe = replace(replay, decisions=(replace(record, selected_action=set_spell),))
    assert derive(chosen_safe, (), rule_set_id=rules.RULE_SET_V5)[0] == expected
    valid = SimpleNamespace(rule_set_id=rules.RULE_SET_V5,
                            preferences=(ReviewedPreference(0, (2, 3), (0, 1)),))
    rules.validate_automated_preferences(replay, valid, {})


def test_v6_declines_breaker_effect_before_forced_own_target():
    breaker = CardView(0, "monster", "faceup", 71413901, 0, owner=0)
    own_spell = CardView(0, "spell_trap", "facedown", 19613556, 1)
    observation = Observation(
        viewer=0, acting_player=0, turn=3, phase="main1",
        life_points=(8000, 8000), hand=(), field=(breaker, own_spell),
        graveyards=((), ()), banished=((), ()), opponent_hand_count=4,
        deck_counts=(35, 35), extra_deck_counts=(0, 0), turn_player=0)
    use_counter = Action("breaker", "chain", 0, {"code": 71413901})
    pass_action = Action("pass", "pass", 0)
    record = DecisionRecord(observation, (use_counter, pass_action), use_counter)
    replay = Trajectory("goat", ("a.ydk", "b.ydk"), 42, (record,), 1,
                        source="self_play_rl", skill_metadata={"learner_seat": 0})
    expected = ([{"decision_index": 0, "preferred_action_indices": [1],
                  "disfavored_action_indices": [0]}],
                {"breaker_only_own_backrow": 1})
    assert derive(replay, (), rule_set_id=rules.RULE_SET_V6) == expected
    valid = SimpleNamespace(rule_set_id=rules.RULE_SET_V6,
                            preferences=(ReviewedPreference(0, (1,), (0,)),))
    rules.validate_automated_preferences(replay, valid, {})
    enemy_spell = CardView(1, "spell_trap", "facedown", None, 0)
    with_enemy = replace(replay, decisions=(replace(record, observation=replace(
        observation, field=(*observation.field, enemy_spell))),))
    assert derive(with_enemy, (), rule_set_id=rules.RULE_SET_V6) == ([], {})


def test_v7_distills_visible_guard_activation_and_target_masks():
    own_set = CardView(0, "spell_trap", "facedown", 45986603, 1)
    view = Observation(
        viewer=0, acting_player=0, turn=3, phase="main1",
        life_points=(8000, 8000), hand=(), field=(own_set,),
        graveyards=((), ()), banished=((), ()), opponent_hand_count=4,
        deck_counts=(35, 35), extra_deck_counts=(0, 0), turn_player=0)
    mst = Action("mst", "chain", 0, {"code": 5318639})
    pass_action = Action("pass", "pass", 0)
    activation = DecisionRecord(view, (mst, pass_action), mst)
    own_target = Action("own", "select_card", 0,
                        {"controller": 0, "location": 4, "sequence": 0})
    enemy_target = Action("enemy", "select_card", 0,
                          {"controller": 1, "location": 4, "sequence": 0})
    target_view = replace(view, chain=(ChainLinkView(1, 504700118, 0, 4, 0),))
    target = DecisionRecord(target_view, (own_target, enemy_target), own_target)
    replay = Trajectory("goat", ("a.ydk", "b.ydk"), 42,
                        (activation, target), 1, source="self_play_rl",
                        skill_metadata={"learner_seat": 0})
    expected = ([
        {"decision_index": 0, "preferred_action_indices": [1],
         "disfavored_action_indices": [0]},
        {"decision_index": 1, "preferred_action_indices": [1],
         "disfavored_action_indices": [0]},
    ], {"activation": 1, "target": 1})
    assert derive(replay, (), rule_set_id=rules.RULE_SET_V7) == expected
    valid = SimpleNamespace(rule_set_id=rules.RULE_SET_V7,
                            preferences=(ReviewedPreference(0, (1,), (0,)),
                                         ReviewedPreference(1, (1,), (0,))))
    rules.validate_automated_preferences(replay, valid, {})


def test_v8_labels_only_new_ring_and_one_shot_mst_masks():
    own_monster = CardView(0, "monster", "faceup", 71413901, 0,
                           attack=1600, defense=1000)
    base = Observation(
        viewer=0, acting_player=0, turn=3, phase="main1",
        life_points=(8000, 8000), hand=(), field=(own_monster,),
        graveyards=((), ()), banished=((), ()), opponent_hand_count=4,
        deck_counts=(35, 35), extra_deck_counts=(0, 0), turn_player=0)
    ring = Action("ring", "chain", 0, {"code": 511000824})
    pass_action = Action("pass", "pass", 0)
    ring_record = DecisionRecord(base, (ring, pass_action), ring)
    chain = ChainLinkView(1, 55144522, 1, 8, 0)
    one_shot_view = replace(base, field=(CardView(
        1, "spell_trap", "faceup", 55144522, 0),), chain=(chain,))
    mst = Action("mst", "chain", 0, {"code": 5318639})
    mst_record = DecisionRecord(one_shot_view, (mst, pass_action), mst)
    own_target = Action("own", "select_card", 0,
                        {"controller": 0, "location": 4, "sequence": 0})
    enemy_target = Action("enemy", "select_card", 0,
                          {"controller": 1, "location": 4, "sequence": 0})
    target_view = replace(base, chain=(ChainLinkView(1, 504700118, 0, 4, 0),))
    target_record = DecisionRecord(target_view, (own_target, enemy_target), own_target)
    replay = Trajectory("goat", ("a.ydk", "b.ydk"), 42,
                        (ring_record, mst_record, target_record), 1,
                        source="self_play_rl", skill_metadata={"learner_seat": 0})
    facts = {55144522: (2, 0, 0)}
    expected = ([
        {"decision_index": 0, "preferred_action_indices": [1],
         "disfavored_action_indices": [0]},
        {"decision_index": 1, "preferred_action_indices": [1],
         "disfavored_action_indices": [0]},
    ], {"idle_own_ring": 1, "one_shot_mst": 1})
    assert derive(replay, (), rule_set_id=rules.RULE_SET_V8,
                  card_facts=facts) == expected
    valid = SimpleNamespace(rule_set_id=rules.RULE_SET_V8,
                            preferences=(ReviewedPreference(0, (1,), (0,)),
                                         ReviewedPreference(1, (1,), (0,))))
    rules.validate_automated_preferences(replay, valid, {}, facts)
    with pytest.raises(ValueError, match="do not match"):
        edited = SimpleNamespace(rule_set_id=rules.RULE_SET_V8,
                                 preferences=(ReviewedPreference(0, (0,), (1,)),
                                              ReviewedPreference(1, (1,), (0,))))
        rules.validate_automated_preferences(replay, edited, {}, facts)
    with pytest.raises(ValueError, match="printed card facts"):
        derive(replay, (), rule_set_id=rules.RULE_SET_V8)


def test_v6_declines_only_own_boss_banish_and_off_turn_torrential():
    boss = CardView(0, "monster", "faceup", 504700118, 0, owner=0)
    observation = Observation(
        viewer=0, acting_player=0, turn=3, phase="main1",
        life_points=(8000, 8000), hand=(), field=(boss,),
        graveyards=((), ()), banished=((), ()), opponent_hand_count=4,
        deck_counts=(35, 35), extra_deck_counts=(0, 0), turn_player=0)
    banish = Action("banish", "chain", 0, {"code": 504700118})
    pass_action = Action("pass", "pass", 0)
    record = DecisionRecord(observation, (banish, pass_action), banish)
    replay = Trajectory("goat", ("a.ydk", "b.ydk"), 42, (record,), 1,
                        source="self_play_rl", skill_metadata={"learner_seat": 0})
    assert derive(replay, (), rule_set_id=rules.RULE_SET_V6)[1] == {
        "boss_only_own_monsters": 1}
    stolen = replace(replay, decisions=(replace(record, observation=replace(
        observation, field=(replace(boss, owner=1),))),))
    assert derive(stolen, (), rule_set_id=rules.RULE_SET_V6) == ([], {})
    enemy_turn = replace(observation, turn_player=1)
    torrential = Action("torrential", "chain", 0, {"code": 53582587})
    off_turn = replace(replay, decisions=(DecisionRecord(
        enemy_turn, (torrential, pass_action), torrential),))
    assert derive(off_turn, (), rule_set_id=rules.RULE_SET_V6)[1] == {
        "torrential_only_own_monsters": 1}


def test_v9_covers_activated_boss_ability_without_changing_v6_labels():
    boss = CardView(0, "monster", "faceup", 504700118, 0, owner=0)
    obs = Observation(viewer=0, acting_player=0, turn=3, phase="main1",
                      life_points=(8000, 8000), hand=(), field=(boss,),
                      graveyards=((), ()), banished=((), ()),
                      opponent_hand_count=4, deck_counts=(35, 35),
                      extra_deck_counts=(0, 0), turn_player=0)
    banish = Action("banish", "activate", 0, {"code": 504700118, "sequence": 0})
    pass_action = Action("pass", "pass", 0)
    record = DecisionRecord(obs, (banish, pass_action), banish)
    replay = Trajectory("goat", ("a.ydk", "b.ydk"), 42, (record,), 1,
                        source="self_play_rl", skill_metadata={"learner_seat": 0})
    assert derive(replay, (), rule_set_id=rules.RULE_SET_V6) == ([], {})
    expected = ([{"decision_index": 0, "preferred_action_indices": [1],
                  "disfavored_action_indices": [0]}],
                {"boss_only_own_monsters": 1})
    assert derive(replay, (), rule_set_id=rules.RULE_SET_V9) == expected
    valid = SimpleNamespace(rule_set_id=rules.RULE_SET_V9,
                            preferences=(ReviewedPreference(0, (1,), (0,)),))
    rules.validate_automated_preferences(replay, valid, {})
    enemy = CardView(1, "monster", "faceup", 123, 0, owner=1)
    with_enemy = replace(replay, decisions=(replace(
        record, observation=replace(obs, field=(boss, enemy))),))
    assert derive(with_enemy, (), rule_set_id=rules.RULE_SET_V9) == ([], {})


@pytest.mark.parametrize(("code", "field", "category"), [
    (71413901, (CardView(0, "spell_trap", "facedown", 123, 0),),
     "breaker_only_own_backrow"),
    (33184167, (CardView(0, "monster", "faceup", 123, 0),),
     "tribe_no_visible_enemy"),
])
def test_v9_covers_activated_breaker_and_tribe(code, field, category):
    obs = Observation(viewer=0, acting_player=0, turn=3, phase="main1",
                      life_points=(8000, 8000), hand=(), field=field,
                      graveyards=((), ()), banished=((), ()),
                      opponent_hand_count=4, deck_counts=(35, 35),
                      extra_deck_counts=(0, 0), turn_player=0)
    activate = Action("ability", "activate", 0, {"code": code})
    pass_action = Action("pass", "pass", 0)
    record = DecisionRecord(obs, (activate, pass_action), activate)
    replay = Trajectory("goat", ("a.ydk", "b.ydk"), 42, (record,), 1,
                        source="self_play_rl", skill_metadata={"learner_seat": 0})
    assert derive(replay, (), rule_set_id=rules.RULE_SET_V6) == ([], {})
    assert derive(replay, (), rule_set_id=rules.RULE_SET_V9) == (
        [{"decision_index": 0, "preferred_action_indices": [1],
          "disfavored_action_indices": [0]}], {category: 1})


def test_v10_keeps_only_recorded_own_loss_choices():
    own_set = CardView(0, "monster", "facedown", 123, 0)
    obs = Observation(viewer=0, acting_player=0, turn=3, phase="main1",
                      life_points=(8000, 8000), hand=(), field=(own_set,),
                      graveyards=((), ()), banished=((), ()),
                      opponent_hand_count=4, deck_counts=(35, 35),
                      extra_deck_counts=(0, 0), turn_player=0)
    nobleman = Action("nobleman", "activate", 0, {"code": 504700116})
    battle = Action("battle", "battle_phase", 0)
    bad = DecisionRecord(obs, (nobleman, battle), nobleman)
    safe = DecisionRecord(replace(obs, turn=4), (nobleman, battle), battle)
    replay = Trajectory("goat", ("a.ydk", "b.ydk"), 42, (bad, safe), 1,
                        source="self_play_rl", skill_metadata={"learner_seat": 0})
    assert len(derive(replay, (), rule_set_id=rules.RULE_SET_V9)[0]) == 2
    expected = ([{"decision_index": 0, "preferred_action_indices": [1],
                  "disfavored_action_indices": [0]}],
                {"selected_own_loss": 1})
    assert derive(replay, (), rule_set_id=rules.RULE_SET_V10) == expected
    rules.validate_automated_preferences(
        replay, SimpleNamespace(rule_set_id=rules.RULE_SET_V10,
                                preferences=(ReviewedPreference(0, (1,), (0,)),)), {})


def test_v11_combines_selected_optional_loss_and_ring_response():
    monster = CardView(0, "monster", "faceup", 123, 0,
                       attack=1600, defense=1000)
    own_set = CardView(0, "monster", "facedown", 456, 1)
    obs = Observation(viewer=0, acting_player=0, turn=3, phase="main1",
                      life_points=(8000, 8000), hand=(), field=(monster, own_set),
                      graveyards=((), ()), banished=((), ()),
                      opponent_hand_count=4, deck_counts=(35, 35),
                      extra_deck_counts=(0, 0), turn_player=0)
    ring = Action("ring", "activate", 0, {"code": 511000824})
    nobleman = Action("nobleman", "activate", 0, {"code": 504700116})
    pass_action = Action("pass", "pass", 0)
    records = (DecisionRecord(obs, (ring, pass_action), ring),
               DecisionRecord(replace(obs, turn=4), (nobleman, pass_action), nobleman))
    replay = Trajectory("goat", ("a.ydk", "b.ydk"), 42, records, 1,
                        source="self_play_rl", skill_metadata={"learner_seat": 0})
    with pytest.raises(ValueError, match="printed card facts"):
        derive(replay, (), rule_set_id=rules.RULE_SET_V11)
    expected = ([{"decision_index": 0, "preferred_action_indices": [1],
                  "disfavored_action_indices": [0]},
                 {"decision_index": 1, "preferred_action_indices": [1],
                  "disfavored_action_indices": [0]}],
                {"selected_own_loss": 1, "selected_ring_or_mst_response": 1})
    assert derive(replay, (), rule_set_id=rules.RULE_SET_V11,
                  card_facts={}) == expected
    rules.validate_automated_preferences(
        replay, SimpleNamespace(rule_set_id=rules.RULE_SET_V11,
                                preferences=(ReviewedPreference(0, (1,), (0,)),
                                             ReviewedPreference(1, (1,), (0,)))),
        {}, {})


def test_v13_flags_idle_ring_activation_against_only_sheep_tokens():
    own = CardView(0, "monster", "faceup", 87621407, 1,
                   attack=1400, defense=1400)
    sheep = CardView(1, "monster", "faceup", 73915054, 3,
                     attack=0, defense=0)
    obs = Observation(viewer=0, acting_player=0, turn=3, phase="main1",
                      life_points=(6200, 7200), hand=(), field=(own, sheep),
                      graveyards=((), ()), banished=((), ()),
                      opponent_hand_count=4, deck_counts=(35, 35),
                      extra_deck_counts=(0, 0), turn_player=0)
    ring = Action("ring", "activate", 0, {"code": 511000824})
    battle = Action("battle", "battle_phase", 0)
    end = Action("end", "end_phase", 0)
    record = DecisionRecord(obs, (ring, battle, end), ring)
    replay = Trajectory("goat", ("a.ydk", "b.ydk"), 42, (record,), 1,
                        source="self_play_rl", skill_metadata={"learner_seat": 0})
    expected = ([{"decision_index": 0, "preferred_action_indices": [1, 2],
                  "disfavored_action_indices": [0]}],
                {"selected_own_loss": 0, "selected_ring_or_mst_response": 0,
                 "selected_own_faceup_mst": 0,
                 "selected_idle_ring_token_only": 1})
    assert derive(replay, (), rule_set_id=rules.RULE_SET_V13,
                  card_facts={}) == expected
    rules.validate_automated_preferences(
        replay, SimpleNamespace(rule_set_id=rules.RULE_SET_V13,
                                preferences=(ReviewedPreference(0, (1, 2), (0,)),)),
        {}, {})
    non_token = replace(sheep, code=12345)
    other = replace(replay, decisions=(replace(record, observation=replace(
        obs, field=(own, non_token))),))
    assert derive(other, (), rule_set_id=rules.RULE_SET_V13,
                  card_facts={})[0] == []
