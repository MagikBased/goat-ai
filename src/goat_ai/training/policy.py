"""Visible-state, action-conditioned policy for variable legal-action sets."""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from functools import cached_property
from math import cos, log1p, sin
from pathlib import Path

import torch
from torch import Tensor, nn

from goat_ai.actions import Action
from goat_ai.engine.decks import read_goat_whitelist
from goat_ai.observations import Observation

ZONES = ("hand", "monster", "spell_trap", "graveyard", "banished", "extra", "chain")
POSITIONS = ("hidden", "facedown", "faceup")
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
POLICY_INFERENCE_VERSION = 3  # permit legal cancel once per visible prompt
POLICY_FEATURE_VERSION = 10  # later versions are opt-in representation experiments
# Version 16 branches from v12 so its combat relation can be tested without
# the separate v13-v15 equip, chain-target, and occupancy experiments.
# Version 17 adds attacker-to-target combat stats using schema-v22 context.
EQUIP_FEATURE_VERSIONS = (13, 14, 15)
CHAIN_TARGET_FEATURE_VERSIONS = (14, 15)


@dataclass(frozen=True)
class CardVocabulary:
    """Index 0 is hidden/absent; index 1 is an unknown visible card."""

    codes: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.codes != tuple(sorted(set(self.codes))) or any(code <= 0 for code in self.codes):
            raise ValueError("card vocabulary must contain sorted unique positive codes")

    @classmethod
    def from_goat_whitelist(cls, path: str | Path) -> "CardVocabulary":
        return cls(tuple(sorted(code for code, limit in read_goat_whitelist(path).items()
                                if limit > 0)))

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


