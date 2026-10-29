"""Conservative action filters using only the acting player's observation.

These are experimental play preferences, not additions to the rules engine.
The engine remains responsible for determining what is legal.
"""

from collections.abc import Mapping, Sequence

from goat_ai.actions import Action
from goat_ai.observations import CardView, Observation

HEAVY_STORM = 19613556
POT_OF_GREED = 55144522
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
NOBLEMAN_OF_CROSSOUT = 504700116
DUST_TORNADO = 60082869
BOOK_OF_MOON = 14087893
SINISTER_SERPENT = 511000818
THUNDER_DRAGON = 504700054
CHAOS_SORCERER = 9596126
TSUKUYOMI = 34853266
RAIGEKI_BREAK = 4178474
METAMORPHOSIS = 46411259
THOUSAND_EYES_RESTRICT = 504700102
FUSION_TYPE = 0x40
EFFECT_TYPE = 0x20
SHEEP_TOKENS = frozenset((73915052, 73915053, 73915054, 73915055))
FIELD_PERSISTENT_NORMAL_SPELLS = frozenset((72302403, 11961740))


def safe_one_shot_response_indices(observation: Observation,
                                   legal_actions: Sequence[Action],
                                   admissible: Sequence[int],
                                   card_facts: Mapping[int, tuple[int, int, int]],
                                   ) -> tuple[int, ...]:
    """Defer MST when its only opposing target is an activated one-shot card.

    Destruction does not negate a resolving Normal Spell/Trap or Quick-Play
    Spell. Printed Type is used only for the publicly identified chain source;
    the identities of other opposing Set cards are never inspected. Keep the
    action if any other opposing back row could be a useful target.
    """
    indices = tuple(admissible)
    if not observation.chain:
        return indices
    latest = observation.chain[-1]
    own = observation.viewer
    card_type = card_facts.get(latest.card_code, (0, 0, 0))[0]
    if (latest.controller == own or latest.location != 8
            or card_type not in (2, 4, 0x10002)
            or latest.card_code in FIELD_PERSISTENT_NORMAL_SPELLS):
        return indices
    if any(card.controller != own and card.zone == "spell_trap"
           and (card.controller, card.sequence) != (latest.controller, latest.sequence)
           for card in observation.field):
        return indices
    kept = tuple(index for index in indices if not (
        legal_actions[index].kind == "chain"
        and legal_actions[index].parameters.get("code") == MYSTICAL_SPACE_TYPHOON))
    return kept or indices


def safe_own_one_shot_response_indices(observation: Observation,
                                       legal_actions: Sequence[Action],
                                       admissible: Sequence[int],
                                       card_facts: Mapping[int, tuple[int, int, int]],
                                       ) -> tuple[int, ...]:
    """Defer MST when only its own resolving one-shot card can be destroyed.

    The source and MST's Set slot are excluded from other target checks.
    Unknown opposing back row or another friendly card keeps MST available.
    This is an opt-in preference, not an effect-negation rule.
    """
    indices = tuple(admissible)
    if not observation.chain:
        return indices
    source = observation.chain[-1]
    own = observation.viewer
    card_type = card_facts.get(source.card_code, (0, 0, 0))[0]
    if (source.controller != own or source.location != 8
            or card_type not in (2, 4, 0x10002)
            or source.card_code in FIELD_PERSISTENT_NORMAL_SPELLS):
        return indices

    def only_source_target(action: Action) -> bool:
        if (action.kind != "chain"
                or action.parameters.get("code") != MYSTICAL_SPACE_TYPHOON):
            return False
        own_mst_slot = (action.parameters.get("sequence")
                        if action.parameters.get("location") == 8 else None)
        backrow = [card for card in observation.field if card.zone == "spell_trap"]
        return (any(card.controller == own and card.sequence == source.sequence
                    and card.code == source.card_code and card.position == "faceup"
                    for card in backrow)
                and all((card.controller, card.sequence) == (own, source.sequence)
                        or (card.controller == own and card.sequence == own_mst_slot
                            and card.code == MYSTICAL_SPACE_TYPHOON)
                        for card in backrow))

    kept = tuple(index for index in indices
                 if not only_source_target(legal_actions[index]))
    return kept or indices


