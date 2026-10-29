"""Candidate prompts use the recorded policy seat's public information only."""

from dataclasses import replace

import pytest

from goat_ai.actions import Action
from goat_ai.evaluation.replay_review import (
    compare_parent_greedy_candidates,
    review_candidates,
    sampled_self_play_provenance,
)
from goat_ai.observations import CardView, ChainLinkView, Observation, PendingSummonView
from goat_ai.replay import DecisionRecord, Trajectory
from scripts.shortlist_policy_disagreements import visible_faceup_age


def view(*cards, phase="main1", turn=1, player=0, turn_player=0):
    return Observation(
        viewer=player, acting_player=player, turn=turn, phase=phase,
        life_points=(8000, 8000), hand=(), field=cards,
        graveyards=((), ()), banished=((), ()), opponent_hand_count=5,
        deck_counts=(35, 35), extra_deck_counts=(0, 0),
        turn_player=turn_player,
    )


def record(observation, selected, *other):
    return DecisionRecord(observation, (selected, *other), selected)


def policy(*decisions):
    return Trajectory(
        "tcg-goat-2005-08-17", ("a.ydk", "b.ydk"), 42, decisions, 0,
        source="policy_evaluation",
        skill_metadata={"demonstrator_seat": 0,
                        "policy_checkpoint_sha256": "a" * 64},
    )


def test_visible_faceup_age_review_filter_uses_only_public_field_cards():
    swords = CardView(1, "spell_trap", "faceup", 72302403, 0,
                      faceup_turns=3)
    hidden = CardView(1, "spell_trap", "facedown", None, 1)
    observation = view(swords, hidden, turn=5)
    assert visible_faceup_age(observation, 72302403, 1) == 3
    assert visible_faceup_age(observation, 72302403, 4) is None
    assert visible_faceup_age(observation, 12345, 0) is None
    assert visible_faceup_age(view(hidden, turn=5), 72302403, 0) is None


def test_review_flags_idle_own_only_removal_before_target_prompt():
    own_mst = CardView(0, "spell_trap", "facedown", 5318639, 0)
    own_other = CardView(0, "spell_trap", "facedown", 456, 1)
    own_monster = CardView(0, "monster", "faceup", 123, 0)
    enemy_set = CardView(1, "spell_trap", "facedown", None, 0)
    mst = Action("mst", "chain", 0,
                 {"code": 5318639, "location": 8, "sequence": 0})
    break_card = Action("break", "chain", 0,
                        {"code": 4178474, "location": 2, "sequence": 0})
    wait = Action("pass", "pass", 0)
    replay = policy(
        record(view(own_mst, own_other), mst, wait),
        record(view(own_mst), mst, wait),
        record(view(own_monster), break_card, wait),
        record(view(own_mst, enemy_set), mst, wait),
        record(view(own_monster, enemy_set), break_card, wait),
    )
    flags = {(item.decision_index, item.category)
             for item in review_candidates(replay)}
    assert (0, "mst_idle_only_own_backrow") in flags
    assert (2, "raigeki_break_idle_only_own_field") in flags
    assert not any(index in (1, 3, 4) and category in (
        "mst_idle_only_own_backrow", "raigeki_break_idle_only_own_field")
                   for index, category in flags)


def test_sampled_self_play_provenance_cannot_be_mistaken_for_greedy_choices():
    sampled = replace(
        policy(record(view(), Action("pass", "pass", 0))),
        source="self_play_rl",
        skill_metadata={"learner_seat": 0,
                        "parent_checkpoint_sha256": "a" * 64,
                        "learner_action_selection": "sampled_softmax",
                        "learner_temperature": 2.0},
    )
    provenance = sampled_self_play_provenance(sampled, "a" * 64)
    assert provenance["selection_mode"] == "sampled_softmax"
    assert provenance["selection_temperature"] == 2.0
    assert provenance["choice_verification"] == "not_reproduced_exploratory_sampling"
    assert provenance["verified_policy_choices"] is None
    masked = replace(sampled, skill_metadata={**sampled.skill_metadata,
                                              "selection_progress_mask": 1})
    masked_provenance = sampled_self_play_provenance(masked, "a" * 64)
    assert masked_provenance["selection_mode"] == "sampled_softmax_progress_mask_v1"
    undo = Action("undo", "unselect_card", 0, {"code": 10})
    add = Action("add", "select_card", 0, {"code": 20})
    impossible = replace(masked, decisions=(DecisionRecord(view(), (undo, add), undo),))
    with pytest.raises(ValueError, match="selection progress mask violated"):
        sampled_self_play_provenance(impossible, "a" * 64)
    with pytest.raises(ValueError, match="parent checkpoint"):
        sampled_self_play_provenance(sampled, "b" * 64)
    for key, bad_value in (("learner_seat", True),
                           ("parent_checkpoint_sha256", "unknown"),
                           ("learner_action_selection", "greedy"),
                           ("selection_progress_mask", 2),
                           ("learner_temperature", 0),
                           ("learner_temperature", float("nan"))):
        corrupted = replace(sampled, skill_metadata={**sampled.skill_metadata,
                                                     key: bad_value})
        with pytest.raises(ValueError):
            sampled_self_play_provenance(corrupted)


