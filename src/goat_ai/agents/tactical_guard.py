"""Conservative action filters using only the acting player's observation.

These are experimental play preferences, not additions to the rules engine.
The engine remains responsible for determining what is legal.
"""

from collections.abc import Mapping, Sequence

from goat_ai.actions import Action
from goat_ai.observations import CardView, Observation

HEAVY_STORM = 19613556
SCAPEGOAT = 504700123
TORRENTIAL_TRIBUTE = 53582587
RING_OF_DESTRUCTION = 511000824
TRIBE_INFECTING_VIRUS = 33184167
BREAKER_THE_MAGICAL_WARRIOR = 71413901
ENEMY_CONTROLLER = 98045062
ROYAL_DECREE = 51452091
SAKURETSU_ARMOR = 56120475
BLACK_LUSTER_SOLDIER = 504700118
MYSTICAL_SPACE_TYPHOON = 5318639
SNATCH_STEAL = 45986603
SOLEMN_JUDGMENT = 41420027
SHEEP_TOKENS = frozenset((73915052, 73915053, 73915054, 73915055))


def safe_position_indices(observation: Observation,
                          legal_actions: Sequence[Action],
                          admissible: Sequence[int]) -> tuple[int, ...]:
    """Keep face-up Sheep Tokens in defense when another legal choice exists."""
    indices = tuple(admissible)
    own_defenders = {(card.controller, card.sequence) for card in observation.field
                     if card.zone == "monster" and card.controller == observation.viewer
                     and card.position == "faceup" and card.orientation == "defense"
                     and card.code in SHEEP_TOKENS and card.attack == 0}
    kept = tuple(index for index in indices
                 if not (legal_actions[index].kind == "change_position"
                         and (legal_actions[index].parameters.get("controller"),
                              legal_actions[index].parameters.get("sequence"))
                         in own_defenders))
    return kept or indices


def safe_target_indices(observation: Observation,
                        legal_actions: Sequence[Action],
                        admissible: Sequence[int]) -> tuple[int, ...]:
    """Avoid observed own-target losses when an enemy target is offered.

    This opt-in preference applies only at the target prompt. It does not
    decide whether activating the effect was worthwhile in the first place.
    """
    indices = tuple(admissible)
    if not observation.chain or observation.chain[-1].controller != observation.viewer:
        return indices
    source = observation.chain[-1]
    if source.card_code not in (BLACK_LUSTER_SOLDIER, MYSTICAL_SPACE_TYPHOON):
        return indices
    own = observation.viewer
    if source.card_code == BLACK_LUSTER_SOLDIER and any(
        card.controller == own and card.zone == "monster"
        and card.sequence == source.sequence and card.owner is not None
        and card.owner != own for card in observation.field
    ):
        # Original ownership is public for a face-up monster. A borrowed BLS
        # may be worth banishing before its control-changing effect expires.
        return indices
    if source.card_code == BLACK_LUSTER_SOLDIER and any(
        card.controller == own and card.zone == "spell_trap"
        and card.position == "faceup" and card.code == SNATCH_STEAL
        and card.equipped_to == (own, source.sequence)
        for card in observation.field
    ):
        # A controlled opponent BLS may return when the equip leaves.
        return indices
    has_enemy_target = any(legal_actions[i].kind == "select_card"
                           and legal_actions[i].parameters.get("controller") != own
                           for i in indices)
    if not has_enemy_target:
        return indices
    kept = tuple(i for i in indices if not (
        legal_actions[i].kind == "select_card"
        and legal_actions[i].parameters.get("controller") == own))
    return kept or indices


def visible_monster_race(card: CardView, printed_races: Mapping[int, int]) -> int | None:
    """Prefer the current public Type; older replays have only printed metadata."""
    if card.zone != "monster" or card.position != "faceup":
        return None
    return card.race if card.race is not None else printed_races.get(card.code)


