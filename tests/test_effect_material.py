"""Resolved material diagnostic covers monster abilities and card effects."""

import pytest

from goat_ai.actions import Action
from goat_ai.evaluation.effect_material import (
    effect_material_changes,
    material_margin,
    paired_outcome_association,
)
from goat_ai.observations import CardView, ChainLinkView, Observation
from goat_ai.replay import DecisionRecord, Trajectory
from scripts.audit_own_card_risks import own_card_risk_rows
from scripts.audit_review_material import material_review_rows

MONSTER = 100
SPELL = 200
TOKEN = 300
FACTS = {MONSTER: (1, 4, 1600), SPELL: (2, 0, 0),
         TOKEN: (0x4001, 1, 0)}


def view(*, viewer=0, actor=0, hand=1, opponent_hand=1, field=(), chain=()):
    return Observation(viewer=viewer, acting_player=actor, turn=2, phase="main1",
                       life_points=(8000, 8000),
                       hand=tuple(CardView(viewer, "hand", "faceup", MONSTER)
                                  for _ in range(hand)),
                       field=field, graveyards=((), ()), banished=((), ()),
                       opponent_hand_count=opponent_hand, deck_counts=(30, 30),
                       extra_deck_counts=(15, 15), chain=chain, turn_player=0)


def record(observation, kind, code=None, location=None):
    parameters = ({"code": code, "location": location} if code is not None else {})
    action = Action("choice", kind, observation.acting_player, parameters)
    return DecisionRecord(observation, (action,), action)


@pytest.mark.parametrize("action_kind", ("activate", "chain"))
def test_monster_ability_material_is_measured_after_chain_from_either_view(action_kind):
    own = CardView(0, "monster", "faceup", MONSTER, sequence=0)
    enemy = CardView(1, "monster", "faceup", MONSTER, sequence=0)
    pending = (ChainLinkView(1, MONSTER, 0, 4, 0),)
    trajectory = Trajectory("goat", ("a", "b"), 1, (
        record(view(field=(own, enemy)), action_kind, MONSTER, 4),
        record(view(field=(own, enemy), chain=pending), "pass"),
        record(view(viewer=1, actor=1, field=(own,)), "pass"),
    ), winner=None)
    changes = effect_material_changes(trajectory, FACTS)
    assert len(changes) == 1
    assert changes[0]["source_type"] == "monster_ability"
    assert changes[0]["material_delta"] == 1
    assert changes[0]["resolved_before_decision"] == 2
    assert changes[0]["additional_activations"] == 0


def test_spell_effect_counts_card_spent_and_excludes_tokens():
    backrow = tuple(CardView(1, "spell_trap", "facedown", None, sequence=i)
                    for i in range(2))
    token = CardView(0, "monster", "faceup", TOKEN, sequence=0)
    pending = (ChainLinkView(1, SPELL, 0, 2, 0),)
    assert material_margin(view(field=backrow + (token,)), 0, FACTS) == -2
    trajectory = Trajectory("goat", ("a", "b"), 1, (
        record(view(field=backrow + (token,)), "activate", SPELL, 2),
        record(view(hand=0, field=backrow + (token,), chain=pending), "pass"),
        record(view(hand=0, field=(token,)), "pass"),
    ), winner=None)
    changes = effect_material_changes(trajectory, FACTS)
    assert changes[0]["source_type"] == "spell_trap_effect"
    assert changes[0]["material_delta"] == 1


def test_unresolved_activation_is_not_called_a_material_result():
    trajectory = Trajectory("goat", ("a", "b"), 1, (
        record(view(), "activate", MONSTER, 4),
        record(view(), "pass"),
    ), winner=None)
    assert effect_material_changes(trajectory, FACTS) == []


def test_activation_material_closes_at_terminal_observation():
    pending = (ChainLinkView(1, SPELL, 0, 2, 0),)
    trajectory = Trajectory("goat", ("a", "b"), 1, (
        record(view(hand=1), "activate", SPELL, 2),
        record(view(hand=0, chain=pending), "pass"),
    ), winner=0, schema_version=18,
        terminal_observation=view(hand=0, opponent_hand=0, chain=pending))
    change, = effect_material_changes(trajectory, FACTS)
    assert change["resolved_before_decision"] == len(trajectory.decisions)
    assert change["material_delta"] == 0