def test_shortlist_flags_public_waste_and_deduplicates_priority_passes():
    own_set = CardView(0, "spell_trap", "facedown", 53582587, 0)
    enemy_set = CardView(1, "spell_trap", "facedown", None, 0)
    decree = CardView(0, "spell_trap", "faceup", 51452091, 1)
    enemy_monster = CardView(1, "monster", "faceup", 123, 0,
                             "attack", 1800, 1000)
    storm = Action("storm", "activate", 0, {"code": 19613556})
    sak = Action("sak", "chain", 0, {"code": 56120475})
    goat = Action("goat", "chain", 0, {"code": 504700123})
    decline = Action("decline", "pass", 0)
    opponent_action = Action("opp", "pass", 1)
    saved = policy(
        record(view(own_set), storm, Action("end", "end_phase", 0)),
        record(view(own_set, enemy_set), storm),
        record(view(decree, enemy_monster, phase="battle_step", turn=2,
                    turn_player=1), sak, decline),
        record(view(enemy_monster, phase="battle_start", turn=2,
                    turn_player=1), decline, goat),
        record(view(enemy_monster, phase="battle_start", turn=2,
                    turn_player=1), decline, goat),
        record(view(enemy_monster, replace(enemy_monster, sequence=1),
                    phase="end", turn=2,
                    turn_player=1), decline, goat),
        record(view(enemy_monster, phase="end", turn=3,
                    turn_player=None), decline, goat),
        record(view(player=1), opponent_action),
    )
    candidates = review_candidates(saved)
    assert [(c.viewer_frame, c.category) for c in candidates] == [
        (1, "heavy_storm_only_own_backrow"),
        (2, "heavy_storm_negative_visible_trade"),
        (3, "sakuretsu_under_decree"),
        (4, "scapegoat_pass_during_open_attack"),
        (6, "scapegoat_pass_opponent_end"),
    ]
    assert candidates[0].evidence == {"own_other_backrow": 1, "enemy_backrow": 0}
    assert candidates[3].evidence["own_life_points"] == 8000


def test_shortlist_flags_own_monster_removal_as_review_candidates():
    own_monster = CardView(0, "monster", "faceup", 87621407, 0,
                           "attack", 1400, 1000)
    torrential = Action("torrential", "chain", 0, {"code": 53582587})
    ring = Action("ring", "chain", 0, {"code": 511000824})
    decline = Action("decline", "pass", 0)
    saved = policy(record(view(own_monster), torrential, decline),
                   record(view(own_monster), ring, decline))
    assert [c.category for c in review_candidates(saved)] == [
        "torrential_only_own_monsters", "ring_without_visible_enemy_target"]


def test_shortlist_flags_idle_own_ring_but_preserves_visible_lethal_exception():
    own = CardView(0, "monster", "faceup", 49881766, 0,
                   "attack", 1900, 1500)
    ring = Action("ring", "activate", 0, {"code": 511000824})
    summon = Action("summon", "normal_summon", 0, {"code": 71413901})
    idle = record(view(own, turn=3), ring, summon)
    lethal = replace(idle, observation=replace(
        idle.observation, life_points=(8000, 1000)))
    enemy = CardView(1, "monster", "faceup", 31560081, 0,
                     "attack", 1200, 1000)
    with_enemy = replace(idle, observation=replace(
        idle.observation, field=(own, enemy)))
    own_response = replace(idle, observation=replace(
        idle.observation, chain=(ChainLinkView(1, 19613556, 1, 8, 0),)))
    assert [c.category for c in review_candidates(policy(idle))] == [
        "ring_idle_only_own_faceup"]
    assert review_candidates(policy(lethal)) == ()
    assert review_candidates(policy(with_enemy)) == ()
    assert review_candidates(policy(own_response)) == ()


def test_book_on_monster_under_torrential_is_a_review_prompt_only():
    own = CardView(0, "monster", "faceup", 87621407, 0,
                   "attack", 1400, 1000)
    enemy = CardView(1, "monster", "faceup", 71413901, 0,
                     "attack", 1600, 1000)
    torrential = ChainLinkView(1, 53582587, 1, 8, 0)
    book = ChainLinkView(2, 14087893, 0, 8, 0)
    own_target = Action("own", "select_card", 0,
                        {"controller": 0, "location": 4, "sequence": 0,
                         "code": own.code})
    enemy_target = Action("enemy", "select_card", 0,
                          {"controller": 1, "location": 4, "sequence": 0,
                           "code": enemy.code})
    chained = replace(view(own, enemy), chain=(torrential, book))
    no_torrential = replace(chained, chain=(book,))
    saved = policy(record(chained, own_target, enemy_target),
                   record(chained, enemy_target, own_target),
                   record(no_torrential, own_target, enemy_target))
    candidates = review_candidates(saved)
    assert [(candidate.decision_index, candidate.category) for candidate in candidates] == [
        (0, "book_targets_monster_under_torrential"),
        (1, "book_targets_monster_under_torrential")]
    assert candidates[0].evidence == {"target_code": own.code,
                                      "target_controller": 0,
                                      "torrential_chain_links": 1}
    assert candidates[1].evidence == {"target_code": enemy.code,
                                      "target_controller": 1,
                                      "torrential_chain_links": 1}


