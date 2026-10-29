"""Conservative, player-visible prompts for human review of policy replays.

These are candidates, not automatic play labels or evidence of a rules error.
"""

import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from math import isfinite

from goat_ai.actions import Action
from goat_ai.agents.tactical_guard import (
    safe_own_one_shot_response_indices,
    visible_monster_race,
)
from goat_ai.replay import Trajectory

HEAVY_STORM = 19613556
NOBLEMAN_OF_CROSSOUT = 504700116
RING_OF_DESTRUCTION = 511000824
TORRENTIAL_TRIBUTE = 53582587
BOOK_OF_MOON = 14087893
SCAPEGOAT = 504700123
ROYAL_DECREE = 51452091
SAKURETSU_ARMOR = 56120475
TRIBE_INFECTING_VIRUS = 33184167
BLACK_LUSTER_SOLDIER = 504700118
CHAOS_SORCERER = 9596126
MYSTICAL_SPACE_TYPHOON = 5318639
RAIGEKI_BREAK = 4178474
BREAKER_THE_MAGICAL_WARRIOR = 71413901
POT_OF_GREED = 55144522
THUNDER_DRAGON = 504700054
METAMORPHOSIS = 46411259
SOLEMN_JUDGMENT = 41420027
SINISTER_SERPENT = 511000818
FIELD_PERSISTENT_NORMAL_SPELLS = frozenset({
    72302403,  # Swords of Revealing Light
    11961740,  # Different Dimension Capsule
})


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


def thunder_search_count(action: Action, seat: int) -> int:
    """Count Thunder Dragons offered by either native search prompt shape."""
    if action.kind == "select_cards":
        return sum(card.get("code") == THUNDER_DRAGON
                   for card in action.parameters.get("cards", ()))
    if (action.kind == "select_card"
            and action.parameters.get("code") == THUNDER_DRAGON
            and action.parameters.get("location") == 1
            and action.parameters.get("controller") == seat):
        return 1
    return 0


