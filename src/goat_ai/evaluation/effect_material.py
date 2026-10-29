"""Describe observed material changes after resolved, player-visible effects.

This is a replay diagnostic. A chain may include an opponent response or a
follow-up trigger, so its material change is not a counterfactual action value.
"""

from collections.abc import Mapping

from goat_ai.observations import Observation
from goat_ai.replay import Trajectory

TYPE_MONSTER = 0x1
TYPE_TOKEN = 0x4000
LOCATIONS = {1: "deck", 2: "hand", 4: "monster_zone",
             8: "spell_trap_zone", 16: "graveyard", 32: "banished",
             64: "extra_deck"}


def material_margin(observation: Observation, seat: int,
                    card_facts: Mapping[int, tuple[int, int, int]]) -> int:
    """Count controlled non-token field cards and hand sizes from a legal view."""
    if seat not in (0, 1):
        raise ValueError("seat must be 0 or 1")
    own_hand = (len(observation.hand) if observation.viewer == seat
                else observation.opponent_hand_count)
    other_hand = (observation.opponent_hand_count if observation.viewer == seat
                  else len(observation.hand))
    own_field = 0
    other_field = 0
    for card in observation.field:
        # Tokens cannot be Set; an unknown face-down identity is a real card.
        card_type = card_facts.get(card.code, (0, 0, 0))[0]
        if card_type & TYPE_TOKEN:
            continue
        if card.controller == seat:
            own_field += 1
        else:
            other_field += 1
    return own_hand + own_field - other_hand - other_field


def effect_material_changes(trajectory: Trajectory,
                            card_facts: Mapping[int, tuple[int, int, int]],
                            *, max_resolution_decisions: int = 64) -> list[dict]:
    """Measure selected Spell/Trap and monster activations through chain closure.

    Only the selected action is observed. Responses and automatic triggers may
    affect the measured delta; no alternative play is simulated or labeled.
    """
    if max_resolution_decisions < 1:
        raise ValueError("resolution window must be positive")
    results = []
    decisions = trajectory.decisions
    for index, record in enumerate(decisions):
        action = record.selected_action
        if action.kind not in ("activate", "chain"):
            continue
        code = action.parameters.get("code")
        if type(code) is not int:
            continue
        facts = card_facts.get(code)
        if facts is None:
            continue
        location = action.parameters.get("location")
        if location not in LOCATIONS:
            continue
        seat = record.observation.acting_player
        before = material_margin(record.observation, seat, card_facts)
        saw_chain = bool(record.observation.chain)
        for end_index in range(index + 1, min(len(decisions),
                                                index + max_resolution_decisions + 1)):
            endpoint = decisions[end_index].observation
            if endpoint.turn != record.observation.turn:
                break
            saw_chain |= bool(endpoint.chain)
            if saw_chain and not endpoint.chain:
                after = material_margin(endpoint, seat, card_facts)
                results.append({
                    "decision_index": index,
                    "resolved_before_decision": end_index,
                    "acting_player": seat,
                    "card_code": code,
                    "action_kind": action.kind,
                    "source_location": LOCATIONS[location],
                    "source_type": ("monster_ability" if facts[0] & TYPE_MONSTER
                                    else "spell_trap_effect"),
                    "additional_activations": sum(
                        later.selected_action.kind in ("activate", "chain")
                        for later in decisions[index + 1:end_index]),
                    "material_before": before,
                    "material_after": after,
                    "material_delta": after - before,
                })
                break
    return results