@pytest.mark.parametrize("removal", [5318639, 4178474])
@pytest.mark.parametrize("target_code, card_type", [
    (55144522, 0x2),              # Pot of Greed: Normal Spell
    (14087893, 0x2 | 0x10000),    # Book of Moon: Quick-Play Spell
    (53582587, 0x4),              # Torrential Tribute: Normal Trap
])
def test_shortlist_flags_removal_of_resolving_one_shot_card(
    removal, target_code, card_type,
):
    target = CardView(1, "spell_trap", "faceup", target_code, 0)
    obs = replace(view(target), chain=(
        ChainLinkView(1, target_code, 1, 8, 0),
        ChainLinkView(2, removal, 0, 8, 1),
    ))
    select = Action("target", "select_card", 0, {
        "controller": 1, "location": 8, "sequence": 0, "code": target_code,
    })
    candidates = review_candidates(policy(record(obs, select)),
                                   card_facts={target_code: (card_type, 0, 0)})
    assert [(item.category, item.evidence) for item in candidates] == [(
        "removal_targets_resolving_one_shot_spell_trap",
        {"removal_code": removal, "target_code": target_code})]


def test_shortlist_does_not_flag_persistent_or_unchained_spell_trap_removal():
    decree = CardView(1, "spell_trap", "faceup", 51452091, 0)
    pot = CardView(1, "spell_trap", "faceup", 55144522, 1)
    select = Action("target", "select_card", 0, {
        "controller": 1, "location": 8, "sequence": 0,
    })
    chained = replace(view(decree, pot), chain=(
        ChainLinkView(1, 51452091, 1, 8, 0),
        ChainLinkView(2, 5318639, 0, 8, 2),
    ))
    unchained = replace(view(pot), chain=(ChainLinkView(1, 5318639, 0, 8, 2),))
    facts = {51452091: (0x4 | 0x20000, 0, 0),
             55144522: (0x2, 0, 0)}
    assert review_candidates(policy(record(chained, select)), card_facts=facts) == ()
    assert review_candidates(policy(record(unchained, select)), card_facts=facts) == ()
    swords = CardView(1, "spell_trap", "faceup", 72302403, 0)
    persistent = replace(view(swords), chain=(
        ChainLinkView(1, 72302403, 1, 8, 0),
        ChainLinkView(2, 5318639, 0, 8, 2),
    ))
    assert review_candidates(policy(record(persistent, select)),
                             card_facts={72302403: (0x2, 0, 0)}) == ()


def test_one_shot_prompt_survives_frozen_parent_greedy_comparison():
    pot = CardView(1, "spell_trap", "faceup", 55144522, 0)
    obs = replace(view(pot), chain=(
        ChainLinkView(1, 55144522, 1, 8, 0),
        ChainLinkView(2, 5318639, 0, 8, 1),
    ))
    target = Action("pot", "select_card", 0, {
        "controller": 1, "location": 8, "sequence": 0,
    })
    sampled = replace(policy(record(obs, target)), source="self_play_rl",
                      skill_metadata={"learner_seat": 0})
    facts = {55144522: (0x2, 0, 0)}
    candidates = review_candidates(sampled, card_facts=facts)

    class SameAgent:
        def select_action(self, _observation, _legal_actions):
            return target

    compared = compare_parent_greedy_candidates(
        sampled, candidates, SameAgent(), card_facts=facts)
    assert compared[0]["parent_greedy_same_category_flagged"] is True


def test_heavy_storm_does_not_count_its_own_set_card_as_collateral():
    storm = Action("storm", "activate", 0,
                   {"code": 19613556, "location": 8, "sequence": 0,
                    "controller": 0})
    own_storm = CardView(0, "spell_trap", "facedown", 19613556, 0)
    own_field_spell = CardView(0, "spell_trap", "faceup", 511002998, 5)
    assert review_candidates(policy(record(view(own_storm), storm)))[0].category == (
        "heavy_storm_negative_visible_trade")
    candidates = review_candidates(policy(record(view(own_storm, own_field_spell),
                                                 storm)))
    assert candidates[0].evidence == {"own_other_backrow": 1,
                                      "enemy_backrow": 0}