@dataclass(frozen=True)
class DecisionFeatures:
    state_cards: Tensor  # [N, 4]: card, zone, owner, position
    state_card_numbers: Tensor  # [N, 5]: ATK, DEF, counters, Spell Counters, visible
    state_numbers: Tensor  # [10] for v1-v3, [42] for v4
    phase: Tensor  # scalar
    action_kinds: Tensor  # [A]
    action_cards: Tensor  # [A]
    action_targets: Tensor  # [A, T], zero-padded
    action_target_context: Tensor  # [A, T, 5] through v6; v7 adds selected order
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
    if feature_version not in range(1, 18):
        raise ValueError("unsupported policy feature version")

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
        cards.append((vocabulary.index(code), ZONES.index(card.zone) + 1,
                      int(card.controller != observation.viewer) + 1,
                      POSITIONS.index(card.position) + 1))
        card_sequences.append(card.sequence if card.zone in ("monster", "spell_trap")
                              and card.sequence is not None else -1)
        equip_slots.append((int(card.equipped_to[0] != observation.viewer) + 1,
                            ZONES.index("monster") + 1, card.equipped_to[1])
                           if feature_version in EQUIP_FEATURE_VERSIONS
                           and card.equipped_to is not None
                           else (0, 0, -1))
        spell_count = sum(count for kind, count in card.counters if kind == 1)
        card_numbers.append((card.attack / 8000 if card.attack is not None else 0.0,
                             card.defense / 8000 if card.defense is not None else 0.0,
                             sum(count for _, count in card.counters) / 10,
                             spell_count / 10,
                             float(card.attack is not None))
                            if feature_version >= 8 else (0.0,) * 5)
    for link in observation.chain:
        cards.append((vocabulary.index(link.card_code), ZONES.index("chain") + 1,
                      int(link.controller != observation.viewer) + 1, 3))
        card_numbers.append((0.0,) * 5)
        card_sequences.append(-1)
        equip_slots.append((0, 0, -1))
    if not cards:
        cards.append((0, 0, 0, 0))
        card_numbers.append((0.0,) * 5)
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
    kinds = ACTION_KINDS + ZONE_ACTION_KINDS if feature_version >= 4 else ACTION_KINDS
    if feature_version >= 6:
        kinds += ANNOUNCE_ACTION_KINDS
    if feature_version >= 7:
        kinds += SORT_ACTION_KINDS

    def field_slot(params: dict) -> tuple[int, int, int]:
        location = params.get("location")
        sequence = params.get("sequence")
        controller = params.get("controller")
        zone = {4: "monster", 8: "spell_trap"}.get(location)
        if (zone is None or not isinstance(sequence, int)
                or controller not in (0, 1)):
            return (0, 0, -1)
        return (int(controller != own) + 1, ZONES.index(zone) + 1, sequence)

    for action in legal_actions:
        params = action.parameters
        kind_indices.append(kinds.index(action.kind) + 1
                            if action.kind in kinds else 0)
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
            for rank, card in enumerate(selected)
        ])
        prompt_id = int(params.get("prompt_id", 0))
        race = int(params.get("race", 0))
        numeric = (
            float(params.get("controller", own) != own),
            int(params.get("location", 0)) / 64,
            int(params.get("sequence", 0)) / 8,
            int(params.get("position", 0)) / 8,
            (race & 0xFFFFFFFF) / 0xFFFFFFFF,
            (race >> 32) / 0xFFFFFFFF,
            (prompt_id & 0xFFFFFFFF) / 0xFFFFFFFF,
            len(selected) / 5,
        )
        if feature_version >= 6:
            announced = int(params.get("number", 0))
            numeric += (int(params.get("attribute", 0)) / 127,
                        min(announced, 8000) / 8000,
                        log1p(announced) / log1p((1 << 64) - 1))
        if feature_version >= 16:
            attacker = own_field_monsters.get((action.actor, params.get("sequence"))) \
                if action.kind == "attack" else None
            attack = attacker.attack if attacker is not None else None
            fully_visible = all(card.position == "faceup"
                                and (card.attack if card.orientation == "attack"
                                     else card.defense) is not None
                                for card in opponent_monsters)
            opposing_stats = tuple(card.attack if card.orientation == "attack"
                                   else card.defense for card in opponent_monsters)
            margin = (attack - min(opposing_stats)
                      if attack is not None and opposing_stats and fully_visible else 0)
            numeric += (attack / 8000 if attack is not None else 0.0,
                        margin / 8000,
                        float(action.kind == "attack" and fully_visible),
                        float(action.kind == "attack" and not opponent_monsters))
        if feature_version == 17:
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
        action_numbers.append(numeric)
    width = max(1, *(len(row) for row in targets))
    padded_targets = [row + [0] * (width - len(row)) for row in targets]
    empty_context = (0.0,) * (6 if feature_version >= 7 else 5)
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
           ZONES.index(target.zone) + 1, target.sequence)
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
        if feature_version not in range(1, 18):
            raise ValueError("unsupported policy feature version")
        self.feature_version = feature_version
        self.card = nn.Embedding(vocabulary_size, width, padding_idx=0)
        self.zone = nn.Embedding(len(ZONES) + 1, width, padding_idx=0)
        self.owner = nn.Embedding(3, width, padding_idx=0)
        self.position = nn.Embedding(len(POSITIONS) + 1, width, padding_idx=0)
        if feature_version >= 8:
            self.card_numbers = nn.Sequential(nn.Linear(5, width), nn.ReLU(),
                                              nn.Linear(width, width))
        self.phase = nn.Embedding(len(PHASES) + 1, width, padding_idx=0)
        kind_count = (len(ACTION_KINDS)
                      + (len(ZONE_ACTION_KINDS) if feature_version >= 4 else 0)
                      + (len(ANNOUNCE_ACTION_KINDS) if feature_version >= 6 else 0)
                      + (len(SORT_ACTION_KINDS) if feature_version >= 7 else 0))
        self.kind = nn.Embedding(kind_count + 1, width, padding_idx=0)
        number_width = 54 if feature_version == 15 else 42 if feature_version >= 4 else 10
        self.state_numbers = nn.Sequential(nn.Linear(number_width, width), nn.ReLU(),
                                           nn.Linear(width, width))
        action_number_width = (19 if feature_version == 17 else 15
                               if feature_version == 16 else 11
                               if feature_version >= 6 else 8)
        self.action_numbers = nn.Sequential(nn.Linear(action_number_width, width), nn.ReLU(),
                                            nn.Linear(width, width))
        if feature_version >= 2:
            self.target_context = nn.Sequential(nn.Linear(
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

    def forward(self, features: DecisionFeatures) -> Tensor:
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
            state = state + hidden[-1, 0] * (chain[:, 0] != 0).any()
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
        return self.score(torch.cat((state.expand(len(action), -1), action), dim=1)).squeeze(1)


class PolicyAgent:
    """Greedy inference through the same Agent interface as the baselines."""

    def __init__(self, model: LegalActionPolicy, vocabulary: CardVocabulary) -> None:
        self.model = model
        self.vocabulary = vocabulary
        self._last_selection: tuple[int, str, tuple] | None = None
        self._cancel_turn: int | None = None
        self._cancelled_prompts: list[tuple[Observation, tuple[tuple, ...]]] = []

    @staticmethod
    def _card_reference(action: Action) -> tuple:
        return tuple(action.parameters.get(key) for key in
                     ("code", "controller", "location", "sequence"))

    def select_action(self, observation: Observation, legal_actions: Sequence[Action]) -> Action:
        features = encode_decision(observation, legal_actions, self.vocabulary,
                                   getattr(self.model, "feature_version", POLICY_FEATURE_VERSION))
        device = next(self.model.parameters()).device
        self.model.eval()
        with torch.no_grad():
            scores = self.model(features.to(device))
        chosen = legal_actions[int(scores.argmax().item())]
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
            elif self._last_selection == (
                observation.turn, observation.phase, self._card_reference(chosen)
            ):
                alternatives = [(index, action) for index, action in enumerate(legal_actions)
                                if action.kind == "select_card"]
                if alternatives:
                    chosen = max(alternatives, key=lambda item: scores[item[0]].item())[1]
        self._last_selection = ((observation.turn, observation.phase,
                                 self._card_reference(chosen))
                                if chosen.kind == "select_card" else None)
        return chosen
