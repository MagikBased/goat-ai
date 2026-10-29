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