def test_shortlist_flags_negative_heavy_trade_and_self_nobleman():
    own_set = CardView(0, "spell_trap", "facedown", 53582587, 0)
    enemy_set = CardView(1, "spell_trap", "facedown", None, 0)
    spy = CardView(0, "monster", "facedown", 504700044, 0)
    storm = Action("storm", "activate", 0, {"code": 19613556})
    nobleman = Action("nobleman", "activate", 0, {"code": 504700116})
    cases = policy(record(view(own_set, enemy_set), storm),
                   record(view(spy), nobleman))
    found = review_candidates(cases)
    assert [(item.viewer_frame, item.category) for item in found] == [
        (1, "heavy_storm_negative_visible_trade"),
        (2, "nobleman_only_own_set_monster"),
    ]
    assert found[0].evidence == {"own_other_backrow": 1, "enemy_backrow": 1}
    assert found[1].evidence == {"own_set_monsters": 1, "enemy_set_monsters": 0}


def test_sampled_review_separates_frozen_parent_greedy_choice():
    spy = CardView(0, "monster", "facedown", 504700044, 0)
    nobleman = Action("nobleman", "activate", 0, {"code": 504700116})
    end = Action("end", "end_phase", 0)
    sampled = replace(policy(record(view(spy), nobleman, end)),
                      source="self_play_rl", skill_metadata={"learner_seat": 0})
    candidates = review_candidates(sampled)
    assert len(candidates) == 1

    class FixedAgent:
        def __init__(self, choice):
            self.choice = choice

        def select_action(self, _observation, _legal_actions):
            return self.choice

    safe = compare_parent_greedy_candidates(sampled, candidates, FixedAgent(end))
    assert safe[0]["sampled_category"] == "nobleman_only_own_set_monster"
    assert safe[0]["parent_greedy_same_action"] is False
    assert safe[0]["parent_greedy_same_category_flagged"] is False
    assert safe[0]["parent_greedy_flagged_categories"] == []

    flagged = compare_parent_greedy_candidates(sampled, candidates,
                                                FixedAgent(nobleman))
    assert flagged[0]["parent_greedy_same_action"] is True
    assert flagged[0]["parent_greedy_same_category_flagged"] is True
    with pytest.raises(ValueError, match="outside the visible legal set"):
        compare_parent_greedy_candidates(
            sampled, candidates, FixedAgent(Action("invalid", "pass", 0)))


def test_shortlist_rejects_non_policy_source_or_missing_seat():
    saved = policy(record(view(), Action("pass", "pass", 0)))
    with pytest.raises(ValueError, match="verified AI replay"):
        review_candidates(replace(saved, source="human_cli"))
    with pytest.raises(ValueError, match="policy seat"):
        review_candidates(replace(saved, skill_metadata={}))
    with pytest.raises(ValueError, match="checkpoint SHA-256"):
        review_candidates(replace(saved, skill_metadata={"demonstrator_seat": 0}))


def test_local_ai_match_needs_explicit_review_seat():
    saved = replace(policy(record(view(), Action("pass", "pass", 0))),
                    source="local_ai_match", skill_metadata={"agents": ["Policy", "Tactical"]})
    with pytest.raises(ValueError, match="review seat"):
        review_candidates(saved)
    assert review_candidates(saved, review_seat=0) == ()


def test_shortlist_accepts_versioned_tactical_teacher_source():
    storm = Action("storm", "activate", 0,
                   {"code": 19613556, "controller": 0, "location": 8,
                    "sequence": 1})
    own_set = CardView(0, "spell_trap", "facedown", 53582587, 0)
    own_storm = CardView(0, "spell_trap", "facedown", 19613556, 1)
    tactical = replace(
        policy(record(view(own_set, own_storm), storm)), source="tactical",
        skill_metadata={"demonstrator_seat": 0, "teacher": "TacticalHeuristicAgent",
                        "teacher_version": 7})
    assert review_candidates(tactical)[0].category == "heavy_storm_only_own_backrow"
    with pytest.raises(ValueError, match="teacher version"):
        review_candidates(replace(tactical, skill_metadata={"demonstrator_seat": 0}))


def test_shortlist_flags_weak_flip_summon_only_when_set_was_legal():
    faith = 31560081
    summon = Action("summon", "normal_summon", 0, {"code": faith})
    set_faith = Action("set", "set_monster", 0, {"code": faith})
    with_set = policy(record(view(), summon, set_faith))
    without_set = policy(record(view(), summon))
    printed = {faith: 300}
    assert review_candidates(with_set) == ()
    found = review_candidates(with_set, weak_flip_attacks=printed)
    assert [(c.category, c.evidence) for c in found] == [
        ("weak_flip_normal_summon_with_set_available",
         {"card_code": faith, "printed_attack": 300})]
    assert review_candidates(without_set, weak_flip_attacks=printed) == ()


