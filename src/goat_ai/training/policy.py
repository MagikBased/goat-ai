"""Visible-state, action-conditioned policy for variable legal-action sets."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from functools import cached_property, lru_cache
from math import cos, log1p, sin, sqrt
from pathlib import Path

import torch
from torch import Tensor, nn
from torch.nn.utils.rnn import pack_padded_sequence

from goat_ai.actions import Action
from goat_ai.agents.card_metadata import FLIP_MONSTER_TYPE, load_card_properties
from goat_ai.agents.tactical_guard import (
    admissible_action_indices,
    safe_idle_own_ring_indices,
    safe_one_shot_response_indices,
    safe_optional_own_loss_indices,
    safe_position_indices,
    safe_target_indices,
    weak_flip_set_substitute,
)
from goat_ai.engine.decks import read_goat_whitelist
from goat_ai.observations import Observation

ZONES = ("hand", "monster", "spell_trap", "graveyard", "banished", "extra", "chain")
POSITIONS = ("hidden", "facedown", "faceup")
ZONE_IDS = {zone: index + 1 for index, zone in enumerate(ZONES)}
POSITION_IDS = {position: index + 1 for index, position in enumerate(POSITIONS)}
PHASES = ("draw", "standby", "main1", "battle_start", "battle_step", "damage_step",
          "damage_calculation", "battle", "main2", "end")
ACTION_KINDS = (
    "activate", "announce_race", "attack", "battle_phase", "cancel", "chain",
    "change_position", "end_phase", "finish_selection", "flip_summon", "main2",
    "no", "normal_summon", "pass", "phase_transition", "place", "select_card",
    "select_cards", "select_option", "select_position", "set", "set_monster",
    "set_spell_trap", "shuffle_hand", "special_summon", "tribute", "tribute_cards",
    "unselect_card", "yes",
)
ZONE_ACTION_KINDS = ("disable_zone", "disable_zones", "place_zones")
ANNOUNCE_ACTION_KINDS = ("announce_attribute", "announce_number", "announce_card")
SORT_ACTION_KINDS = ("sort_cards",)
COUNTER_ACTION_KINDS = ("select_counters",)
POLICY_INFERENCE_VERSION = 6  # unfinished card selection cannot toggle while adding is legal
POLICY_FEATURE_VERSION = 10  # later versions are opt-in representation experiments
# Version 16 branches from v12 so its combat relation can be tested without
# the separate v13-v15 equip, chain-target, and occupancy experiments.
# Version 17 adds attacker-to-target combat stats using schema-v22 context.
# Version 18 adds an explicit public chain-source/candidate-card relation.
# Version 19 adds the public turn player, distinct from the actor in response windows.
# Version 20 represents announced monster Types as exact mask bits. Dividing
# small Type masks by 2**32 made common choices indistinguishable to float32.
# Version 21 relates an announced Type to current public face-up monster Types.
# Version 22 adds printed Flip/ATK metadata and public board-resource context
# for the reviewed Faith, Heavy Storm, and Ring choices. It is opt-in.
# Version 23 binds a position-change action to that monster's visible battle
# stats and orientation, with only publicly visible opposing battle stats.
# Version 24 adds a visible, before-chain card-trade estimate for Heavy Storm
# and Nobleman of Crossout activations. It cannot predict chain responses.
# Version 25 adds an opt-in, zero-initialized learned correction for that
# estimate. With only this head trainable, all other action logits stay frozen.
# Version 26 branches from v23 and adds separate own/opponent visible-card
# pools. The residual is zero-initialized for exact v23 checkpoint behavior.
# Version 27 branches from v23 and lets each legal action attend to visible
# cards before scoring. Its output is zero-initialized for exact v23 behavior.
# Version 28 branches from v23 and encodes the amount removed from each
# selected field card in a counter-allocation action.
# Version 29 adds public face-up field age to v28's card inputs.
# Version 30 gives select_option choices their public ordinal. Adjacent native
# prompt IDs can collapse to the same float32 after the legacy scaling.
# Version 31 represents announced card codes with exact binary digits and
# marks a match to a publicly known opponent hand card. Unknown names remain
# distinguishable without exposing the opponent's hidden hand.
EQUIP_FEATURE_VERSIONS = (13, 14, 15)
CHAIN_TARGET_FEATURE_VERSIONS = (14, 15)
SPELL_TYPE = 0x2  # TYPE_SPELL in pinned ocgcore constant.lua
HEAVY_STORM = 19613556
NOBLEMAN_OF_CROSSOUT = 504700116


@lru_cache(maxsize=256)
def _race_mask_bits(race: int) -> tuple[float, ...]:
    """Reuse the exact float features for repeated public race choices."""
    return tuple(float(bool(race & (1 << bit))) for bit in range(64))


@dataclass(frozen=True)
class CardVocabulary:
    """Index 0 is hidden/absent; index 1 is an unknown visible card."""

    codes: tuple[int, ...]
    card_properties: tuple[tuple[int, int, int], ...] = ()  # code, printed Type, ATK

    def __post_init__(self) -> None:
        if self.codes != tuple(sorted(set(self.codes))) or any(code <= 0 for code in self.codes):
            raise ValueError("card vocabulary must contain sorted unique positive codes")
        if (tuple(code for code, _, _ in self.card_properties)
                != tuple(sorted({code for code, _, _ in self.card_properties}))
                or any(code not in self.codes or card_type < 0
                       for code, card_type, _ in self.card_properties)):
            raise ValueError("card properties must be sorted unique vocabulary members")

    @classmethod
    def from_goat_whitelist(cls, path: str | Path, *,
                            native_root: str | Path | None = None) -> "CardVocabulary":
        codes = tuple(sorted(code for code, limit in read_goat_whitelist(path).items()
                             if limit > 0))
        if native_root is None:
            return cls(codes)
        properties = load_card_properties(native_root, set(codes))
        missing = set(codes) - properties.keys()
        if missing:
            raise ValueError(f"allowed cards missing pinned printed metadata: {sorted(missing)}")
        return cls(codes, tuple((code, *properties[code]) for code in codes))

    def index(self, code: int | None) -> int:
        if code is None:
            return 0
        # Card pool is small enough that a direct mapping is cheap to construct once.
        return self._indices.get(code, 1)

    @cached_property
    def _indices(self) -> dict[int, int]:
        return {code: index + 2 for index, code in enumerate(self.codes)}

    @property
    def size(self) -> int:
        return len(self.codes) + 2

    @cached_property
    def _properties(self) -> dict[int, tuple[int, int]]:
        return {code: (card_type, attack)
                for code, card_type, attack in self.card_properties}

    def properties(self, code: int | None) -> tuple[int, int]:
        return self._properties.get(code, (0, 0))


@dataclass(frozen=True)
class DecisionFeatures:
    state_cards: Tensor  # [N, 4]: card, zone, owner, position
    state_card_numbers: Tensor  # [N, 5/6]: ATK, DEF, counters, Spell Counters, visible, age
    state_numbers: Tensor  # [10] for v1-v3, [42] for v4
    phase: Tensor  # scalar
    action_kinds: Tensor  # [A]
    action_cards: Tensor  # [A]
    action_targets: Tensor  # [A, T], zero-padded
    action_target_context: Tensor  # [A, T, 5] through v6; v7 adds order, v28 adds counter amount
    action_target_mask: Tensor  # [A, T]: target exists, even when its ID is hidden
    action_numbers: Tensor  # [A, 8] through v5, [A, 11] in v6
    deck_cards: Tensor  # [D]: sorted initial own Main Deck card IDs, or [0] before v5
    known_hand_cards: Tensor  # [H]: publicly known opponent hand IDs, or [0] before v9
    chain_cards: Tensor  # [L, 2]: ordered public chain card and relative controller, or [[0, 0]]
    chain_target_slots: Tensor  # [L, T, 3]: relative controller, field zone, sequence
    state_card_sequences: Tensor  # [N]: field sequence, -1 for non-field cards
    state_equip_slots: Tensor  # [N, 3]: public target controller, zone, sequence
    action_field_slots: Tensor  # [A, 3]: relative controller, zone, sequence
    action_multi_field_slots: Tensor  # [A, T, 3]: field slots in variable target sets

    def to(self, device: torch.device | str) -> "DecisionFeatures":
        return DecisionFeatures(*(value.to(device) for value in self.__dict__.values()))


def encode_decision(observation: Observation, legal_actions: Sequence[Action],
                    vocabulary: CardVocabulary,
                    feature_version: int = POLICY_FEATURE_VERSION) -> DecisionFeatures:
    """Read only the public agent contract; action IDs and native state are ignored."""
    if not legal_actions:
        raise ValueError("cannot score an empty legal-action set")
    if any(action.actor != observation.acting_player for action in legal_actions):
        raise ValueError("legal-action actor differs from observation")
    if feature_version not in range(1, 32):
        raise ValueError("unsupported policy feature version")
    if feature_version >= 22 and not vocabulary.card_properties:
        raise ValueError("feature version 22 requires pinned printed card properties")

    zone_locations = {"monster": 0x04, "spell_trap": 0x08}
    known_codes = ({(card.controller, zone_locations[card.zone], card.sequence): card.code
                    for card in observation.known_opponent_field_cards}
                   if feature_version >= 3 else {})

    def visible_code(code: int | None, controller: int | None,
                     location: int | None, sequence: int | None) -> int | None:
        if code is not None:
            return code
        return known_codes.get((controller, location, sequence))

    cards = []
    card_numbers = []
    card_sequences = []
    equip_slots = []
    for card in (*observation.hand, *observation.field, *observation.graveyards[0],
                 *observation.graveyards[1], *observation.banished[0],
                 *observation.banished[1], *observation.own_extra_deck):
        if card.zone not in ZONES or card.position not in POSITIONS:
            raise ValueError("unknown visible card zone or position")
        code = visible_code(card.code, card.controller, zone_locations.get(card.zone),
                            card.sequence)
        cards.append((vocabulary.index(code), ZONE_IDS[card.zone],
                      int(card.controller != observation.viewer) + 1,
                      POSITION_IDS[card.position]))
        card_sequences.append(card.sequence if card.zone in ("monster", "spell_trap")
                              and card.sequence is not None else -1)
        equip_slots.append((int(card.equipped_to[0] != observation.viewer) + 1,
                            ZONE_IDS["monster"], card.equipped_to[1])
                           if feature_version in EQUIP_FEATURE_VERSIONS
                           and card.equipped_to is not None
                           else (0, 0, -1))
        spell_count = sum(count for kind, count in card.counters if kind == 1)
        values = ((card.attack / 8000 if card.attack is not None else 0.0,
                   card.defense / 8000 if card.defense is not None else 0.0,
                   sum(count for _, count in card.counters) / 10,
                   spell_count / 10,
                   float(card.attack is not None))
                  if feature_version >= 8 else (0.0,) * 5)
        if feature_version >= 29:
            values += (min(card.faceup_turns or 0, 20) / 20,)
        card_numbers.append(values)
    for link in observation.chain:
        cards.append((vocabulary.index(link.card_code), ZONE_IDS["chain"],
                      int(link.controller != observation.viewer) + 1, 3))
        card_numbers.append((0.0,) * (6 if feature_version >= 29 else 5))
        card_sequences.append(-1)
        equip_slots.append((0, 0, -1))
    if not cards:
        cards.append((0, 0, 0, 0))
        card_numbers.append((0.0,) * (6 if feature_version >= 29 else 5))
        card_sequences.append(-1)
        equip_slots.append((0, 0, -1))

    own = observation.viewer
    opponent = 1 - own
    numbers = (
        observation.life_points[own] / 8000, observation.life_points[opponent] / 8000,
        observation.deck_counts[own] / 40, observation.deck_counts[opponent] / 40,
        observation.extra_deck_counts[own] / 40,
        observation.extra_deck_counts[opponent] / 40,
        len(observation.hand) / 40, observation.opponent_hand_count / 40,
        observation.turn / 100, len(observation.chain) / 10,
    )
    if feature_version >= 4:
        disabled = {(slot.player, slot.zone, slot.sequence)
                    for slot in observation.disabled_zones}
        numbers += tuple(
            float((player, zone, sequence) in disabled)
            for player in (own, opponent)
            for zone in ("monster", "spell_trap")
            for sequence in range(8)
        )
    if feature_version == 15:
        # The average card embedding does not retain how many cards occupy
        # each public zone. Counts are available to either player, including
        # for face-down cards whose identities stay hidden.
        numbers += tuple(
            sum(card.controller == player and card.zone == zone
                and card.position == position for card in observation.field) / 5
            for player in (own, opponent)
            for zone in ("monster", "spell_trap")
            for position in ("faceup", "facedown")
        )
        numbers += tuple(len(pile) / 40 for piles in
                         (observation.graveyards, observation.banished)
                         for pile in (piles[own], piles[opponent]))
    if feature_version >= 19:
        numbers += (float(observation.turn_player == own),
                    float(observation.turn_player is not None))
    kind_indices = []
    card_indices = []
    targets = []
    target_context = []
    action_numbers = []
    action_field_slots = []
    action_multi_field_slots = []
    own_field_monsters = {(card.controller, card.sequence): card
                          for card in observation.field
                          if card.zone == "monster" and card.controller == own}
    opponent_monsters = tuple(card for card in observation.field
                              if card.zone == "monster" and card.controller == opponent)
    if feature_version >= 16:
        opposing_stats = tuple(card.attack if card.orientation == "attack"
                               else card.defense for card in opponent_monsters)
        fully_visible = all(card.position == "faceup" and stat is not None
                            for card, stat in zip(opponent_monsters, opposing_stats,
                                                  strict=True))
    if feature_version >= 23:
        visible_enemy_stats = tuple(
            stat for card, stat in zip(opponent_monsters, opposing_stats, strict=True)
            if card.position == "faceup" and stat is not None)
    if feature_version >= 22:
        own_gy_spells = sum(bool(vocabulary.properties(card.code)[0] & SPELL_TYPE)
                            for card in observation.graveyards[own])
        own_backrow = sum(card.zone == "spell_trap" and card.controller == own
                          for card in observation.field)
        enemy_backrow = sum(card.zone == "spell_trap" and card.controller == opponent
                            for card in observation.field)
        own_monster_count = len(own_field_monsters)
        enemy_monster_count = len(opponent_monsters)
    kinds = ACTION_KINDS + ZONE_ACTION_KINDS if feature_version >= 4 else ACTION_KINDS
    if feature_version >= 6:
        kinds += ANNOUNCE_ACTION_KINDS
    if feature_version >= 7:
        kinds += SORT_ACTION_KINDS
    if feature_version >= 28:
        kinds += COUNTER_ACTION_KINDS
    kind_ids = {kind: index + 1 for index, kind in enumerate(kinds)}

    def field_slot(params: dict) -> tuple[int, int, int]:
        location = params.get("location")
        sequence = params.get("sequence")
        controller = params.get("controller")
        zone = {4: "monster", 8: "spell_trap"}.get(location)
        if (zone is None or not isinstance(sequence, int)
                or controller not in (0, 1)):
            return (0, 0, -1)
        return (int(controller != own) + 1, ZONE_IDS[zone], sequence)

    for action_index, action in enumerate(legal_actions):
        params = action.parameters
        kind_indices.append(kind_ids.get(action.kind, 0))
        card_indices.append(vocabulary.index(visible_code(
            params.get("code"), params.get("controller"), params.get("location"),
            params.get("sequence"))))
        selected = (params.get("cards", params.get("zones", ()))
                    if feature_version >= 4 else params.get("cards", ()))
        action_field_slots.append(field_slot(params))
        action_multi_field_slots.append([field_slot(card) for card in selected])
        targets.append([vocabulary.index(visible_code(
            card.get("code"), card.get("controller"), card.get("location"),
            card.get("sequence"))) for card in selected])
        target_context.append([
            (float(card.get("controller", own) != own),
             int(card.get("location", 0)) / 64,
             int(card.get("sequence", 0)) / 64,
             sin(int(card.get("sequence", 0))),
             cos(int(card.get("sequence", 0))))
            + (((rank / max(1, len(selected) - 1)
                 if action.kind == "sort_cards" else 0.0),)
               if feature_version >= 7 else ())
            + ((log1p(max(0, int(card.get("amount", 0)))) / log1p(32767),)
               if feature_version >= 28 else ())
            for rank, card in enumerate(selected)
        ])
        prompt_id = int(params.get("prompt_id", 0))
        race = int(params.get("race", 0))
        race_numbers = (_race_mask_bits(race) if feature_version >= 20 else
                        ((race & 0xFFFFFFFF) / 0xFFFFFFFF,
                         (race >> 32) / 0xFFFFFFFF))
        numeric = (
            float(params.get("controller", own) != own),
            int(params.get("location", 0)) / 64,
            int(params.get("sequence", 0)) / 8,
            int(params.get("position", 0)) / 8,
        ) + race_numbers + ((prompt_id & 0xFFFFFFFF) / 0xFFFFFFFF,
                            len(selected) / 5)
        if feature_version >= 6:
            announced = int(params.get("number", 0))
            numeric += (int(params.get("attribute", 0)) / 127,
                        min(announced, 8000) / 8000,
                        log1p(announced) / log1p((1 << 64) - 1))
        if feature_version >= 16:
            attacker = own_field_monsters.get((action.actor, params.get("sequence"))) \
                if action.kind == "attack" else None
            attack = attacker.attack if attacker is not None else None
            margin = (attack - min(opposing_stats)
                      if attack is not None and opposing_stats and fully_visible else 0)
            numeric += (attack / 8000 if attack is not None else 0.0,
                        margin / 8000,
                        float(action.kind == "attack" and fully_visible),
                        float(action.kind == "attack" and not opponent_monsters))
        if feature_version >= 17:
            pending = observation.pending_attack
            attacker = (own_field_monsters.get((own, pending.sequence))
                        if pending is not None else None)
            target = next((card for card in opponent_monsters
                           if card.sequence == params.get("sequence")), None) \
                if action.kind == "select_card" and params.get("controller") == opponent \
                and params.get("location") == 0x04 else None
            attack = attacker.attack if attacker is not None else None
            defense = (target.attack if target.orientation == "attack" else target.defense) \
                if target is not None and target.position == "faceup" else None
            numeric += (attack / 8000 if attack is not None and target is not None else 0.0,
                        defense / 8000 if defense is not None else 0.0,
                        (attack - defense) / 8000 if attack is not None
                        and defense is not None else 0.0,
                        float(attack is not None and defense is not None))
        if feature_version >= 21:
            matches = (tuple(card for card in observation.field
                             if action.kind == "announce_race" and race > 0
                             and card.zone == "monster" and card.position == "faceup"
                             and card.race is not None and card.race & race))
            enemy_hits = tuple(card for card in matches if card.controller != own)
            own_hits = tuple(card for card in matches if card.controller == own)
            numeric += (len(enemy_hits) / 5, len(own_hits) / 5,
                        sum(card.attack or 0 for card in enemy_hits) / 8000,
                        sum(card.attack or 0 for card in own_hits) / 8000)
        if feature_version >= 22:
            card_type, printed_attack = vocabulary.properties(visible_code(
                params.get("code"), params.get("controller"),
                params.get("location"), params.get("sequence")))
            selected_monster = next((card for card in observation.field
                                     if action.kind == "select_card"
                                     and params.get("location") == 0x04
                                     and card.zone == "monster"
                                     and card.controller == params.get("controller")
                                     and card.sequence == params.get("sequence")
                                     and card.position == "faceup"), None)
            numeric += (float(bool(card_type & FLIP_MONSTER_TYPE)),
                        max(0, printed_attack) / 8000,
                        own_gy_spells / 5, own_backrow / 5, enemy_backrow / 5,
                        own_monster_count / 5, enemy_monster_count / 5,
                        (selected_monster.attack or 0) / 8000
                        if selected_monster is not None else 0.0)
        if feature_version >= 23:
            moved = (own_field_monsters.get((own, params.get("sequence")))
                     if action.kind == "change_position" else None)
            attack = moved.attack if moved is not None else None
            defense = moved.defense if moved is not None else None
            numeric += (float(moved is not None),
                        float(moved is not None and moved.orientation == "defense"),
                        attack / 8000 if attack is not None else 0.0,
                        defense / 8000 if defense is not None else 0.0,
                        (attack - defense) / 8000
                        if attack is not None and defense is not None else 0.0,
                        max(visible_enemy_stats, default=0) / 8000,
                        min(visible_enemy_stats, default=0) / 8000,
                        float(bool(opponent_monsters) and
                              len(visible_enemy_stats) == len(opponent_monsters)))
        if feature_version >= 28:
            counter_total = int(params.get("counter_total", 0))
            numeric += (int(params.get("counter_type", 0)) / 65535,
                        log1p(max(0, counter_total)) / log1p(32767))
        if feature_version >= 30:
            numeric += (action_index / 16 if action.kind == "select_option" else 0.0,)
        if feature_version >= 31:
            announced_code = int(params.get("code", 0)) if action.kind == "announce_card" else 0
            if action.kind == "announce_card" and not 0 < announced_code < (1 << 32):
                raise ValueError("announced card code must be a positive 32-bit ID")
            numeric += tuple(float(bool(announced_code & (1 << bit)))
                             for bit in range(32))
            numeric += (float(action.kind == "announce_card" and
                              announced_code in observation.known_opponent_hand_cards),)
        if feature_version in (24, 25):
            trade = 0
            own_collateral = 0
            estimated = action.kind == "activate" and params.get("code") in (
                HEAVY_STORM, NOBLEMAN_OF_CROSSOUT)
            if estimated and params["code"] == HEAVY_STORM:
                source_is_set = params.get("location") == 8 and any(
                    card.controller == own and card.zone == "spell_trap"
                    and card.sequence == params.get("sequence")
                    and card.code == HEAVY_STORM for card in observation.field)
                own_collateral = own_backrow - int(source_is_set)
                trade = enemy_backrow - own_collateral - 1
            elif estimated:
                enemy_set = any(card.position == "facedown" for card in opponent_monsters)
                own_collateral = int(not enemy_set and any(
                    card.position == "facedown" for card in own_field_monsters.values()))
                trade = int(enemy_set) - own_collateral - 1
            numeric += (trade / 5, own_collateral / 5, float(estimated))
        action_numbers.append(numeric)
    width = max(1, *(len(row) for row in targets))
    padded_targets = [row + [0] * (width - len(row)) for row in targets]
    empty_context = (0.0,) * (7 if feature_version >= 28 else
                              6 if feature_version >= 7 else 5)
    padded_context = [row + [empty_context] * (width - len(row))
                      for row in target_context]
    target_masks = [[1] * len(row) + [0] * (width - len(row)) for row in targets]
    padded_field_slots = [row + [(0, 0, -1)] * (width - len(row))
                          for row in action_multi_field_slots]
    phase = PHASES.index(observation.phase) + 1 if observation.phase in PHASES else 0
    chain_links = [(vocabulary.index(link.card_code),
                    int(link.controller != observation.viewer) + 1)
                   for link in observation.chain]
    if feature_version == 11:
        chain_links.sort()
    chain_targets = (
        [[(int(target.controller != observation.viewer) + 1,
           ZONE_IDS[target.zone], target.sequence)
          for target in link.targets]
         for link in observation.chain]
        if feature_version in CHAIN_TARGET_FEATURE_VERSIONS else []
    )
    target_width = max(1, max((len(row) for row in chain_targets), default=0))
    chain_targets = ([row + [(0, 0, -1)] * (target_width - len(row))
                      for row in chain_targets] if chain_targets else [[(0, 0, -1)]])
    return DecisionFeatures(
        torch.tensor(cards, dtype=torch.long), torch.tensor(card_numbers, dtype=torch.float32),
        torch.tensor(numbers, dtype=torch.float32),
        torch.tensor(phase, dtype=torch.long), torch.tensor(kind_indices, dtype=torch.long),
        torch.tensor(card_indices, dtype=torch.long),
        torch.tensor(padded_targets, dtype=torch.long),
        torch.tensor(padded_context, dtype=torch.float32),
        torch.tensor(target_masks, dtype=torch.bool),
        torch.tensor(action_numbers, dtype=torch.float32),
        torch.tensor([vocabulary.index(code) for code in observation.own_main_deck]
                     if feature_version >= 5 and observation.own_main_deck else [0],
                     dtype=torch.long),
        torch.tensor([vocabulary.index(code)
                      for code in observation.known_opponent_hand_cards]
                     if feature_version >= 9 and observation.known_opponent_hand_cards else [0],
                     dtype=torch.long),
        torch.tensor(chain_links if feature_version >= 10 and chain_links else [(0, 0)],
                     dtype=torch.long),
        torch.tensor(chain_targets, dtype=torch.long),
        torch.tensor(card_sequences, dtype=torch.long),
        torch.tensor(equip_slots, dtype=torch.long),
        torch.tensor(action_field_slots, dtype=torch.long),
        torch.tensor(padded_field_slots, dtype=torch.long),
    )


class LegalActionPolicy(nn.Module):
    """Shared visible-state encoder and action-conditioned legal-option scorer."""

    def __init__(self, vocabulary_size: int, width: int = 64,
                 feature_version: int = POLICY_FEATURE_VERSION) -> None:
        super().__init__()
        if feature_version not in range(1, 32):
            raise ValueError("unsupported policy feature version")
        self.feature_version = feature_version
        self.card = nn.Embedding(vocabulary_size, width, padding_idx=0)
        self.zone = nn.Embedding(len(ZONES) + 1, width, padding_idx=0)
        self.owner = nn.Embedding(3, width, padding_idx=0)
        self.position = nn.Embedding(len(POSITIONS) + 1, width, padding_idx=0)
        if feature_version >= 8:
            self.card_numbers = nn.Sequential(nn.Linear(
                6 if feature_version >= 29 else 5, width), nn.ReLU(),
                                              nn.Linear(width, width))
        self.phase = nn.Embedding(len(PHASES) + 1, width, padding_idx=0)
        kind_count = (len(ACTION_KINDS)
                      + (len(ZONE_ACTION_KINDS) if feature_version >= 4 else 0)
                      + (len(ANNOUNCE_ACTION_KINDS) if feature_version >= 6 else 0)
                      + (len(SORT_ACTION_KINDS) if feature_version >= 7 else 0)
                      + (len(COUNTER_ACTION_KINDS) if feature_version >= 28 else 0))
        self.kind = nn.Embedding(kind_count + 1, width, padding_idx=0)
        number_width = (44 if feature_version >= 19 else 54
                        if feature_version == 15 else 42 if feature_version >= 4 else 10)
        self.state_numbers = nn.Sequential(nn.Linear(number_width, width), nn.ReLU(),
                                           nn.Linear(width, width))
        action_number_width = (137 if feature_version >= 31 else
                               104 if feature_version >= 30 else
                               103 if feature_version >= 28 else
                               104 if feature_version in (24, 25) else 101
                               if feature_version >= 23 else 93
                               if feature_version >= 22 else 85
                               if feature_version >= 21 else 81
                               if feature_version >= 20 else 19
                               if feature_version >= 17 else 15
                               if feature_version == 16 else 11
                               if feature_version >= 6 else 8)
        self.action_numbers = nn.Sequential(nn.Linear(action_number_width, width), nn.ReLU(),
                                            nn.Linear(width, width))
        if feature_version >= 2:
            self.target_context = nn.Sequential(nn.Linear(
                width + 7 if feature_version >= 28 else
                width + 6 if feature_version >= 7 else 5, width), nn.ReLU(),
                                                nn.Linear(width, width))
        if feature_version >= 5:
            self.deck_projection = nn.Sequential(nn.Linear(width, width), nn.ReLU())
        if feature_version >= 9:
            self.known_hand_projection = nn.Sequential(nn.Linear(width, width), nn.ReLU())
        if feature_version >= 10:
            self.chain_encoder = nn.GRU(width, width, batch_first=True)
        self.score = nn.Sequential(nn.Linear(width * 2, width), nn.ReLU(),
                                   nn.Linear(width, 1))
        # Construct the opt-in layer last so common layers keep identical
        # seeded initial weights in v12/v13 comparison experiments.
        if feature_version in EQUIP_FEATURE_VERSIONS:
            self.equip_pair = nn.Sequential(nn.Linear(width * 2, width), nn.ReLU(),
                                            nn.Linear(width, width))
        if feature_version in CHAIN_TARGET_FEATURE_VERSIONS:
            self.chain_target_sequence = nn.Embedding(8, width)
            self.chain_target_pair = nn.Sequential(nn.Linear(width * 2, width), nn.ReLU(),
                                                   nn.Linear(width, width))
        if feature_version >= 18:
            # Directly bind the active effect to each candidate target instead
            # of requiring the pooled state scorer to discover that relation.
            self.source_target_pair = nn.Sequential(nn.Linear(width * 2, width), nn.ReLU(),
                                                    nn.Linear(width, width))
        if feature_version == 25:
            self.trade_head = nn.Linear(2, 1, bias=False)
            nn.init.zeros_(self.trade_head.weight)
        if feature_version == 26:
            self.player_pool = nn.Linear(width * 2, width, bias=False)
            nn.init.zeros_(self.player_pool.weight)
        if feature_version == 27:
            self.action_query = nn.Linear(width, width, bias=False)
            self.attended_card = nn.Linear(width, width, bias=False)
            nn.init.zeros_(self.attended_card.weight)

    def forward(self, features: DecisionFeatures) -> Tensor:
        return self._forward(features)

    def _forward(self, features: DecisionFeatures,
                 chain_hidden: Tensor | None = None,
                 chain_source: Tensor | None = None) -> Tensor:
        cards = features.state_cards
        visible = (self.card(cards[:, 0]) + self.zone(cards[:, 1])
                   + self.owner(cards[:, 2]) + self.position(cards[:, 3]))
        if self.feature_version >= 8:
            visible = visible + self.card_numbers(features.state_card_numbers)
        if self.feature_version in EQUIP_FEATURE_VERSIONS:
            slots = features.state_equip_slots
            target_match = ((slots[:, None, 0] == cards[None, :, 2])
                            & (slots[:, None, 1] == cards[None, :, 1])
                            & (slots[:, None, 2] ==
                               features.state_card_sequences[None, :])
                            & (slots[:, None, 1] != 0))
            target_visible = target_match.to(visible.dtype) @ visible
            pair = self.equip_pair(torch.cat((visible, target_visible), dim=1))
            visible = visible + pair * (slots[:, 1] != 0).unsqueeze(1)
        mask = (cards[:, 1] != 0).unsqueeze(1)
        pooled = (visible * mask).sum(0) / mask.sum().clamp(min=1)
        state = pooled + self.phase(features.phase) + self.state_numbers(
            features.state_numbers)
        if self.feature_version == 26:
            own_mask = (cards[:, 1] != 0) & (cards[:, 2] == 1)
            opponent_mask = (cards[:, 1] != 0) & (cards[:, 2] == 2)
            own_pool = (visible * own_mask.unsqueeze(1)).sum(0) / own_mask.sum().clamp(min=1)
            opponent_pool = (visible * opponent_mask.unsqueeze(1)).sum(0) / (
                opponent_mask.sum().clamp(min=1))
            state = state + self.player_pool(torch.cat((own_pool, opponent_pool)))
        if self.feature_version >= 5:
            deck_mask = (features.deck_cards != 0).unsqueeze(1)
            deck = (self.card(features.deck_cards) * deck_mask).sum(0) / deck_mask.sum().clamp(
                min=1)
            state = state + self.deck_projection(deck)
        if self.feature_version >= 9:
            known_mask = (features.known_hand_cards != 0).unsqueeze(1)
            known_hand = (self.card(features.known_hand_cards) * known_mask).sum(0) / (
                known_mask.sum().clamp(min=1))
            state = state + self.known_hand_projection(known_hand)
        if self.feature_version >= 10:
            if chain_hidden is None:
                chain = features.chain_cards
                chain_input = self.card(chain[:, 0]) + self.owner(chain[:, 1])
                if self.feature_version in CHAIN_TARGET_FEATURE_VERSIONS:
                    slots = features.chain_target_slots
                    slot_mask = slots[:, :, 0] != 0
                    field_match = ((slots[:, :, None, 0] == cards[None, None, :, 2])
                                   & (slots[:, :, None, 1] == cards[None, None, :, 1])
                                   & (slots[:, :, None, 2] ==
                                      features.state_card_sequences[None, None, :])
                                   & slot_mask[:, :, None])
                    occupant = field_match.to(visible.dtype) @ visible
                    target = (self.owner(slots[:, :, 0]) + self.zone(slots[:, :, 1])
                              + self.chain_target_sequence(slots[:, :, 2].clamp(min=0))
                              + occupant)
                    target_mean = (target * slot_mask.unsqueeze(-1)).sum(1) / (
                        slot_mask.sum(1, keepdim=True).clamp(min=1))
                    chain_input = chain_input + self.chain_target_pair(torch.cat(
                        (chain_input, target_mean), dim=1)) * slot_mask.any(1).unsqueeze(1)
                _, hidden = self.chain_encoder(chain_input.unsqueeze(0))
                chain_hidden = hidden[-1, 0] * (chain[:, 0] != 0).any()
            state = state + chain_hidden
        targets = features.action_targets
        target_mask = ((targets != 0) if self.feature_version == 1
                       else features.action_target_mask).unsqueeze(-1)
        target_mean = (self.card(targets) * target_mask).sum(1) / target_mask.sum(1).clamp(
            min=1)
        if self.feature_version >= 2:
            context_input = (torch.cat((self.card(targets), features.action_target_context),
                                       dim=-1) if self.feature_version >= 7
                             else features.action_target_context)
            context = self.target_context(context_input)
            target_mean = target_mean + (context * target_mask).sum(1) / target_mask.sum(
                1).clamp(min=1)
        action = (self.kind(features.action_kinds) + self.card(features.action_cards)
                  + target_mean + self.action_numbers(features.action_numbers))
        if self.feature_version >= 18:
            source = (features.chain_cards[-1, 0] if chain_source is None
                      else chain_source)
            source_embedding = self.card(source).expand(action.shape[0], -1)
            target_embedding = self.card(features.action_cards)
            action = action + self.source_target_pair(torch.cat(
                (source_embedding, target_embedding), dim=1)) * (source != 0)
        if self.feature_version >= 12:
            # Bind each selected field slot to its visible card. A pooled state
            # alone loses which known face-down identity occupies which slot.
            slots = features.action_field_slots
            direct_match = ((slots[:, None, 0] == cards[None, :, 2])
                            & (slots[:, None, 1] == cards[None, :, 1])
                            & (slots[:, None, 2] ==
                               features.state_card_sequences[None, :])
                            & (slots[:, None, 1] != 0))
            action = action + direct_match.to(visible.dtype) @ visible
            multi_slots = features.action_multi_field_slots
            multi_match = ((multi_slots[:, :, None, 0] == cards[None, None, :, 2])
                           & (multi_slots[:, :, None, 1] == cards[None, None, :, 1])
                           & (multi_slots[:, :, None, 2] ==
                              features.state_card_sequences[None, None, :])
                           & (multi_slots[:, :, None, 1] != 0))
            matched = (multi_match.to(visible.dtype) @ visible)
            multi_mask = (multi_slots[:, :, 1] != 0).unsqueeze(-1)
            action = action + (matched * multi_mask).sum(1) / multi_mask.sum(1).clamp(min=1)
        if self.feature_version == 27:
            relevance = self.action_query(action) @ visible.transpose(0, 1)
            relevance = relevance / sqrt(visible.shape[1])
            valid_cards = cards[:, 1] != 0
            relevance = relevance.masked_fill(~valid_cards[None, :], -1e9)
            attended = (relevance.softmax(dim=1) * valid_cards[None, :]) @ visible
            action = action + self.attended_card(attended)
        logits = self.score(torch.cat((state.expand(action.shape[0], -1), action), dim=1)).squeeze(1)
        if self.feature_version == 25:
            trade = features.action_numbers[:, -3] * 5
            present = features.action_numbers[:, -1]
            logits = logits + self.trade_head(torch.stack((trade, present), dim=1)).squeeze(1)
        return logits

    def forward_batch(self, decisions: Sequence[DecisionFeatures]) -> tuple[Tensor, Tensor]:
        """Score padded variable-length decisions together, returning a legal mask.

        The chain-target variants need their field-dependent GRU inputs and
        remain on the ordinary per-decision path. Other v10+ versions batch
        the chain GRU before vectorizing the remaining state/action encoder.
        """
        if not decisions or self.feature_version < 10 or (
                self.feature_version in CHAIN_TARGET_FEATURE_VERSIONS):
            raise ValueError("batched forward requires decisions and a supported v10+ model")
        action_lengths = [len(item.action_kinds) for item in decisions]
        if any(length < 1 for length in action_lengths):
            raise ValueError("each batched decision needs a legal action")
        names = tuple(decisions[0].__dict__)
        stacked = []
        for name in names:
            values = [getattr(item, name) for item in decisions]
            shape = tuple(max(value.shape[axis] for value in values)
                          for axis in range(values[0].ndim))
            padded_values = values[0].new_zeros((len(values), *shape))
            for index, value in enumerate(values):
                padded_values[(index, *(slice(0, size) for size in value.shape))] = value
            stacked.append(padded_values)
        padded = DecisionFeatures(*stacked)
        chain_lengths = [len(item.chain_cards) for item in decisions]
        chain = padded.chain_cards
        chain_input = self.card(chain[:, :, 0]) + self.owner(chain[:, :, 1])
        packed = pack_padded_sequence(chain_input, chain_lengths,
                                      batch_first=True, enforce_sorted=False)
        _, hidden = self.chain_encoder(packed)
        chain_hidden = hidden[-1] * (chain[:, 0, 0] != 0).unsqueeze(1)
        chain_sources = torch.stack([item.chain_cards[-1, 0] for item in decisions])

        def score(*values: Tensor) -> Tensor:
            features = DecisionFeatures(*values[:-2])
            return self._forward(features, values[-2], values[-1])

        logits = torch.vmap(score)(*stacked, chain_hidden, chain_sources)
        mask = (torch.arange(logits.shape[1], device=logits.device)[None, :]
                < torch.tensor(action_lengths, device=logits.device)[:, None])
        return logits.masked_fill(~mask, -1e9), mask


class PolicyAgent:
    """Greedy inference through the same Agent interface as the baselines."""

    def __init__(self, model: LegalActionPolicy, vocabulary: CardVocabulary,
                 *, tactical_guard: bool = False,
                 card_races: Mapping[int, int] | None = None,
                 weak_flip_attacks: Mapping[int, int] | None = None,
                 self_target_guard: bool = False,
                 own_loss_guard: bool = False,
                 own_loss_guard_version: int = 1,
                 card_facts: Mapping[int, tuple[int, int, int]] | None = None,
                 position_guard: bool = False,
                 position_guard_version: int = 2) -> None:
        self.model = model
        self.vocabulary = vocabulary
        self.tactical_guard = tactical_guard
        self.card_races = dict(card_races or {})
        self.weak_flip_attacks = dict(weak_flip_attacks or {})
        self.self_target_guard = self_target_guard
        self.own_loss_guard = own_loss_guard
        if own_loss_guard_version not in (1, 2, 3):
            raise ValueError("unknown own-loss guard version")
        if own_loss_guard and own_loss_guard_version == 2 and card_facts is None:
            raise ValueError("own-loss guard v2 requires printed card facts")
        self.own_loss_guard_version = own_loss_guard_version
        self.card_facts = dict(card_facts or {})
        self.position_guard = position_guard
        if position_guard_version not in (1, 2):
            raise ValueError("unknown position guard version")
        self.position_guard_version = position_guard_version
        self._cancel_turn: int | None = None
        self._cancelled_prompts: list[tuple[Observation, tuple[tuple, ...]]] = []

    def select_action(self, observation: Observation, legal_actions: Sequence[Action]) -> Action:
        if len(legal_actions) == 1:
            return legal_actions[0]
        features = encode_decision(observation, legal_actions, self.vocabulary,
                                   getattr(self.model, "feature_version", POLICY_FEATURE_VERSION))
        device = next(self.model.parameters()).device
        if self.model.training:
            self.model.eval()
        with torch.inference_mode():
            scores = self.model(features.to(device))
        admissible = (admissible_action_indices(observation, legal_actions,
                                                self.card_races)
                      if self.tactical_guard else range(len(legal_actions)))
        if self.own_loss_guard:
            admissible = safe_optional_own_loss_indices(
                observation, legal_actions, admissible)
            if self.own_loss_guard_version == 2:
                admissible = safe_one_shot_response_indices(
                    observation, legal_actions, admissible, self.card_facts)
            if self.own_loss_guard_version == 3:
                admissible = safe_idle_own_ring_indices(
                    observation, legal_actions, admissible)
            admissible = safe_target_indices(
                observation, legal_actions, admissible,
                protect_removal_targets=True)
        if self.self_target_guard:
            admissible = safe_target_indices(observation, legal_actions, admissible)
        if self.position_guard:
            admissible = safe_position_indices(
                observation, legal_actions, admissible,
                empty_field_attack_guard=self.position_guard_version >= 2)
        chosen = legal_actions[max(admissible, key=lambda i: scores[i].item())]
        if self.tactical_guard and self.weak_flip_attacks:
            chosen = (weak_flip_set_substitute(
                observation, legal_actions, chosen, self.weak_flip_attacks)
                or chosen)
        if chosen.kind == "cancel":
            if observation.turn != self._cancel_turn:
                self._cancel_turn = observation.turn
                self._cancelled_prompts.clear()
            # A cancellation may return to the same prompt after an activation
            # retry. Ignore history text and ephemeral action IDs, but compare
            # all player-visible state and legal choices before overriding it.
            prompt = (replace(observation, public_history=()),
                      tuple((action.kind, action.actor, action.parameters)
                            for action in legal_actions))
            if prompt in self._cancelled_prompts:
                alternatives = [(index, action) for index, action in enumerate(legal_actions)
                                if action.kind != "cancel"]
                if alternatives:
                    chosen = max(alternatives, key=lambda item: scores[item[0]].item())[1]
            else:
                self._cancelled_prompts.append(prompt)
                if len(self._cancelled_prompts) > 64:
                    self._cancelled_prompts.pop(0)
        if chosen.kind == "unselect_card":
            finish = next((action for action in legal_actions
                           if action.kind == "finish_selection"), None)
            if finish is not None:
                chosen = finish
            else:
                # Select/unselect prompts can offer several selected cards.
                # Toggling a different card on each step defeats the old
                # single-card repeat check and can loop indefinitely. If the
                # selection is not finishable, add a legal card when possible.
                alternatives = [(index, action) for index, action in enumerate(legal_actions)
                                if action.kind == "select_card"]
                if alternatives:
                    chosen = max(alternatives, key=lambda item: scores[item[0]].item())[1]
        return chosen