def safe_chained_own_only_mst_indices(observation: Observation,
                                      legal_actions: Sequence[Action],
                                      admissible: Sequence[int]) -> tuple[int, ...]:
    """Defer an optional MST chain when only friendly back row can be hit.

    This extends the idle own-only MST preference to a response window. It
    uses card zones, not the identities of opposing hidden cards. A forced
    action stays available, and any opposing back row keeps MST available.
    """
    indices = tuple(admissible)
    if not observation.chain:
        return indices
    own = observation.viewer
    if any(card.controller != own and card.zone == "spell_trap"
           for card in observation.field):
        return indices

    def own_only_mst(index: int) -> bool:
        action = legal_actions[index]
        if (action.kind != "chain"
                or action.parameters.get("code") != MYSTICAL_SPACE_TYPHOON):
            return False
        source_slot = (action.parameters.get("sequence")
                       if action.parameters.get("location") == 8 else None)
        return any(card.controller == own and card.zone == "spell_trap"
                   and not (card.sequence == source_slot
                            and card.code == MYSTICAL_SPACE_TYPHOON)
                   for card in observation.field)

    kept = tuple(index for index in indices if not own_only_mst(index))
    return kept or indices


def safe_optional_own_loss_indices(observation: Observation,
                                   legal_actions: Sequence[Action],
                                   admissible: Sequence[int]) -> tuple[int, ...]:
    """Defer a few visible own-only removal activations for an opt-in ablation.

    This is a strategic filter, never a legality ruling. A facedown opposing
    card is counted only by zone and position; its identity is not inspected.
    Keep a legal fallback if every offered action matches the filter.
    """
    indices = tuple(admissible)
    own = observation.viewer
    own_sets = any(c.controller == own and c.zone == "monster"
                   and c.position == "facedown" for c in observation.field)
    enemy_sets = any(c.controller != own and c.zone == "monster"
                     and c.position == "facedown" for c in observation.field)
    own_backrow = any(c.controller == own and c.zone == "spell_trap"
                      for c in observation.field)
    enemy_backrow = any(c.controller != own and c.zone == "spell_trap"
                        for c in observation.field)
    enemy_monsters = any(c.controller != own and c.zone == "monster"
                         for c in observation.field)
    own_faceup_monsters = any(c.controller == own and c.zone == "monster"
                              and c.position == "faceup" for c in observation.field)
    own_monsters = any(c.controller == own and c.zone == "monster"
                       for c in observation.field)

    def own_only(index: int) -> bool:
        action = legal_actions[index]
        if action.kind not in ("activate", "chain"):
            return False
        code = action.parameters.get("code")
        if code == HEAVY_STORM:
            # A Set Storm is the source being spent, not friendly collateral.
            source_slot = (action.parameters.get("sequence")
                           if action.parameters.get("location") == 8 else None)
            return not enemy_backrow and any(
                c.controller == own and c.zone == "spell_trap"
                and not (c.code == HEAVY_STORM and c.sequence == source_slot)
                for c in observation.field)
        if code == TORRENTIAL_TRIBUTE:
            return own_monsters and not enemy_monsters
        if not observation.chain and code == MYSTICAL_SPACE_TYPHOON:
            source_slot = (action.parameters.get("sequence")
                           if action.parameters.get("location") == 8 else None)
            return not enemy_backrow and any(
                c.controller == own and c.zone == "spell_trap"
                and not (c.code == code and c.sequence == source_slot)
                for c in observation.field)
        if not observation.chain and code == RAIGEKI_BREAK:
            source_slot = (action.parameters.get("sequence")
                           if action.parameters.get("location") == 8 else None)
            own_other_backrow = any(
                c.controller == own and c.zone == "spell_trap"
                and not (c.code == code and c.sequence == source_slot)
                for c in observation.field)
            return ((own_monsters or own_other_backrow)
                    and not (enemy_monsters or enemy_backrow))
        if code == NOBLEMAN_OF_CROSSOUT:
            return own_sets and not enemy_sets
        if code == BREAKER_THE_MAGICAL_WARRIOR:
            return own_backrow and not enemy_backrow
        if code == TRIBE_INFECTING_VIRUS:
            return own_faceup_monsters and not any(
                c.controller != own and c.zone == "monster" and c.position == "faceup"
                for c in observation.field)
        if code in (BLACK_LUSTER_SOLDIER, CHAOS_SORCERER) and not enemy_monsters:
            return any(c.controller == own and c.zone == "monster"
                       and c.sequence == action.parameters.get("sequence")
                       and c.code == code and c.owner == own
                       for c in observation.field)
        return False

    kept = tuple(index for index in indices if not own_only(index))
    return kept or indices