def test_shortlist_flags_thunder_order_empty_search_and_flip_metamorphosis():
    thunder, pot, faith, metamorphosis = 504700054, 55144522, 31560081, 46411259
    pot_action = Action("pot", "activate", 0, {"code": pot})
    thunder_action = Action("thunder", "activate", 0, {"code": thunder})
    empty = Action("empty", "select_cards", 0)
    take_two = Action("two", "select_cards", 0,
                      {"cards": [{"code": thunder}, {"code": thunder}]})
    search = replace(view(), chain=(ChainLinkView(1, thunder, 0, 2, 0),))
    tribute = Action("tribute", "select_card", 0, {"code": faith,
                                                     "controller": 0, "location": 4,
                                                     "sequence": 0})
    metamorphosis_view = replace(
        view(CardView(0, "monster", "faceup", faith, 0,
                      "attack", 300, 400)),
        chain=(ChainLinkView(1, metamorphosis, 0, 8, 0),))
    found = review_candidates(policy(
        record(view(), pot_action, thunder_action),
        record(search, empty, take_two),
        record(metamorphosis_view, tribute)),
        weak_flip_attacks={faith: 300})
    assert [(item.viewer_frame, item.category) for item in found] == [
        (1, "pot_before_available_thunder_dragon"),
        (2, "thunder_empty_search_with_copies_available"),
        (3, "metamorphosis_spends_weak_flip_on_empty_enemy_field")]
    assert found[1].evidence == {"maximum_selectable_copies": 2}


def test_shortlist_flags_staged_thunder_search_with_a_deck_copy_offered():
    thunder = 504700054
    search = replace(view(), chain=(ChainLinkView(1, thunder, 0, 2, 0),))
    empty = Action("empty", "select_cards", 0)
    take_one = Action("one", "select_card", 0,
                      {"code": thunder, "location": 1, "controller": 0})
    unrelated = Action("other", "select_card", 0,
                       {"code": thunder, "location": 2, "controller": 0})
    found = review_candidates(policy(record(search, empty, take_one, unrelated)))
    assert [(item.category, item.evidence) for item in found] == [
        ("thunder_empty_search_with_copies_available",
         {"maximum_selectable_copies": 1})]
    assert review_candidates(policy(record(search, empty, unrelated))) == ()


def test_shortlist_flags_unused_activatable_thunder_only_at_own_turn_end():
    thunder = 504700054
    hand_card = CardView(0, "hand", "hidden", thunder)
    available = Action("thunder", "activate", 0, {"code": thunder})
    end = Action("end", "end_phase", 0)
    battle = Action("battle", "battle_phase", 0)
    own = replace(view(), hand=(hand_card,), own_main_deck=(thunder,) * 3)
    found = review_candidates(policy(record(own, end, available)))
    assert [(candidate.viewer_frame, candidate.category) for candidate in found] == [
        (1, "end_turn_with_activatable_thunder_dragon")]
    assert found[0].evidence == {"thunder_in_hand": 1, "initial_thunder_copies": 3}
    assert review_candidates(policy(record(own, battle, available))) == ()
    assert review_candidates(policy(record(replace(own, turn_player=1), end,
                                           available))) == ()
    grave_card = CardView(0, "graveyard", "faceup", thunder)
    banished_card = CardView(0, "banished", "faceup", thunder)
    exhausted = replace(own, graveyards=((grave_card, grave_card), ()))
    assert review_candidates(policy(record(exhausted, end, available))) == ()
    banished = replace(own, graveyards=((grave_card,), ()),
                       banished=((banished_card,), ()))
    assert review_candidates(policy(record(banished, end, available))) == ()
    one_left = replace(own, graveyards=((grave_card,), ()))
    assert [item.category for item in review_candidates(
        policy(record(one_left, end, available)))] == [
            "end_turn_with_activatable_thunder_dragon"]


def test_opponent_review_keeps_bls_and_solemn_findings_separate():
    bls, goat, solemn = 504700118, 504700123, 41420027
    self_target = Action("self", "select_card", 1,
                         {"code": bls, "controller": 1, "location": 4, "sequence": 0})
    enemy_target = Action("enemy", "select_card", 1,
                          {"code": 31560081, "controller": 0,
                           "location": 4, "sequence": 1})
    opponent_view = replace(
        view(CardView(1, "monster", "faceup", bls, 0,
                      "attack", 3000, 2500),
             CardView(0, "monster", "faceup", 31560081, 1,
                      "attack", 300, 400), player=1),
        chain=(ChainLinkView(1, bls, 1, 4, 0),))
    goat_view = replace(opponent_view,
                        chain=(ChainLinkView(1, goat, 0, 8, 0),))
    solemn_action = Action("solemn", "chain", 1, {"code": solemn})
    decline = Action("pass", "pass", 1)
    saved = policy(record(opponent_view, self_target, enemy_target),
                   record(goat_view, solemn_action, decline))
    assert review_candidates(saved) == ()
    findings = review_candidates(saved, review_seat=1)
    assert [(item.viewer_frame, item.category) for item in findings] == [
        (1, "bls_targets_itself_with_enemy_option"),
        (2, "solemn_on_opponent_scapegoat")]
    with pytest.raises(ValueError, match="review seat"):
        review_candidates(saved, review_seat=True)