def tribe_race_value(observation: Observation, race: int,
                     card_races: Mapping[int, int]) -> int:
    """Estimate visible monsters removed by a declared race, with ATK as tiebreak."""
    enemy = [c for c in observation.field
             if c.zone == "monster" and c.controller != observation.viewer
             and visible_monster_race(c, card_races) == race]
    own = [c for c in observation.field
           if c.zone == "monster" and c.controller == observation.viewer
           and visible_monster_race(c, card_races) == race]
    return (10000 * len(enemy) - 15000 * len(own)
            + sum(c.attack or 0 for c in enemy) - sum(c.attack or 0 for c in own))


def weak_flip_set_substitute(observation: Observation,
                             legal_actions: Sequence[Action],
                             preferred: Action,
                             weak_flip_attacks: Mapping[int, int],
                             ) -> Action | None:
    """Offer the same low-ATK Flip monster as a Set when no direct lethal is visible."""
    code = preferred.parameters.get("code")
    if preferred.kind != "normal_summon" or code not in weak_flip_attacks:
        return None
    own = observation.viewer
    own_attack = sum(c.attack or 0 for c in observation.field
                     if c.controller == own and c.zone == "monster"
                     and c.position == "faceup" and c.orientation == "attack")
    enemy_monsters = any(c.controller != own and c.zone == "monster"
                         for c in observation.field)
    if (observation.phase == "main1"
            and any(a.kind == "battle_phase" for a in legal_actions)
            and not enemy_monsters
            and observation.life_points[1 - own]
            <= own_attack + weak_flip_attacks[code]):
        return None
    return next((a for a in legal_actions if a.kind == "set_monster"
                 and a.parameters.get("code") == code), None)


def admissible_action_indices(observation: Observation,
                              legal_actions: Sequence[Action],
                              card_races: Mapping[int, int] | None = None,
                              ) -> tuple[int, ...]:
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
    faceup_decree = any(c.zone == "spell_trap" and c.position == "faceup"
                        and c.code == ROYAL_DECREE for c in observation.field)
    own_monsters = [c for c in observation.field
                    if c.zone == "monster" and c.controller == own]
    opponent_monsters = [c for c in observation.field
                         if c.zone == "monster" and c.controller != own]
    can_pass = any(a.kind == "pass" for a in legal_actions)
    card_races = card_races or {}
    have_race_data = bool(card_races) or any(c.race is not None for c in opponent_monsters)
    tribe_prompt = (have_race_data and observation.chain
                    and observation.chain[-1].card_code == TRIBE_INFECTING_VIRUS
                    and observation.chain[-1].controller == own)
    race_actions = [a for a in legal_actions if a.kind == "announce_race"]
    best_race_value = (max(tribe_race_value(observation, a.parameters["race"], card_races)
                           for a in race_actions) if tribe_prompt and race_actions else None)
    tribe_has_target = any(visible_monster_race(c, card_races) is not None
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
                and have_race_data and not tribe_has_target):
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
        if (code == SOLEMN_JUDGMENT and action.kind == "chain" and can_pass
                and observation.chain and observation.chain[-1].card_code == SCAPEGOAT
                and observation.chain[-1].controller != own
                and observation.turn_player != own):
            continue
        if (code == SOLEMN_JUDGMENT and action.kind == "chain" and can_pass
                and observation.pending_summon is not None
                and observation.pending_summon.controller != own
                and observation.pending_summon.code == 511000818):  # Sinister Serpent
            continue
        if (code == TORRENTIAL_TRIBUTE and action.kind == "chain" and can_pass
                and len(opponent_monsters) <= len(own_monsters)):
            continue
        if (code == RING_OF_DESTRUCTION and action.kind == "chain" and can_pass
                and not any(c.attack is not None and c.position == "faceup"
                            and 1400 <= c.attack < observation.life_points[own]
                            for c in opponent_monsters)):
            continue
        if (code == SAKURETSU_ARMOR and action.kind == "chain" and can_pass
                and faceup_decree):
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