def safe_negative_heavy_trade_indices(observation: Observation,
                                      legal_actions: Sequence[Action],
                                      admissible: Sequence[int]) -> tuple[int, ...]:
    """Defer Heavy Storm when visible friendly collateral meets enemy back row.

    This estimates the immediate card trade before a chain can be built. It
    counts a Set Heavy Storm as the spent source, not its own collateral, and
    treats opposing face-down cards only as visible occupied slots. It is an
    experimental preference; a forced legal action remains available.
    """
    indices = tuple(admissible)
    own = observation.viewer
    own_backrow = [card for card in observation.field
                   if card.controller == own and card.zone == "spell_trap"]
    enemy_backrow = sum(card.controller != own and card.zone == "spell_trap"
                        for card in observation.field)

    def negative_trade(index: int) -> bool:
        action = legal_actions[index]
        if (action.kind != "activate"
                or action.parameters.get("code") != HEAVY_STORM):
            return False
        source_is_set = action.parameters.get("location") == 8 and any(
            card.sequence == action.parameters.get("sequence")
            and card.code == HEAVY_STORM for card in own_backrow)
        collateral = len(own_backrow) - int(source_is_set)
        return enemy_backrow <= collateral

    kept = tuple(index for index in indices if not negative_trade(index))
    return kept or indices


def safe_idle_own_ring_indices(observation: Observation,
                               legal_actions: Sequence[Action],
                               admissible: Sequence[int]) -> tuple[int, ...]:
    """Defer an idle own-only Ring activation unless visible damage can win.

    The opponent may still have hidden responses. This narrow experiment only
    applies on our turn with no pending chain; Ring responses remain available.
    """
    indices = tuple(admissible)
    own = observation.viewer
    if observation.turn_player != own or observation.chain:
        return indices
    if any(card.controller != own and card.zone == "monster"
           and card.position == "faceup" for card in observation.field):
        return indices
    own_targets = [card for card in observation.field
                   if card.controller == own and card.zone == "monster"
                   and card.position == "faceup"]
    if not own_targets:
        return indices
    if any(card.attack is None or card.attack >= observation.life_points[1 - own]
           for card in own_targets):
        return indices
    kept = tuple(index for index in indices if not (
        legal_actions[index].kind in ("activate", "chain")
        and legal_actions[index].parameters.get("code") == RING_OF_DESTRUCTION))
    return kept or indices


def safe_ring_target_indices(observation: Observation,
                             legal_actions: Sequence[Action],
                             admissible: Sequence[int]) -> tuple[int, ...]:
    """Prefer a survivable enemy Ring target over spending an own monster.

    An own target that could end the duel remains available. This uses
    only the public chain source, face-up monster ATK, LP, and legal choices.
    """
    indices = tuple(admissible)
    own = observation.viewer
    if (not observation.chain or observation.chain[-1].controller != own
            or observation.chain[-1].card_code != RING_OF_DESTRUCTION):
        return indices
    monsters = {(card.controller, card.sequence): card
                for card in observation.field
                if card.zone == "monster" and card.position == "faceup"}
    enemy_safe = any(
        legal_actions[index].kind == "select_card"
        and (action := legal_actions[index]).parameters.get("controller") != own
        and (target := monsters.get((action.parameters.get("controller"),
                                    action.parameters.get("sequence")))) is not None
        and target.attack is not None and target.attack < observation.life_points[own]
        for index in indices)
    if not enemy_safe:
        return indices

    def spend_own(index: int) -> bool:
        action = legal_actions[index]
        if action.kind != "select_card" or action.parameters.get("controller") != own:
            return False
        target = monsters.get((own, action.parameters.get("sequence")))
        return (target is not None and target.attack is not None
                and target.attack < observation.life_points[1 - own])

    kept = tuple(index for index in indices if not spend_own(index))
    return kept or indices


