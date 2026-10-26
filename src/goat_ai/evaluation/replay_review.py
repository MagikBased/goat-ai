"""Conservative, player-visible prompts for human review of policy replays.

These are candidates, not automatic play labels or evidence of a rules error.
"""

import re
from math import isfinite
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass

from goat_ai.actions import Action
from goat_ai.agents.tactical_guard import visible_monster_race
from goat_ai.replay import Trajectory

HEAVY_STORM = 19613556
RING_OF_DESTRUCTION = 511000824
TORRENTIAL_TRIBUTE = 53582587
SCAPEGOAT = 504700123
ROYAL_DECREE = 51452091
SAKURETSU_ARMOR = 56120475
TRIBE_INFECTING_VIRUS = 33184167
BLACK_LUSTER_SOLDIER = 504700118
MYSTICAL_SPACE_TYPHOON = 5318639
BREAKER_THE_MAGICAL_WARRIOR = 71413901


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


def review_candidates(trajectory: Trajectory,
                      card_races: Mapping[int, int] | None = None,
                      weak_flip_attacks: Mapping[int, int] | None = None,
                      ) -> tuple[ReviewCandidate, ...]:
    """Flag selected actions of the recorded policy seat using only its view.

    Repeated priority passes in the same turn and phase are reported once so
    a reviewer gets a useful shortlist. Callers must verify the source replay
    against its native assets before treating these as replay-backed findings.
    """
    if trajectory.source not in ("policy_evaluation", "self_play_rl"):
        raise ValueError("review candidates require a policy_evaluation or self_play_rl replay")
    metadata = trajectory.skill_metadata or {}
    seat = metadata.get("learner_seat" if trajectory.source == "self_play_rl"
                        else "demonstrator_seat")
    if type(seat) is not int or seat not in (0, 1):
        raise ValueError("replay must identify its policy seat or learner seat")
    if trajectory.source == "policy_evaluation":
        checkpoint_sha256 = metadata.get("policy_checkpoint_sha256")
        if (not isinstance(checkpoint_sha256, str)
                or re.fullmatch(r"[0-9a-f]{64}", checkpoint_sha256) is None):
            raise ValueError("policy replay must identify its checkpoint SHA-256")
    candidates: list[ReviewCandidate] = []
    card_races = card_races or {}
    weak_flip_attacks = weak_flip_attacks or {}
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
        if (selected.kind == "normal_summon"
                and (code := selected.parameters.get("code")) in weak_flip_attacks
                and any(a.kind == "set_monster"
                        and a.parameters.get("code") == code
                        for a in record.legal_actions)):
            found.append(("weak_flip_normal_summon_with_set_available",
                          {"card_code": code,
                           "printed_attack": weak_flip_attacks[code]}))
        if (_is_action(selected, "chain", TRIBE_INFECTING_VIRUS)
                and can_pass and not any(c.zone == "monster"
                                     and c.position == "faceup"
                                     for c in opposing)):
            found.append(("tribe_activation_without_visible_enemy",
                          {"own_monsters": len(own_monsters),
                           "visible_enemy_monsters": 0}))
        if (selected.kind == "announce_race" and obs.chain
                and obs.chain[-1].card_code == TRIBE_INFECTING_VIRUS
                and obs.chain[-1].controller == seat):
            race = selected.parameters.get("race")
            own_hits = sum(visible_monster_race(c, card_races) == race
                           for c in own_monsters)
            enemy_hits = sum(visible_monster_race(c, card_races) == race
                             for c in enemy_monsters)
            enemy_races_offered = {visible_monster_race(c, card_races)
                                   for c in enemy_monsters
                                   if visible_monster_race(c, card_races) is not None
                                   and any(a.kind == "announce_race"
                                           and a.parameters.get("race") ==
                                           visible_monster_race(c, card_races)
                                           for a in record.legal_actions)}
            if own_hits and not enemy_hits and enemy_races_offered:
                found.append(("tribe_race_hits_only_own_with_enemy_option",
                              {"race": race, "own_hits": own_hits,
                               "visible_enemy_hits": 0,
                               "enemy_race_options": len(enemy_races_offered)}))
            elif own_hits and not enemy_hits:
                found.append(("tribe_race_hits_only_own_no_enemy_option",
                              {"race": race, "own_hits": own_hits,
                               "visible_enemy_hits": 0,
                               "enemy_race_options": 0}))
        if (selected.kind == "select_card" and obs.chain
                and obs.chain[-1].controller == seat
                and selected.parameters.get("controller") == seat
                and any(a.kind == "select_card"
                        and a.parameters.get("controller") != seat
                        for a in record.legal_actions)):
            source = obs.chain[-1].card_code
            if (source == BLACK_LUSTER_SOLDIER
                    and selected.parameters.get("code") == source
                    and selected.parameters.get("location") == obs.chain[-1].location
                    and selected.parameters.get("sequence") == obs.chain[-1].sequence):
                found.append(("bls_targets_itself_with_enemy_option",
                              {"source_card_code": source}))
            elif source == MYSTICAL_SPACE_TYPHOON:
                found.append(("mst_targets_own_card_with_enemy_option",
                              {"source_card_code": source}))
            elif source == BREAKER_THE_MAGICAL_WARRIOR:
                found.append(("breaker_targets_own_card_with_enemy_option",
                              {"source_card_code": source}))
            elif source == RING_OF_DESTRUCTION:
                safe_enemy_targets = sum(
                    a.kind == "select_card" and a.parameters.get("controller") != seat
                    and any(c.zone == "monster" and c.position == "faceup"
                            and c.controller != seat
                            and c.sequence == a.parameters.get("sequence")
                            and c.attack is not None
                            and c.attack < obs.life_points[seat]
                            for c in enemy_monsters)
                    for a in record.legal_actions)
                if safe_enemy_targets:
                    found.append(("ring_targets_own_with_safe_enemy_option",
                                  {"safe_enemy_targets": safe_enemy_targets}))
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
            if category.startswith("scapegoat_pass_"):
                if key in seen:
                    continue
                seen.add(key)
            candidates.append(ReviewCandidate(
                index, category, obs.turn, obs.phase, seat, evidence))
    return tuple(candidates)