def test_review_material_distinguishes_resolved_target_prompt_and_open_chain():
    pending = (ChainLinkView(1, SPELL, 0, 2, 0),)
    trajectory = Trajectory("goat", ("a", "b"), 1, (
        record(view(hand=1), "activate", SPELL, 2),
        record(view(hand=0, chain=pending), "pass"),
        record(view(hand=0), "select_card"),
        record(view(hand=0), "activate", SPELL, 2),
        record(view(hand=0, chain=pending), "pass"),
    ), winner=None)
    offered = {index: {"audit_flags": ["review"]} for index in (0, 2, 3)}
    rows = material_review_rows(trajectory, offered, FACTS)
    assert [row["status"] for row in rows] == [
        "resolved", "not_activation", "no_chain_closure"]
    assert [row["material_delta"] for row in rows] == [-1, None, None]
    assert rows[0]["resolved_before_decision"] == 2


def test_paired_outcome_uses_duels_with_both_seats_and_single_activations():
    def effect(source, seat, delta, additional=0):
        return {"source_type": source, "acting_player": seat,
                "material_delta": delta, "additional_activations": additional}

    games = [
        (0, [effect("monster_ability", 0, 2),
             effect("monster_ability", 1, 0),
             effect("monster_ability", 1, 9, additional=1),
             effect("spell_trap_effect", 0, 1)]),
        (1, [effect("monster_ability", 1, 1),
             effect("monster_ability", 0, 0)]),
        (None, [effect("monster_ability", 0, 100),
                effect("monster_ability", 1, -100)]),
    ]
    result = paired_outcome_association(games, bootstrap_samples=100, seed=3)
    assert result["monster_ability"]["paired_games"] == 2
    assert result["monster_ability"]["mean_winner_minus_loser"] == 1.5
    assert result["spell_trap_effect"]["paired_games"] == 0
    assert result["spell_trap_effect"]["bootstrap_95_interval"] is None
    assert result == paired_outcome_association(games, bootstrap_samples=100, seed=3)


def test_own_card_risk_audit_counts_resolved_idle_ring_without_calling_it_value():
    ring = 511000824
    own = CardView(0, "monster", "faceup", MONSTER, sequence=0,
                   attack=1600, defense=1000)
    set_ring = CardView(0, "spell_trap", "facedown", ring, sequence=0)
    activation = Action("ring", "activate", 0,
                        {"code": ring, "location": 8, "sequence": 0})
    wait = Action("wait", "pass", 0, {})
    pending = (ChainLinkView(1, ring, 0, 8, 0),)
    trajectory = Trajectory("goat", ("a", "b"), 1, (
        DecisionRecord(view(hand=0, field=(own, set_ring)),
                       (activation, wait), activation),
        record(view(hand=0, field=(own, set_ring), chain=pending), "pass"),
        record(view(hand=0), "pass"),
    ), winner=None, source="policy_evaluation",
        skill_metadata={"demonstrator_seat": 0})
    rows, counts = own_card_risk_rows(trajectory, FACTS | {ring: (4, 0, 0)})
    assert len(rows) == 1
    assert rows[0]["flags"] == ["idle_own_only_ring"]
    assert rows[0]["material_delta"] == -2
    assert counts["flagged_single_activations_negative_material"] == 1
    assert counts["policy_decisions"] == 3


def test_own_card_risk_audit_flags_ability_self_target_without_material_label():
    bls = 504700118
    own = CardView(0, "monster", "faceup", bls, sequence=0, owner=0)
    enemy = CardView(1, "monster", "faceup", MONSTER, sequence=0, owner=1)
    chain = (ChainLinkView(1, bls, 0, 4, 0),)
    self_target = Action("self", "select_card", 0,
                         {"controller": 0, "location": 4, "sequence": 0})
    enemy_target = Action("enemy", "select_card", 0,
                          {"controller": 1, "location": 4, "sequence": 0})
    trajectory = Trajectory("goat", ("a", "b"), 1, (
        DecisionRecord(view(field=(own, enemy), chain=chain),
                       (self_target, enemy_target), self_target),
    ), winner=None, source="policy_evaluation",
        skill_metadata={"demonstrator_seat": 0})
    rows, counts = own_card_risk_rows(trajectory, FACTS)
    assert rows[0]["flags"] == ["own_removal_target_with_enemy_option"]
    assert rows[0]["material_delta"] is None
    assert counts["flagged_decisions"] == 1
    assert counts["flagged_single_activations_negative_material"] == 0
