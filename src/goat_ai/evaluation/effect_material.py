"""Describe observed material changes after resolved, player-visible effects.

This is a replay diagnostic. A chain may include an opponent response or a
follow-up trigger, so its material change is not a counterfactual action value.
"""

from collections.abc import Mapping
from random import Random
from statistics import mean

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
        last_endpoint = len(decisions) + int(trajectory.terminal_observation is not None)
        for end_index in range(index + 1, min(last_endpoint,
                                                index + max_resolution_decisions + 1)):
            endpoint = (decisions[end_index].observation
                        if end_index < len(decisions)
                        else trajectory.terminal_observation)
            if endpoint.turn != record.observation.turn:
                break
            saw_chain |= bool(endpoint.chain)
            # The native terminal snapshot can retain the last public chain
            # link after lethal resolution, although no further response can
            # occur. Treat terminal as the final measurement boundary.
            terminal_endpoint = end_index == len(decisions)
            if saw_chain and (not endpoint.chain or terminal_endpoint):
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


def paired_outcome_association(
    games: list[tuple[int | None, list[dict]]], *, bootstrap_samples: int = 10_000,
    seed: int = 0,
) -> dict[str, dict]:
    """Compare winners' and losers' observed deltas within each duel.

    Only single selected activations with a decision after chain closure are
    included. This descriptive association does not establish that an effect
    caused a win or estimate the value of an alternative legal action.
    """
    if bootstrap_samples < 1:
        raise ValueError("bootstrap_samples must be positive")
    result = {}
    for source in ("monster_ability", "spell_trap_effect"):
        paired_differences = []
        for winner, effects in games:
            if winner not in (0, 1):
                continue
            winner_deltas = [effect["material_delta"] for effect in effects
                             if effect["source_type"] == source
                             and effect["additional_activations"] == 0
                             and effect["acting_player"] == winner]
            loser_deltas = [effect["material_delta"] for effect in effects
                            if effect["source_type"] == source
                            and effect["additional_activations"] == 0
                            and effect["acting_player"] == 1 - winner]
            if winner_deltas and loser_deltas:
                paired_differences.append(mean(winner_deltas) - mean(loser_deltas))
        if not paired_differences:
            result[source] = {"paired_games": 0, "mean_winner_minus_loser": None,
                              "bootstrap_95_interval": None}
            continue
        rng = Random(seed)
        estimates = sorted(mean(rng.choices(paired_differences,
                                            k=len(paired_differences)))
                           for _ in range(bootstrap_samples))
        lower = int(0.025 * bootstrap_samples)
        upper = int(0.975 * bootstrap_samples) - 1
        result[source] = {
            "paired_games": len(paired_differences),
            "mean_winner_minus_loser": mean(paired_differences),
            "bootstrap_95_interval": [estimates[lower], estimates[upper]],
        }
    return result