def safe_position_indices(observation: Observation,
                          legal_actions: Sequence[Action],
                          admissible: Sequence[int], *,
                          empty_field_attack_guard: bool = True,
                          v10_guard: bool = False) -> tuple[int, ...]:
    """Remove position switches with no visible combat upside.

    A defending Sheep Token has no attack power. On an empty opposing field,
    moving a face-up attacker with at least as much ATK as DEF into defense
    only loses its ability to attack and does not improve its battle stat.
    Unknown opposing monsters keep other switches available to the policy.
    """
    indices = tuple(admissible)
    own_monsters = {(card.controller, card.sequence): card
                    for card in observation.field
                    if card.zone == "monster" and card.controller == observation.viewer}
    opponent_monsters = any(card.zone == "monster"
                            and card.controller != observation.viewer
                            for card in observation.field)
    own_defenders = {(card.controller, card.sequence) for card in observation.field
                     if card.zone == "monster" and card.controller == observation.viewer
                     and card.position == "faceup" and card.orientation == "defense"
                     and card.code in SHEEP_TOKENS and card.attack == 0}
    def useful(index: int) -> bool:
        action = legal_actions[index]
        if action.kind != "change_position":
            return True
        slot = (action.parameters.get("controller"),
                action.parameters.get("sequence"))
        if slot in own_defenders:
            return False
        card = own_monsters.get(slot)
        if (v10_guard and card is not None and card.position == "faceup"
                and card.attack is not None and card.defense is not None):
            if card.orientation == "attack" and card.attack >= card.defense:
                return False
            if card.orientation == "defense" and opponent_monsters:
                # Keep the safer stance unless a visible battle can justify
                # exposing this monster. Unknown Set monsters remain uncertain.
                enemies = [enemy for enemy in observation.field
                           if enemy.zone == "monster" and enemy.controller != observation.viewer]
                if (all(enemy.position == "faceup" and enemy.attack is not None
                        for enemy in enemies)
                        and not any(card.attack > (
                            enemy.attack if enemy.orientation == "attack"
                            else (enemy.defense or 0)) for enemy in enemies)):
                    return False
        return not (empty_field_attack_guard and not opponent_monsters
                    and card is not None and card.position == "faceup"
                    and card.orientation == "attack" and card.attack is not None
                    and card.defense is not None and card.attack >= card.defense)

    kept = tuple(index for index in indices if useful(index))
    return kept or indices


