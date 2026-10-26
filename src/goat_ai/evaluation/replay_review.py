"""Conservative, player-visible prompts for human review of policy replays.

These are candidates, not automatic play labels or evidence of a rules error.
"""

import re
from collections import Counter
from dataclasses import asdict, dataclass

from goat_ai.actions import Action
from goat_ai.replay import Trajectory

HEAVY_STORM = 19613556
RING_OF_DESTRUCTION = 511000824
TORRENTIAL_TRIBUTE = 53582587
SCAPEGOAT = 504700123
ROYAL_DECREE = 51452091
SAKURETSU_ARMOR = 56120475


@dataclass(frozen=True)
class ReviewCandidate:
    decision_index: int
    category: str
    turn: int
    phase: str
    acting_player: int
    evidence: dict[str, int]

    @property
    def viewer_frame(self) -> int:
        return self.decision_index + 1

    def to_dict(self) -> dict:
        return {**asdict(self), "viewer_frame": self.viewer_frame}


def _is_action(action: Action, kind: str, code: int) -> bool:
    return action.kind == kind and action.parameters.get("code") == code


def review_candidates(trajectory: Trajectory) -> tuple[ReviewCandidate, ...]:
    """Flag selected actions of the recorded policy seat using only its view.

    Repeated priority passes in the same turn and phase are reported once so
    a reviewer gets a useful shortlist. Callers must verify the source replay
    against its native assets before treating these as replay-backed findings.
    """
    if trajectory.source != "policy_evaluation":
        raise ValueError("review candidates require a policy_evaluation replay")
    metadata = trajectory.skill_metadata or {}
    seat = metadata.get("demonstrator_seat")
    if type(seat) is not int or seat not in (0, 1):
        raise ValueError("policy replay must identify its policy seat")
    checkpoint_sha256 = metadata.get("policy_checkpoint_sha256")
    if (not isinstance(checkpoint_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", checkpoint_sha256) is None):
        raise ValueError("policy replay must identify its checkpoint SHA-256")
    candidates: list[ReviewCandidate] = []
    seen: set[tuple[str, int, str]] = set()
    for index, record in enumerate(trajectory.decisions):
        obs = record.observation
        if obs.acting_player != seat:
            continue
        own = [c for c in obs.field if c.controller == seat]
        opposing = [c for c in obs.field if c.controller != seat]
        own_monsters = [c for c in own if c.zone == "monster"]
        enemy_monsters = [c for c in opposing if c.zone == "monster"]
        own_backrow = sum(c.zone == "spell_trap" for c in own)
        enemy_backrow = sum(c.zone == "spell_trap" for c in opposing)
        can_pass = any(a.kind == "pass" for a in record.legal_actions)
        goat_offered = any(_is_action(a, "chain", SCAPEGOAT)
                           for a in record.legal_actions)
        selected = record.selected_action
        found: list[tuple[str, dict[str, int]]] = []
        own_other_backrow = own_backrow
        if (_is_action(selected, "activate", HEAVY_STORM)
                and selected.parameters.get("location") == 8
                and selected.parameters.get("controller") == seat):
            own_other_backrow -= sum(
                c.zone == "spell_trap" and c.sequence == selected.parameters.get("sequence")
                for c in own)
        if (_is_action(selected, "activate", HEAVY_STORM)
                and own_other_backrow > 0 and enemy_backrow == 0):
            found.append(("heavy_storm_only_own_backrow",
                          {"own_other_backrow": own_other_backrow,
                           "enemy_backrow": 0}))
        if (_is_action(selected, "chain", SAKURETSU_ARMOR) and can_pass
                and any(c.zone == "spell_trap" and c.position == "faceup"
                        and c.code == ROYAL_DECREE for c in obs.field)):
            found.append(("sakuretsu_under_decree", {"faceup_decree": 1}))
        if (_is_action(selected, "chain", TORRENTIAL_TRIBUTE) and can_pass
                and own_monsters and not enemy_monsters):
            found.append(("torrential_only_own_monsters",
                          {"own_monsters": len(own_monsters), "enemy_monsters": 0}))
        if (_is_action(selected, "chain", RING_OF_DESTRUCTION) and can_pass
                and any(c.position == "faceup" for c in own_monsters)
                and not any(c.position == "faceup" for c in enemy_monsters)):
            found.append(("ring_without_visible_enemy_target",
                          {"own_monsters": len(own_monsters),
                           "visible_enemy_monsters": 0}))
        if (selected.kind == "pass" and goat_offered
                and obs.turn_player is not None and obs.turn_player != seat):
            if (obs.phase in ("battle_start", "battle_step")
                    and not own_monsters and enemy_monsters):
                found.append(("scapegoat_pass_during_open_attack",
                              {"enemy_monsters": len(enemy_monsters),
                               "own_life_points": obs.life_points[seat]}))
            elif (obs.phase == "end" and not own_monsters
                  and len(enemy_monsters) >= 2):
                found.append(("scapegoat_pass_opponent_end",
                              {"enemy_monsters": len(enemy_monsters),
                               "own_life_points": obs.life_points[seat]}))
        for category, evidence in found:
            key = (category, obs.turn, obs.phase)
            if key not in seen:
                seen.add(key)
                candidates.append(ReviewCandidate(
                    index, category, obs.turn, obs.phase, seat, evidence))
    return tuple(candidates)


def category_counts(candidates: tuple[ReviewCandidate, ...]) -> dict[str, int]:
    return dict(sorted(Counter(c.category for c in candidates).items()))
