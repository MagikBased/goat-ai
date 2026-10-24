"""Visible-state, action-conditioned policy for variable legal-action sets."""

from collections.abc import Sequence
from dataclasses import dataclass
from functools import cached_property
from math import cos, sin
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
POLICY_INFERENCE_VERSION = 2  # selection-progress and cancel-loop guards
POLICY_FEATURE_VERSION = 3  # resolve publicly known facedown card IDs by field slot


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
    state_numbers: Tensor  # [10]
    phase: Tensor  # scalar
    action_kinds: Tensor  # [A]
    action_cards: Tensor  # [A]
    action_targets: Tensor  # [A, T], zero-padded
    action_target_context: Tensor  # [A, T, 5]: owner, zone, slot, slot sin/cos
    action_target_mask: Tensor  # [A, T]: target exists, even when its ID is hidden
    action_numbers: Tensor  # [A, 8]

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
    if feature_version not in (1, 2, 3):
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
    for link in observation.chain:
        cards.append((vocabulary.index(link.card_code), ZONES.index("chain") + 1,
                      int(link.controller != observation.viewer) + 1, 3))
    if not cards:
        cards.append((0, 0, 0, 0))

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
    kind_indices = []
    card_indices = []
    targets = []
    target_context = []
    action_numbers = []
    for action in legal_actions:
        params = action.parameters
        kind_indices.append(ACTION_KINDS.index(action.kind) + 1
                            if action.kind in ACTION_KINDS else 0)
        card_indices.append(vocabulary.index(visible_code(
            params.get("code"), params.get("controller"), params.get("location"),
            params.get("sequence"))))
        selected = params.get("cards", ())
        targets.append([vocabulary.index(visible_code(
            card.get("code"), card.get("controller"), card.get("location"),
            card.get("sequence"))) for card in selected])
        target_context.append([
            (float(card.get("controller", own) != own),
             int(card.get("location", 0)) / 64,
             int(card.get("sequence", 0)) / 64,
             sin(int(card.get("sequence", 0))),
             cos(int(card.get("sequence", 0))))
            for card in selected
        ])
        prompt_id = int(params.get("prompt_id", 0))
        race = int(params.get("race", 0))
        action_numbers.append((
            float(params.get("controller", own) != own),
            int(params.get("location", 0)) / 64,
            int(params.get("sequence", 0)) / 8,
            int(params.get("position", 0)) / 8,
            (race & 0xFFFFFFFF) / 0xFFFFFFFF,
            (race >> 32) / 0xFFFFFFFF,
            (prompt_id & 0xFFFFFFFF) / 0xFFFFFFFF,
            len(selected) / 5,
        ))
    width = max(1, *(len(row) for row in targets))
    padded_targets = [row + [0] * (width - len(row)) for row in targets]
    padded_context = [row + [(0.0, 0.0, 0.0, 0.0, 0.0)] * (width - len(row))
                      for row in target_context]
    target_masks = [[1] * len(row) + [0] * (width - len(row)) for row in targets]
    phase = PHASES.index(observation.phase) + 1 if observation.phase in PHASES else 0
    return DecisionFeatures(
        torch.tensor(cards, dtype=torch.long), torch.tensor(numbers, dtype=torch.float32),
        torch.tensor(phase, dtype=torch.long), torch.tensor(kind_indices, dtype=torch.long),
        torch.tensor(card_indices, dtype=torch.long),
        torch.tensor(padded_targets, dtype=torch.long),
        torch.tensor(padded_context, dtype=torch.float32),
        torch.tensor(target_masks, dtype=torch.bool),
        torch.tensor(action_numbers, dtype=torch.float32),
    )


class LegalActionPolicy(nn.Module):
    """Shared visible-state encoder and action-conditioned legal-option scorer."""

    def __init__(self, vocabulary_size: int, width: int = 64,
                 feature_version: int = POLICY_FEATURE_VERSION) -> None:
        super().__init__()
        if feature_version not in (1, 2, 3):
            raise ValueError("unsupported policy feature version")
        self.feature_version = feature_version
        self.card = nn.Embedding(vocabulary_size, width, padding_idx=0)
        self.zone = nn.Embedding(len(ZONES) + 1, width, padding_idx=0)
        self.owner = nn.Embedding(3, width, padding_idx=0)
        self.position = nn.Embedding(len(POSITIONS) + 1, width, padding_idx=0)
        self.phase = nn.Embedding(len(PHASES) + 1, width, padding_idx=0)
        self.kind = nn.Embedding(len(ACTION_KINDS) + 1, width, padding_idx=0)
        self.state_numbers = nn.Sequential(nn.Linear(10, width), nn.ReLU(),
                                           nn.Linear(width, width))
        self.action_numbers = nn.Sequential(nn.Linear(8, width), nn.ReLU(),
                                            nn.Linear(width, width))
        if feature_version >= 2:
            self.target_context = nn.Sequential(nn.Linear(5, width), nn.ReLU(),
                                                nn.Linear(width, width))
        self.score = nn.Sequential(nn.Linear(width * 2, width), nn.ReLU(),
                                   nn.Linear(width, 1))

    def forward(self, features: DecisionFeatures) -> Tensor:
        cards = features.state_cards
        visible = (self.card(cards[:, 0]) + self.zone(cards[:, 1])
                   + self.owner(cards[:, 2]) + self.position(cards[:, 3]))
        mask = (cards[:, 1] != 0).unsqueeze(1)
        pooled = (visible * mask).sum(0) / mask.sum().clamp(min=1)
        state = pooled + self.phase(features.phase) + self.state_numbers(
            features.state_numbers)
        targets = features.action_targets
        target_mask = ((targets != 0) if self.feature_version == 1
                       else features.action_target_mask).unsqueeze(-1)
        target_mean = (self.card(targets) * target_mask).sum(1) / target_mask.sum(1).clamp(
            min=1)
        if self.feature_version >= 2:
            context = self.target_context(features.action_target_context)
            target_mean = target_mean + (context * target_mask).sum(1) / target_mask.sum(
                1).clamp(min=1)
        action = (self.kind(features.action_kinds) + self.card(features.action_cards)
                  + target_mean + self.action_numbers(features.action_numbers))
        return self.score(torch.cat((state.expand(len(action), -1), action), dim=1)).squeeze(1)


class PolicyAgent:
    """Greedy inference through the same Agent interface as the baselines."""

    def __init__(self, model: LegalActionPolicy, vocabulary: CardVocabulary) -> None:
        self.model = model
        self.vocabulary = vocabulary
        self._last_selection: tuple[int, str, tuple] | None = None

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
            alternatives = [(index, action) for index, action in enumerate(legal_actions)
                            if action.kind != "cancel"]
            if alternatives:
                chosen = max(alternatives, key=lambda item: scores[item[0]].item())[1]
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