def review_candidates(trajectory: Trajectory,
                      card_races: Mapping[int, int] | None = None,
                      weak_flip_attacks: Mapping[int, int] | None = None,
                      review_seat: int | None = None,
                      card_facts: Mapping[int, tuple[int, int, int]] | None = None,
                      ) -> tuple[ReviewCandidate, ...]:
    """Flag selected actions of one seat using only that seat's visible view.

    Repeated priority passes in the same turn and phase are reported once so
    a reviewer gets a useful shortlist. Callers must verify the source replay
    against its native assets before treating these as replay-backed findings.
    The default seat is the recorded policy or learner; an explicit other
    seat supports separate review of the evaluation opponent.
    """
    if trajectory.source not in ("policy_evaluation", "self_play_rl", "tactical",
                                 "local_ai_match"):
        raise ValueError("review candidates require a verified AI replay")
    metadata = trajectory.skill_metadata or {}
    seat = (review_seat if trajectory.source == "local_ai_match" else
            metadata.get("learner_seat" if trajectory.source == "self_play_rl"
                         else "demonstrator_seat"))
    if type(seat) is not int or seat not in (0, 1):
        raise ValueError("replay must identify its policy seat or learner seat, "
                         "or pass a review seat")
    if review_seat is not None:
        if type(review_seat) is not int or review_seat not in (0, 1):
            raise ValueError("review seat must be player 0 or 1")
        seat = review_seat
    if trajectory.source == "policy_evaluation":
        checkpoint_sha256 = metadata.get("policy_checkpoint_sha256")
        if (not isinstance(checkpoint_sha256, str)
                or re.fullmatch(r"[0-9a-f]{64}", checkpoint_sha256) is None):
            raise ValueError("policy replay must identify its checkpoint SHA-256")
    if trajectory.source == "tactical" and (
            metadata.get("teacher") != "TacticalHeuristicAgent"
            or type(metadata.get("teacher_version")) is not int
            or metadata["teacher_version"] < 1):
        raise ValueError("tactical replay must identify its teacher version")
    candidates: list[ReviewCandidate] = []
    card_races = card_races or {}
    weak_flip_attacks = weak_flip_attacks or {}
    card_facts = card_facts or {}
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
        if selected.kind == "change_position":
            changed = next((card for card in own_monsters
                            if card.sequence == selected.parameters.get("sequence")), None)
            if (changed is not None and changed.position == "faceup"
                    and changed.orientation == "defense" and changed.attack == 0):
                found.append(("zero_attack_defender_changed_to_attack",
                              {"card_code": changed.code or 0,
                               "current_defense": changed.defense or 0}))
            if (changed is not None and changed.position == "faceup"
                    and changed.orientation == "attack" and not enemy_monsters
                    and changed.attack is not None and changed.defense is not None
                    and changed.attack > changed.defense):
                found.append(("empty_field_attacker_changed_to_weaker_defense",
                              {"card_code": changed.code or 0,
                               "current_attack": changed.attack,
                               "new_defense": changed.defense}))
        if (_is_action(selected, "activate", POT_OF_GREED)
                and any(_is_action(a, "activate", THUNDER_DRAGON)
                        for a in record.legal_actions)):
            found.append(("pot_before_available_thunder_dragon", {"thunder_offered": 1}))
        initial_thunder = obs.own_main_deck.count(THUNDER_DRAGON)
        known_thunder_outside_deck = (
            sum(card.code == THUNDER_DRAGON for card in obs.hand)
            + sum(card.code == THUNDER_DRAGON for card in obs.graveyards[seat])
            + sum(card.code == THUNDER_DRAGON for card in obs.banished[seat])
            + sum(card.code == THUNDER_DRAGON and card.owner == seat
                  for card in obs.field)
        )
        if (selected.kind == "end_phase" and obs.phase in ("main1", "main2")
                and obs.turn_player == seat
                and initial_thunder > known_thunder_outside_deck
                and any(_is_action(a, "activate", THUNDER_DRAGON)
                        for a in record.legal_actions)):
            found.append(("end_turn_with_activatable_thunder_dragon", {
                "thunder_in_hand": sum(card.code == THUNDER_DRAGON for card in obs.hand),
                "initial_thunder_copies": initial_thunder,
            }))
        if (selected.kind == "select_cards" and not selected.parameters.get("cards")
                and obs.chain and obs.chain[-1].card_code == THUNDER_DRAGON
                and obs.chain[-1].controller == seat):
            available = max((thunder_search_count(action, seat)
                             for action in record.legal_actions), default=0)
            if available:
                found.append(("thunder_empty_search_with_copies_available",
                              {"maximum_selectable_copies": available}))
        if (selected.kind == "select_card" and obs.chain
                and obs.chain[-1].card_code == METAMORPHOSIS
                and obs.chain[-1].controller == seat
                and selected.parameters.get("code") in weak_flip_attacks
                and not enemy_monsters):
            found.append(("metamorphosis_spends_weak_flip_on_empty_enemy_field",
                          {"card_code": selected.parameters["code"]}))
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
        elif (_is_action(selected, "activate", HEAVY_STORM)
              and enemy_backrow <= own_other_backrow):
            found.append(("heavy_storm_negative_visible_trade",
                          {"own_other_backrow": own_other_backrow,
                           "enemy_backrow": enemy_backrow}))
        if (_is_action(selected, "activate", NOBLEMAN_OF_CROSSOUT)
                and any(c.zone == "monster" and c.position == "facedown"
                        for c in own_monsters)
                and not any(c.zone == "monster" and c.position == "facedown"
                            for c in enemy_monsters)):
            found.append(("nobleman_only_own_set_monster",
                          {"own_set_monsters": sum(c.position == "facedown"
                                                   for c in own_monsters),
                           "enemy_set_monsters": 0}))
        if (selected.kind in ("activate", "chain") and can_pass
                and selected.parameters.get("code") == BREAKER_THE_MAGICAL_WARRIOR
                and own_backrow and not enemy_backrow):
            found.append(("breaker_activates_with_only_own_backrow",
                          {"own_backrow": own_backrow, "enemy_backrow": 0}))
        if (selected.kind in ("activate", "chain") and can_pass
                and selected.parameters.get("code") in (
                    BLACK_LUSTER_SOLDIER, CHAOS_SORCERER)
                and not enemy_monsters
                and any(c.zone == "monster" and c.controller == seat
                        and c.sequence == selected.parameters.get("sequence")
                        and c.code == selected.parameters.get("code")
                        and c.owner == seat for c in own_monsters)):
            found.append(("owned_chaos_boss_activates_without_enemy_monster",
                          {"source_card_code": selected.parameters["code"],
                           "enemy_monsters": 0}))
        if (selected.kind in ("activate", "chain") and not obs.chain
                and obs.turn_player == seat and len(record.legal_actions) > 1):
            source_is_set = (selected.parameters.get("location") == 8
                             and any(c.zone == "spell_trap"
                                     and c.sequence == selected.parameters.get("sequence")
                                     and c.code == selected.parameters.get("code")
                                     for c in own))
            own_other_backrow = own_backrow - int(source_is_set)
            if (selected.parameters.get("code") == MYSTICAL_SPACE_TYPHOON
                    and own_other_backrow > 0 and enemy_backrow == 0):
                found.append(("mst_idle_only_own_backrow",
                              {"own_other_backrow": own_other_backrow}))
            if (selected.parameters.get("code") == RAIGEKI_BREAK
                    and own_other_backrow + len(own_monsters) > 0
                    and enemy_backrow + len(enemy_monsters) == 0):
                found.append(("raigeki_break_idle_only_own_field",
                              {"own_field_targets": own_other_backrow
                               + len(own_monsters)}))
        if (selected.kind == "chain"
                and selected.parameters.get("code") == MYSTICAL_SPACE_TYPHOON
                and can_pass and selected not in tuple(
                    record.legal_actions[i] for i in safe_own_one_shot_response_indices(
                        obs, record.legal_actions,
                        range(len(record.legal_actions)), card_facts))):
            found.append(("mst_chains_to_own_one_shot_only",
                          {"chain_source_code": obs.chain[-1].card_code}))
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
        if (_is_action(selected, "activate", RING_OF_DESTRUCTION)
                and obs.turn_player == seat and not obs.chain
                and len(record.legal_actions) > 1
                and not any(c.position == "faceup" for c in enemy_monsters)):
            visible_own = [c for c in own_monsters if c.position == "faceup"]
            if (visible_own and all(c.attack is not None
                                    and c.attack < obs.life_points[1 - seat]
                                    for c in visible_own)):
                found.append(("ring_idle_only_own_faceup",
                              {"own_faceup_monsters": len(visible_own),
                               "opponent_life_points": obs.life_points[1 - seat]}))
        if (_is_action(selected, "chain", SOLEMN_JUDGMENT) and can_pass
                and obs.chain and obs.chain[-1].card_code == SCAPEGOAT
                and obs.chain[-1].controller != seat):
            found.append(("solemn_on_opponent_scapegoat",
                          {"own_life_points": obs.life_points[seat]}))
        if (_is_action(selected, "chain", SOLEMN_JUDGMENT) and can_pass
                and obs.pending_summon is not None
                and obs.pending_summon.controller != seat
                and obs.pending_summon.code == SINISTER_SERPENT):
            found.append(("solemn_on_opponent_sinister_serpent_summon",
                          {"own_life_points": obs.life_points[seat],
                           "summoned_card_code": SINISTER_SERPENT}))
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
            if (source in (BLACK_LUSTER_SOLDIER, CHAOS_SORCERER)
                    and selected.parameters.get("code") == source
                    and selected.parameters.get("location") == obs.chain[-1].location
                    and selected.parameters.get("sequence") == obs.chain[-1].sequence):
                category = ("bls_targets_itself_with_enemy_option"
                            if source == BLACK_LUSTER_SOLDIER else
                            "chaos_sorcerer_targets_itself_with_enemy_option")
                found.append((category,
                              {"source_card_code": source}))
            elif source == MYSTICAL_SPACE_TYPHOON:
                found.append(("mst_targets_own_card_with_enemy_option",
                              {"source_card_code": source}))
            elif source == RAIGEKI_BREAK:
                found.append(("raigeki_break_targets_own_card_with_enemy_option",
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
        if (selected.kind == "select_card" and obs.chain
                and obs.chain[-1].card_code == BOOK_OF_MOON
                and obs.chain[-1].controller == seat
                and any(link.card_code == TORRENTIAL_TRIBUTE
                        for link in obs.chain[:-1])
                and selected.parameters.get("location") == 4):
            target = next((card for card in obs.field
                           if card.zone == "monster"
                           and card.controller == selected.parameters.get("controller")
                           and card.sequence == selected.parameters.get("sequence")), None)
            if target is not None:
                found.append(("book_targets_monster_under_torrential",
                              {"target_code": target.code or 0,
                               "target_controller": target.controller,
                               "torrential_chain_links": sum(
                                   link.card_code == TORRENTIAL_TRIBUTE
                                   for link in obs.chain[:-1])}))
        if (selected.kind == "select_card" and obs.chain
                and obs.chain[-1].controller == seat
                and obs.chain[-1].card_code == BREAKER_THE_MAGICAL_WARRIOR
                and selected.parameters.get("controller") == seat
                and selected.parameters.get("location") == 8
                and enemy_backrow == 0
                and any(card.controller == seat and card.zone == "spell_trap"
                        and card.sequence == selected.parameters.get("sequence")
                        for card in obs.field)):
            found.append(("breaker_targets_only_own_backrow",
                          {"own_backrow": own_backrow, "enemy_backrow": 0}))
        if (selected.kind == "select_card" and obs.chain
                and obs.chain[-1].controller == seat
                and obs.chain[-1].card_code in (MYSTICAL_SPACE_TYPHOON, RAIGEKI_BREAK)
                and selected.parameters.get("location") == 8):
            target = next((link for link in obs.chain[:-1]
                           if (link.controller == selected.parameters.get("controller")
                               and link.location == selected.parameters.get("location")
                               and link.sequence == selected.parameters.get("sequence"))), None)
            target_type = card_facts.get(target.card_code, (0, 0, 0))[0] if target else 0
            # The pinned database stores Normal Spells/Traps as bare TYPE_SPELL
            # or TYPE_TRAP. Swords and Capsule are Normal Spells that remain
            # face-up after resolution, so destruction can still matter.
            nonpersistent = (target is not None
                             and target_type in (0x2, 0x4, 0x2 | 0x10000)
                             and target.card_code not in FIELD_PERSISTENT_NORMAL_SPELLS)
            if (target is not None and nonpersistent
                    and any(card.controller == target.controller
                            and card.zone == "spell_trap" and card.sequence == target.sequence
                            and card.position == "faceup" for card in obs.field)):
                found.append(("removal_targets_resolving_one_shot_spell_trap", {
                    "removal_code": obs.chain[-1].card_code,
                    "target_code": target.card_code,
                }))
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


def compare_parent_greedy_candidates(
    trajectory: Trajectory, candidates: tuple[ReviewCandidate, ...], agent,
    card_races: Mapping[int, int] | None = None,
    weak_flip_attacks: Mapping[int, int] | None = None,
    card_facts: Mapping[int, tuple[int, int, int]] | None = None,
) -> tuple[dict, ...]:
    """Diagnose sampled flags using a frozen parent's greedy choice at that view.

    A self-play policy may change after each rollout. This checks the supplied
    parent checkpoint on recorded visible states, not the exact sampling policy
    that generated every action or a counterfactual game outcome.
    """
    if trajectory.source != "self_play_rl":
        raise ValueError("frozen-parent comparison requires sampled self-play")
    result = []
    for candidate in candidates:
        record = trajectory.decisions[candidate.decision_index]
        greedy = agent.select_action(record.observation, record.legal_actions)
        if greedy not in record.legal_actions:
            raise ValueError("parent selected an action outside the visible legal set")
        one_decision = replace(
            trajectory, decisions=(replace(record, selected_action=greedy),))
        flags = review_candidates(one_decision, card_races, weak_flip_attacks,
                                  card_facts=card_facts)
        categories = sorted({flag.category for flag in flags})
        result.append({
            "decision_index": candidate.decision_index,
            "sampled_category": candidate.category,
            "parent_greedy_same_action": greedy == record.selected_action,
            "parent_greedy_action_kind": greedy.kind,
            "parent_greedy_flagged_categories": categories,
            "parent_greedy_same_category_flagged": candidate.category in categories,
        })
    return tuple(result)


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
    progress_mask = metadata.get("selection_progress_mask", 0)
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
    if type(progress_mask) is not int or progress_mask not in (0, 1):
        raise ValueError("unsupported self-play selection progress mask")
    if progress_mask == 1:
        for index, decision in enumerate(trajectory.decisions):
            if decision.observation.acting_player != seat:
                continue
            if (decision.selected_action.kind == "unselect_card"
                    and any(action.kind in ("select_card", "finish_selection")
                            for action in decision.legal_actions)):
                raise ValueError(f"selection progress mask violated at decision {index}")
    return {"policy_seat": seat, "checkpoint_sha256": parent,
            "selection_mode": ("sampled_softmax_progress_mask_v1" if progress_mask
                               else "sampled_softmax"),
            "selection_progress_mask": progress_mask,
            "selection_temperature": temperature,
            "choice_verification": "not_reproduced_exploratory_sampling",
            "verified_policy_choices": None}