def test_summon_negation_review_uses_only_public_sinister_serpent_identity():
    serpent = 511000818
    summoned = CardView(1, "monster", "faceup", serpent, 0,
                        "attack", 300, 250)
    response = replace(view(summoned, phase="main1", turn_player=1),
                       pending_summon=PendingSummonView("normal", 1, 0, serpent))
    solemn = Action("solemn", "chain", 0, {"code": 41420027})
    decline = Action("decline", "pass", 0)
    found = review_candidates(policy(record(response, solemn, decline)))
    assert [(item.category, item.evidence) for item in found] == [
        ("solemn_on_opponent_sinister_serpent_summon",
         {"own_life_points": 8000, "summoned_card_code": serpent})]
    assert review_candidates(policy(record(response, decline, solemn))) == ()
    other = replace(response, pending_summon=PendingSummonView("normal", 1, 0,
                                                                69140098),
                    field=(replace(summoned, code=69140098),))
    assert review_candidates(policy(record(other, solemn, decline))) == ()
    assert review_candidates(policy(record(
        replace(response, pending_summon=PendingSummonView("normal", 0, 0,
                                                            serpent),
                field=(replace(summoned, controller=0),)), solemn, decline))) == ()


@pytest.mark.parametrize("source,category", [
    (9596126, "chaos_sorcerer_targets_itself_with_enemy_option"),
    (4178474, "raigeki_break_targets_own_card_with_enemy_option"),
])
def test_shortlist_flags_self_removal_only_with_visible_enemy_option(source, category):
    own = CardView(0, "monster", "faceup", 9596126, 0,
                   "attack", 2300, 2000)
    enemy = CardView(1, "monster", "faceup", 69140098, 1,
                     "attack", 1900, 900)
    target = Action("own", "select_card", 0,
                    {"code": own.code, "controller": 0,
                     "location": 4, "sequence": 0})
    other = Action("enemy", "select_card", 0,
                   {"code": enemy.code, "controller": 1,
                    "location": 4, "sequence": 1})
    obs = replace(view(own, enemy),
                  chain=(ChainLinkView(1, source, 0, 4, 0),))
    found = review_candidates(policy(record(obs, target, other)))
    assert [(item.category, item.evidence) for item in found] == [
        (category, {"source_card_code": source})]
    assert review_candidates(policy(record(obs, other, target))) == ()
    assert review_candidates(policy(record(
        replace(obs, field=(own,)), target))) == ()


def test_shortlist_flags_zero_attack_defender_changed_to_attack():
    sheep = CardView(0, "monster", "faceup", 73915053, 2,
                     "defense", 0, 0)
    change = Action("change", "change_position", 0,
                    {"code": 73915053, "controller": 0,
                     "location": 4, "sequence": 2})
    end = Action("end", "end_phase", 0)
    found = review_candidates(policy(record(view(sheep), change, end)))
    assert [(item.category, item.evidence) for item in found] == [
        ("zero_attack_defender_changed_to_attack",
         {"card_code": 73915053, "current_defense": 0})]
    attacker = replace(sheep, orientation="attack")
    assert review_candidates(policy(record(view(attacker), change, end))) == ()


def test_shortlist_flags_empty_field_attacker_changed_to_weaker_defense():
    attacker = CardView(0, "monster", "faceup", 87621407, 2,
                        "attack", 1400, 1000)
    change = Action("change", "change_position", 0,
                    {"code": attacker.code, "controller": 0,
                     "location": 4, "sequence": 2})
    end = Action("end", "end_phase", 0)
    found = review_candidates(policy(record(view(attacker), change, end)))
    assert [(item.category, item.evidence) for item in found] == [
        ("empty_field_attacker_changed_to_weaker_defense",
         {"card_code": 87621407, "current_attack": 1400,
          "new_defense": 1000})]
    enemy = CardView(1, "monster", "facedown", None, 0, "defense")
    assert review_candidates(policy(record(view(attacker, enemy), change, end))) == ()
    assert review_candidates(policy(record(view(replace(attacker, attack=900)),
                                           change, end))) == ()


def test_shortlist_flags_tribe_type_that_hits_only_own_visible_monsters():
    tribe = 33184167
    own_spellcaster = CardView(0, "monster", "faceup", 101, 0,
                               "attack", 1200, 1000)
    enemy_machine = CardView(1, "monster", "faceup", 202, 0,
                             "attack", 1800, 1000)
    own_hidden = CardView(0, "monster", "facedown", 303, 1,
                          "defense")
    spellcaster, machine = 2, 32
    obs = replace(view(own_spellcaster, own_hidden, enemy_machine),
                  chain=(ChainLinkView(1, tribe, 0, 4, 0),))
    name_spellcaster = Action("spellcaster", "announce_race", 0,
                              {"race": spellcaster})
    name_machine = Action("machine", "announce_race", 0, {"race": machine})
    races = {101: spellcaster, 202: machine, 303: spellcaster}
    bad = policy(record(obs, name_spellcaster, name_machine))
    good = policy(record(obs, name_machine, name_spellcaster))
    assert review_candidates(bad) == ()
    found = review_candidates(bad, card_races=races)
    assert [(c.category, c.evidence) for c in found] == [
        ("tribe_race_hits_only_own_with_enemy_option",
         {"race": spellcaster, "own_hits": 1,
          "visible_enemy_hits": 0, "enemy_race_options": 1})]
    assert review_candidates(good, card_races=races) == ()