def category_counts(candidates: tuple[ReviewCandidate, ...]) -> dict[str, int]:
    return dict(sorted(Counter(c.category for c in candidates).items()))


def sampled_self_play_provenance(trajectory: Trajectory,
                                 checkpoint_sha256: str | None = None) -> dict:
    """Validate exploratory learner provenance without claiming choice reproduction.

    A sampled action need not equal its parent's greedy choice. The full duel
    and visible observations must still be verified by the caller.
    """
    if trajectory.source != "self_play_rl":
        raise ValueError("sampled provenance requires a self_play_rl trajectory")
    metadata = trajectory.skill_metadata or {}
    seat = metadata.get("learner_seat")
    parent = metadata.get("parent_checkpoint_sha256")
    temperature = metadata.get("learner_temperature")
    if type(seat) is not int or seat not in (0, 1):
        raise ValueError("self-play replay must identify learner seat")
    if not isinstance(parent, str) or re.fullmatch(r"[0-9a-f]{64}", parent) is None:
        raise ValueError("self-play replay must identify parent checkpoint SHA-256")
    if checkpoint_sha256 is not None and parent != checkpoint_sha256:
        raise ValueError("parent checkpoint SHA-256 differs from recording")
    if metadata.get("learner_action_selection") != "sampled_softmax":
        raise ValueError("unsupported self-play action selection")
    if (type(temperature) not in (int, float) or not isfinite(temperature)
            or temperature <= 0):
        raise ValueError("self-play replay must record a positive finite temperature")
    return {"policy_seat": seat, "checkpoint_sha256": parent,
            "selection_mode": "sampled_softmax", "selection_temperature": temperature,
            "choice_verification": "not_reproduced_exploratory_sampling",
            "verified_policy_choices": None}
