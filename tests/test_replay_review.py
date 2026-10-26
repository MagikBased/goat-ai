"""Candidate prompts use the recorded policy seat's public information only."""

from dataclasses import replace

import pytest

from goat_ai.actions import Action
from goat_ai.evaluation.replay_review import review_candidates
from goat_ai.observations import CardView, ChainLinkView, Observation
from goat_ai.replay import DecisionRecord, Trajectory


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
        (3, "sakuretsu_under_decree"),
        (4, "scapegoat_pass_during_open_attack"),
        (6, "scapegoat_pass_opponent_end"),
    ]
    assert candidates[0].evidence == {"own_other_backrow": 1, "enemy_backrow": 0}
    assert candidates[2].evidence["own_life_points"] == 8000


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


def test_heavy_storm_does_not_count_its_own_set_card_as_collateral():
    storm = Action("storm", "activate", 0,
                   {"code": 19613556, "location": 8, "sequence": 0,
                    "controller": 0})
    own_storm = CardView(0, "spell_trap", "facedown", 19613556, 0)
    own_field_spell = CardView(0, "spell_trap", "faceup", 511002998, 5)
    assert not review_candidates(policy(record(view(own_storm), storm)))
    candidates = review_candidates(policy(record(view(own_storm, own_field_spell),
                                                 storm)))
    assert candidates[0].evidence == {"own_other_backrow": 1,
                                      "enemy_backrow": 0}


def test_shortlist_rejects_non_policy_source_or_missing_seat():
    saved = policy(record(view(), Action("pass", "pass", 0)))
    with pytest.raises(ValueError, match="policy_evaluation"):
        review_candidates(replace(saved, source="human_cli"))
    with pytest.raises(ValueError, match="policy seat"):
        review_candidates(replace(saved, skill_metadata={}))
    with pytest.raises(ValueError, match="checkpoint SHA-256"):
        review_candidates(replace(saved, skill_metadata={"demonstrator_seat": 0}))


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


def test_selfplay_shortlist_requires_learner_seat():
    saved = replace(policy(record(view(), Action("pass", "pass", 0))),
                    source="self_play_rl", skill_metadata={"demonstrator_seat": 0})
    with pytest.raises(ValueError, match="learner seat"):
        review_candidates(saved)
