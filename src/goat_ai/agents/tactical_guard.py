"""Conservative action filters using only the acting player's observation.

These are experimental play preferences, not additions to the rules engine.
The engine remains responsible for determining what is legal.
"""

from collections.abc import Mapping, Sequence

from goat_ai.actions import Action
from goat_ai.observations import Observation

HEAVY_STORM = 19613556
SCAPEGOAT = 504700123
TORRENTIAL_TRIBUTE = 53582587
RING_OF_DESTRUCTION = 511000824
TRIBE_INFECTING_VIRUS = 33184167
BREAKER_THE_MAGICAL_WARRIOR = 71413901
ENEMY_CONTROLLER = 98045062


def tribe_race_value(observation: Observation, race: int,
                     card_races: Mapping[int, int]) -> int:
    """Estimate visible monsters removed by a declared race, with ATK as tiebreak."""
    enemy = [c for c in observation.field
             if c.zone == "monster" and c.controller != observation.viewer
             and c.position == "faceup" and c.code is not None
             and card_races.get(c.code) == race]
    own = [c for c in observation.field
           if c.zone == "monster" and c.controller == observation.viewer
           and c.position == "faceup" and c.code is not None
           and card_races.get(c.code) == race]
    return (10000 * len(enemy) - 15000 * len(own)
            + sum(c.attack or 0 for c in enemy) - sum(c.attack or 0 for c in own))


def admissible_action_indices(observation: Observation,
                              legal_actions: Sequence[Action],
                              card_races: Mapping[int, int] | None = None) -> tuple[int, ...]:
    """Defer clearly wasteful actions while preserving an engine-legal choice.

    Scapegoat is normally held for the opponent's End Phase. Their Battle
    Phase or a chain threatening a Set copy can justify using it sooner.
    Older trajectories without a turn owner retain the broader timing rule.
    """
    own = observation.viewer
    own_backrow = sum(c.zone == "spell_trap" and c.controller == own
                      for c in observation.field)
    opponent_backrow = sum(c.zone == "spell_trap" and c.controller != own
                           for c in observation.field)
    own_monsters = [c for c in observation.field
                    if c.zone == "monster" and c.controller == own]
    opponent_monsters = [c for c in observation.field
                         if c.zone == "monster" and c.controller != own]
    can_pass = any(a.kind == "pass" for a in legal_actions)
    card_races = card_races or {}
    tribe_prompt = (card_races and observation.chain
                    and observation.chain[-1].card_code == TRIBE_INFECTING_VIRUS
                    and observation.chain[-1].controller == own)
    race_actions = [a for a in legal_actions if a.kind == "announce_race"]
    best_race_value = (max(tribe_race_value(observation, a.parameters["race"], card_races)
                           for a in race_actions) if tribe_prompt and race_actions else None)
    tribe_has_target = any(c.position == "faceup" and c.code in card_races
                           for c in opponent_monsters)
    ring_target_prompt = (observation.chain
                          and observation.chain[-1].card_code == RING_OF_DESTRUCTION
                          and observation.chain[-1].controller == own
                          and any(a.kind == "select_card" for a in legal_actions))
    breaker_target_prompt = (observation.chain
                             and observation.chain[-1].card_code == BREAKER_THE_MAGICAL_WARRIOR
                             and observation.chain[-1].controller == own)
    breaker_has_opponent_target = (breaker_target_prompt and any(
        a.kind == "select_card" and a.parameters.get("location") == 8
        and a.parameters.get("controller") != own for a in legal_actions))
    safe_opponent_ring_targets = {
        (c.controller, c.sequence) for c in opponent_monsters
        if c.position == "faceup" and c.attack is not None
        and c.attack < observation.life_points[own]
    }
    goat_slots = {(c.controller, c.sequence) for c in observation.field
                  if c.controller == own and c.zone == "spell_trap"
                  and c.code == SCAPEGOAT}
    goat_in_danger = any(
        link.card_code == HEAVY_STORM
        or any(target.zone == "spell_trap"
               and (target.controller, target.sequence) in goat_slots
               for target in link.targets)
        for link in observation.chain)
    goat_timing = (observation.phase in (
        "battle_start", "battle_step", "battle", "damage_step",
        "damage_calculation", "end")
        and (observation.turn_player is None or observation.turn_player != own))
    kept = []
    for index, action in enumerate(legal_actions):
        code = action.parameters.get("code")
        if (code == HEAVY_STORM and action.kind == "activate"
                and own_backrow and not opponent_backrow):
            continue
        if (code == TRIBE_INFECTING_VIRUS
                and action.kind in ("activate", "chain")
                and card_races and not tribe_has_target):
            continue
        if (best_race_value is not None and action.kind == "announce_race"
                and tribe_race_value(observation, action.parameters["race"], card_races)
                < best_race_value):
            continue
        if (code == SCAPEGOAT and action.kind in ("activate", "chain")
                and not goat_in_danger
                and not goat_timing):
            continue
        if (code == ENEMY_CONTROLLER and action.kind in ("activate", "chain")
                and can_pass and not observation.chain
                and observation.phase in ("draw", "standby")):
            continue
        if (code == TORRENTIAL_TRIBUTE and action.kind == "chain" and can_pass
                and len(opponent_monsters) <= len(own_monsters)):
            continue
        if (code == RING_OF_DESTRUCTION and action.kind == "chain" and can_pass
                and not any(c.attack is not None and c.position == "faceup"
                            and 1400 <= c.attack < observation.life_points[own]
                            for c in opponent_monsters)):
            continue
        if (ring_target_prompt and safe_opponent_ring_targets
                and action.kind == "select_card"
                and (action.parameters.get("controller"),
                     action.parameters.get("sequence")) not in safe_opponent_ring_targets):
            continue
        if (breaker_has_opponent_target and action.kind == "select_card"
                and action.parameters.get("location") == 8
                and action.parameters.get("controller") == own):
            continue
        kept.append(index)
    return tuple(kept) if kept else tuple(range(len(legal_actions)))