def test_tribe_review_uses_current_type_over_printed_metadata():
    tribe = 33184167
    own = CardView(0, "monster", "faceup", 101, 0, "attack",
                   1200, 1000, race=2)
    enemy = CardView(1, "monster", "faceup", 202, 0, "attack",
                     1800, 1000, race=64)
    obs = replace(view(own, enemy), chain=(ChainLinkView(1, tribe, 0, 4, 1),))
    own_type = Action("own", "announce_race", 0, {"race": 2})
    enemy_type = Action("enemy", "announce_race", 0, {"race": 64})
    found = review_candidates(policy(record(obs, own_type, enemy_type)),
                              card_races={101: 64, 202: 2})
    assert [c.category for c in found] == [
        "tribe_race_hits_only_own_with_enemy_option"]


def test_tribe_review_flags_only_own_type_even_without_enemy_type_option():
    tribe = 33184167
    own = CardView(0, "monster", "faceup", 101, 0, "attack",
                   1200, 1000, race=2)
    enemy_set = CardView(1, "monster", "facedown", None, 0, "defense")
    obs = replace(view(own, enemy_set),
                  chain=(ChainLinkView(1, tribe, 0, 4, 1),))
    own_type = Action("own", "announce_race", 0, {"race": 2})
    found = review_candidates(policy(record(obs, own_type)))
    assert [(c.category, c.evidence) for c in found] == [
        ("tribe_race_hits_only_own_no_enemy_option",
         {"race": 2, "own_hits": 1,
          "visible_enemy_hits": 0, "enemy_race_options": 0})]


def test_shortlist_flags_tribe_activation_before_forced_type_choice():
    tribe = 33184167
    own_monster = CardView(0, "monster", "faceup", tribe, 0,
                           "attack", 1600, 1000)
    enemy_hidden = CardView(1, "monster", "facedown", None, 0, "defense")
    chain_tribe = Action("tribe", "chain", 0, {"code": tribe})
    decline = Action("decline", "pass", 0)
    own_race = Action("own_race", "announce_race", 0, {"race": 64})
    activation = record(view(own_monster, enemy_hidden), chain_tribe, decline)
    prompt = record(replace(view(own_monster, enemy_hidden),
                            chain=(ChainLinkView(1, tribe, 0, 4, 0),)), own_race)
    found = review_candidates(policy(activation, prompt, activation),
                              card_races={tribe: 64})
    assert [(c.viewer_frame, c.category) for c in found] == [
        (1, "tribe_activation_without_visible_enemy"),
        (2, "tribe_race_hits_only_own_no_enemy_option"),
        (3, "tribe_activation_without_visible_enemy")]


def test_shortlist_flags_bls_self_target_and_mst_own_target():
    bls = 504700118
    mst = 5318639
    own_bls = CardView(0, "monster", "faceup", bls, 0,
                       "attack", 3000, 2500)
    opposing_set = CardView(1, "monster", "facedown", None, 0, "defense")
    own_set = CardView(0, "spell_trap", "facedown", 41420027, 2)
    opposing_backrow = CardView(1, "spell_trap", "facedown", None, 1)
    bls_view = replace(
        view(own_bls, opposing_set),
        chain=(ChainLinkView(1, bls, 0, 4, 0),))
    mst_view = replace(
        view(own_set, opposing_backrow),
        chain=(ChainLinkView(1, mst, 0, 8, 0),))
    self_banish = Action("self", "select_card", 0,
                         {"code": bls, "controller": 0,
                          "location": 4, "sequence": 0})
    enemy_monster = Action("enemy", "select_card", 0,
                           {"controller": 1, "location": 4, "sequence": 0})
    own_spell = Action("own", "select_card", 0,
                       {"code": 41420027, "controller": 0,
                        "location": 8, "sequence": 2})
    enemy_spell = Action("opponent", "select_card", 0,
                         {"controller": 1, "location": 8, "sequence": 1})
    candidates = review_candidates(policy(
        record(bls_view, self_banish, enemy_monster),
        record(mst_view, own_spell, enemy_spell),
        record(bls_view, enemy_monster, self_banish),
        record(mst_view, enemy_spell, own_spell),
    ))
    assert [(c.viewer_frame, c.category) for c in candidates] == [
        (1, "bls_targets_itself_with_enemy_option"),
        (2, "mst_targets_own_card_with_enemy_option"),
    ]