def safe_target_indices(observation: Observation,
                        legal_actions: Sequence[Action],
                        admissible: Sequence[int], *,
                        protect_removal_targets: bool = False,
                        prioritize_non_token_removal: bool = False,
                        avoid_resolving_normal_spell_targets: bool = False,
                        card_facts: Mapping[int, tuple[int, int, int]] | None = None,
                        ) -> tuple[int, ...]:
    """Avoid observed own-target losses when an enemy target is offered.

    This opt-in preference applies only at the target prompt. It does not
    decide whether activating the effect was worthwhile in the first place.
    """
    indices = tuple(admissible)
    if not observation.chain or observation.chain[-1].controller != observation.viewer:
        return indices
    source = observation.chain[-1]
    sources = {BLACK_LUSTER_SOLDIER, MYSTICAL_SPACE_TYPHOON}
    if protect_removal_targets:
        sources.update((CHAOS_SORCERER, RAIGEKI_BREAK,
                        BREAKER_THE_MAGICAL_WARRIOR, DUST_TORNADO,
                        NOBLEMAN_OF_CROSSOUT))
    if source.card_code not in sources:
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
    if avoid_resolving_normal_spell_targets and source.card_code == RAIGEKI_BREAK \
            and len(observation.chain) > 1:
        earlier = observation.chain[-2]
        earlier_type = (card_facts or {}).get(earlier.card_code, (None, 0, 0))[0]
        if earlier_type in (2, 4) and earlier.location == 8:
            other = tuple(i for i in kept if not (
                legal_actions[i].parameters.get("controller") == earlier.controller
                and legal_actions[i].parameters.get("location") == earlier.location
                and legal_actions[i].parameters.get("sequence") == earlier.sequence))
            kept = other or kept
    if prioritize_non_token_removal and source.card_code == RAIGEKI_BREAK:
        sheep_slots = {(card.controller, 4, card.sequence) for card in observation.field
                       if card.zone == "monster" and card.code in SHEEP_TOKENS
                       and card.controller != own}
        valuable = tuple(i for i in kept if (
            legal_actions[i].parameters.get("controller"),
            legal_actions[i].parameters.get("location"),
            legal_actions[i].parameters.get("sequence")) not in sheep_slots)
        kept = valuable or kept
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


def known_thunder_copies_in_deck(observation: Observation) -> int | None:
    """Upper bound from the player's own original list and current known zones.

    A transferred card in an opponent's hidden zone is not counted. When the
    initial Main Deck is absent (legacy observations), no inference is made.
    """
    initial = observation.own_main_deck.count(THUNDER_DRAGON)
    if not initial:
        return None
    own = observation.viewer
    outside = sum(card.code == THUNDER_DRAGON for card in (
        *observation.hand, *observation.graveyards[own],
        *observation.banished[own]))
    return max(0, initial - outside)


def useful_metamorphosis_option(observation: Observation,
                                card_facts: Mapping[int, tuple[int, int, int]]) -> bool:
    """Keep Metamorphosis when a visible tribute can make a useful Fusion.

    Unknown printed metadata leaves the option available. This is a
    conservative value filter, never a replacement for the engine's legality.
    """
    if not card_facts or not observation.own_extra_deck:
        return True
    fusions = [card_facts.get(card.code) for card in observation.own_extra_deck]
    own_monsters = [card for card in observation.field
                    if card.zone == "monster" and card.controller == observation.viewer]
    if not own_monsters or any(card.code not in card_facts for card in own_monsters):
        return True
    for monster in own_monsters:
        _, level, printed_attack = card_facts[monster.code]
        attack = monster.attack if monster.attack is not None else printed_attack
        for fusion in fusions:
            if fusion is None:
                return True
            card_type, fusion_level, fusion_attack = fusion
            if not (card_type & FUSION_TYPE) or fusion_level != level:
                continue
            if (card_type & EFFECT_TYPE or fusion_attack > max(0, attack) + 500):
                return True
    return False


