"""Candidate prompts use the recorded policy seat's public information only."""

from dataclasses import replace

import pytest

from goat_ai.actions import Action
from goat_ai.evaluation.replay_review import review_candidates
from goat_ai.observations import CardView, Observation
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