def test_ring_review_flags_own_target_only_with_safe_enemy_option():
    ring = 511000824
    own = CardView(0, "monster", "faceup", 101, 0, "attack",
                   1500, 1000)
    enemy = CardView(1, "monster", "faceup", 202, 1, "attack",
                     1800, 1000)
    obs = replace(view(own, enemy),
                  chain=(ChainLinkView(1, ring, 0, 8, 2),))
    own_target = Action("own", "select_card", 0,
                        {"code": 101, "controller": 0,
                         "location": 4, "sequence": 0})
    enemy_target = Action("enemy", "select_card", 0,
                          {"code": 202, "controller": 1,
                           "location": 4, "sequence": 1})
    saved = policy(record(obs, own_target, enemy_target),
                   record(obs, enemy_target, own_target))
    found = review_candidates(saved)
    assert [(c.viewer_frame, c.category, c.evidence) for c in found] == [
        (1, "ring_targets_own_with_safe_enemy_option",
         {"safe_enemy_targets": 1})]
    lethal = replace(obs, life_points=(1800, 8000))
    assert not review_candidates(policy(record(lethal, own_target, enemy_target)))


def test_selfplay_shortlist_uses_learner_seat_and_flags_breaker_target():
    breaker = 71413901
    own_set = CardView(1, "spell_trap", "facedown", 64697231, 2)
    opposing_set = CardView(0, "spell_trap", "facedown", None, 3)
    obs = replace(view(own_set, opposing_set, player=1),
                  chain=(ChainLinkView(1, breaker, 1, 4, 0),))
    own_target = Action("own", "select_card", 1,
                        {"code": 64697231, "controller": 1,
                         "location": 8, "sequence": 2})
    enemy_target = Action("enemy", "select_card", 1,
                          {"controller": 0, "location": 8, "sequence": 3})
    saved = replace(policy(record(obs, own_target, enemy_target)),
                    source="self_play_rl",
                    skill_metadata={"learner_seat": 1, "demonstrator_seat": 0})
    assert [(c.viewer_frame, c.category) for c in review_candidates(saved)] == [
        (1, "breaker_targets_own_card_with_enemy_option")]


def test_breaker_own_only_backrow_prompt_uses_visible_target_and_field():
    breaker = 71413901
    own_set = CardView(0, "spell_trap", "facedown", 64697231, 2)
    obs = replace(view(own_set), chain=(ChainLinkView(1, breaker, 0, 4, 0),))
    own_target = Action("own", "select_card", 0,
                        {"code": 64697231, "controller": 0,
                         "location": 8, "sequence": 2})
    saved = policy(record(obs, own_target))
    found = review_candidates(saved)
    assert [(c.viewer_frame, c.category, c.evidence) for c in found] == [
        (1, "breaker_targets_only_own_backrow",
         {"own_backrow": 1, "enemy_backrow": 0})]
    no_field_target = replace(obs, field=())
    assert not review_candidates(policy(record(no_field_target, own_target)))
    with_enemy = replace(obs, field=(own_set, CardView(
        1, "spell_trap", "facedown", None, 3)))
    assert not review_candidates(policy(record(with_enemy, own_target)))


def test_review_flags_optional_own_only_ability_before_target_prompt():
    breaker = 71413901
    bls = 504700118
    own_set = CardView(0, "spell_trap", "facedown", 64697231, 2)
    own_breaker = CardView(0, "monster", "faceup", breaker, 0,
                           "attack", 1900, 1000, owner=0)
    own_bls = CardView(0, "monster", "faceup", bls, 1,
                       "attack", 3000, 2500, owner=0)
    enemy_set = CardView(1, "spell_trap", "facedown", None, 0)
    enemy_monster = CardView(1, "monster", "facedown", None, 0)
    breaker_action = Action("breaker", "chain", 0,
                            {"code": breaker, "sequence": 0})
    boss_action = Action("bls", "chain", 0,
                         {"code": bls, "sequence": 1})
    wait = Action("wait", "pass", 0)
    saved = policy(
        record(view(own_breaker, own_set), breaker_action, wait),
        record(view(own_bls), boss_action, wait),
        record(view(own_breaker, own_set, enemy_set), breaker_action, wait),
        record(view(own_bls, enemy_monster), boss_action, wait),
        record(view(CardView(0, "monster", "faceup", bls, 1,
                             "attack", 3000, 2500, owner=1)), boss_action, wait),
    )
    assert [(item.decision_index, item.category) for item in review_candidates(saved)] == [
        (0, "breaker_activates_with_only_own_backrow"),
        (1, "owned_chaos_boss_activates_without_enemy_monster"),
    ]


def test_selfplay_shortlist_requires_learner_seat():
    saved = replace(policy(record(view(), Action("pass", "pass", 0))),
                    source="self_play_rl", skill_metadata={"demonstrator_seat": 0})
    with pytest.raises(ValueError, match="learner seat"):
        review_candidates(saved)