def admissible_action_indices(observation: Observation,
                              legal_actions: Sequence[Action],
                              card_races: Mapping[int, int] | None = None,
                              *, tactical_v8_guards: bool = False,
                              tactical_v9_guards: bool = False,
                              tactical_v10_guards: bool = False,
                              tactical_v11_guards: bool = False,
                              tactical_v12_guards: bool = False,
                              tactical_v13_guards: bool = False,
                              tactical_v14_guards: bool = False,
                              card_advantage_guard: bool = False,
                              card_facts: Mapping[int, tuple[int, int, int]] | None = None,
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
    enemy_faceup_monster = any(c.position == "faceup" for c in opponent_monsters)
    enemy_book_target = any(c.position == "faceup" and c.code not in SHEEP_TOKENS
                            for c in opponent_monsters)
    own_monster_threatened = any(
        target.zone == "monster" and target.controller == own
        for link in observation.chain for target in link.targets)
    own_card_targeted = any(
        target.controller == own
        for link in observation.chain for target in link.targets)
    opponent_non_token = [c for c in opponent_monsters
                          if c.code not in SHEEP_TOKENS]
    only_weak_opponent_monsters = bool(opponent_monsters) and all(
        c.position == "faceup" and c.attack is not None and c.attack < 1000
        for c in opponent_non_token)
    latest_chain_type = ((card_facts or {}).get(observation.chain[-1].card_code,
                         (None, 0, 0))[0] if observation.chain else None)
    other_opponent_backrow = any(
        c.zone == "spell_trap" and c.controller != own
        and not (observation.chain and c.controller == observation.chain[-1].controller
                 and observation.chain[-1].location == 8
                 and c.sequence == observation.chain[-1].sequence)
        for c in observation.field)
    known_thunder_left = (known_thunder_copies_in_deck(observation)
                          if tactical_v9_guards else None)
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
    tribe_has_positive_type = any(
        tribe_race_value(observation, race, card_races) > 0
        for race in {visible_monster_race(c, card_races)
                     for c in opponent_monsters}
        if race is not None)
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
        if code == HEAVY_STORM and action.kind == "activate":
            # A Set Storm is the Spell spent, not collateral destroyed by it.
            source_is_set = action.parameters.get("location") == 8 and any(
                card.controller == own and card.zone == "spell_trap"
                and card.sequence == action.parameters.get("sequence")
                and card.code == HEAVY_STORM for card in observation.field)
            collateral = own_backrow - int(source_is_set)
            if (opponent_backrow <= collateral if card_advantage_guard
                    else own_backrow and not opponent_backrow):
                continue
        if (tactical_v9_guards and code == HEAVY_STORM
                and action.kind == "set_spell_trap" and len(observation.hand) < 6
                and not opponent_backrow):
            continue
        if (tactical_v9_guards and code == THUNDER_DRAGON
                and action.kind in ("activate", "chain")
                and known_thunder_left == 0):
            continue
        if (tactical_v9_guards and code == METAMORPHOSIS
                and action.kind in ("activate", "chain")
                and not useful_metamorphosis_option(observation, card_facts or {})):
            continue
        if (tactical_v9_guards and code in (BOOK_OF_MOON, RAIGEKI_BREAK)
                and action.kind == "chain" and can_pass
                and observation.turn_player == own and not observation.chain
                and observation.phase in ("draw", "standby")):
            continue
        if (tactical_v12_guards and code in (BOOK_OF_MOON, RAIGEKI_BREAK)
                and action.kind == "chain" and can_pass
                and not observation.chain and observation.phase in ("draw", "standby")):
            continue
        if (tactical_v12_guards and code == BOOK_OF_MOON
                and action.kind == "chain" and can_pass
                and observation.turn_player != own and not enemy_book_target
                and not own_monster_threatened):
            continue
        if (tactical_v13_guards and code == MYSTICAL_SPACE_TYPHOON
                and action.kind == "chain" and can_pass and observation.chain
                and (latest_chain_type in (2, 4)
                     or observation.chain[-1].card_code == POT_OF_GREED)
                and not other_opponent_backrow):
            continue
        if (tactical_v13_guards and code == BOOK_OF_MOON
                and action.kind == "chain" and can_pass and observation.chain
                and (any(link.card_code == TORRENTIAL_TRIBUTE
                         for link in observation.chain)
                     or (observation.chain[-1].card_code == BOOK_OF_MOON
                         and not enemy_book_target))):
            continue
        if (tactical_v13_guards and code == RAIGEKI_BREAK
                and action.kind == "chain" and can_pass and not opponent_backrow
                and only_weak_opponent_monsters and not own_monster_threatened
                and observation.pending_attack is None
                and (not tactical_v14_guards or observation.phase not in (
                    "battle_start", "battle_step", "damage_step",
                    "damage_calculation"))):
            continue
        if (tactical_v14_guards and code == RAIGEKI_BREAK
                and action.kind == "chain" and can_pass
                and latest_chain_type in (2, 4) and not own_card_targeted):
            continue
        if (tactical_v14_guards and code == RAIGEKI_BREAK
                and action.kind == "chain" and can_pass
                and not observation.chain and observation.turn_player != own
                and observation.phase in ("main1", "main2")
                and not any(c.position == "faceup" and c.code not in SHEEP_TOKENS
                            for c in opponent_monsters)):
            continue
        if (tactical_v14_guards and code == SNATCH_STEAL
                and action.kind in ("activate", "chain")
                and opponent_monsters
                and all(c.code in SHEEP_TOKENS for c in opponent_monsters)
                and not any(c.code == METAMORPHOSIS for c in observation.hand)):
            continue
        if (tactical_v12_guards and code == RAIGEKI_BREAK
                and action.kind == "chain" and can_pass and observation.chain
                and observation.chain[-1].controller == own
                and observation.chain[-1].card_code == BOOK_OF_MOON):
            continue
        if (tactical_v10_guards and code == BOOK_OF_MOON
                and action.kind in ("activate", "chain")
                and observation.turn_player == own and not observation.chain
                and observation.phase in ("main1", "main2")
                and action.parameters.get("location") == 2
                and not any(c.position == "faceup"
                            and c.code == THOUSAND_EYES_RESTRICT
                            for c in opponent_monsters)):
            continue
        if (tactical_v10_guards and code == BOOK_OF_MOON
                and action.kind == "chain" and can_pass and observation.chain
                and observation.chain[-1].controller == own
                and observation.chain[-1].card_code in (
                    CHAOS_SORCERER, BLACK_LUSTER_SOLDIER,
                    BREAKER_THE_MAGICAL_WARRIOR)):
            continue
        if (tactical_v9_guards and code == BREAKER_THE_MAGICAL_WARRIOR
                and action.kind in ("activate", "chain")
                and (can_pass or tactical_v10_guards)
                and not opponent_backrow):
            continue
        if (tactical_v9_guards and code in (BLACK_LUSTER_SOLDIER, CHAOS_SORCERER)
                and action.kind in ("activate", "chain")
                and (can_pass or tactical_v10_guards)
                and not (enemy_faceup_monster or (tactical_v11_guards
                         and code == BLACK_LUSTER_SOLDIER and bool(opponent_monsters)))
                and not any(c.zone == "monster" and c.controller == own
                            and c.sequence == action.parameters.get("sequence")
                            and c.owner is not None and c.owner != own
                            for c in own_monsters)):
            continue
        if (tactical_v13_guards and code == BLACK_LUSTER_SOLDIER
                and action.kind in ("activate", "chain")
                and observation.turn_player == own
                and observation.phase == "main1" and not opponent_backrow
                and opponent_monsters
                and all(c.code in SHEEP_TOKENS for c in opponent_monsters)
                and any(c.code == BLACK_LUSTER_SOLDIER and c.position == "faceup"
                        and c.orientation == "attack" and c.controller == own
                        for c in own_monsters)):
            continue
        if (tactical_v13_guards and code == THUNDER_DRAGON
                and action.kind == "normal_summon"
                and any(c.code == BLACK_LUSTER_SOLDIER and c.controller == own
                        for c in own_monsters)):
            continue
        if (tactical_v9_guards and code == RAIGEKI_BREAK
                and action.kind in ("activate", "chain")
                and (can_pass or tactical_v10_guards)
                and not any(c.controller != own for c in observation.field)):
            continue
        if (code == TRIBE_INFECTING_VIRUS
                and action.kind in ("activate", "chain")
                and have_race_data and (not tribe_has_target
                                        or tactical_v8_guards
                                        and not tribe_has_positive_type)):
            continue
        if (tactical_v8_guards and code == NOBLEMAN_OF_CROSSOUT
                and action.kind in ("activate", "chain")
                and not any(c.position == "facedown" for c in opponent_monsters)):
            continue
        if (tactical_v8_guards and code == DUST_TORNADO
                and action.kind == "chain" and can_pass and observation.chain
                and observation.chain[-1].card_code == BOOK_OF_MOON):
            continue
        if (tactical_v8_guards and code == SINISTER_SERPENT
                and action.kind == "normal_summon"
                and any(other.kind == "normal_summon"
                        and other.parameters.get("code") != SINISTER_SERPENT
                        for other in legal_actions)):
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
