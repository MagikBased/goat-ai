"""Derive replay-verified synthetic preferences from player-visible decisions.

These labels are automated hypotheses, not human reviews or winning-move
claims. Keep the output separate from human annotations and evaluate a trained
child on held-out decks before using it as a reference policy.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from goat_ai.agents.card_metadata import load_card_facts, load_weak_flip_monster_attack
from goat_ai.agents.tactical_guard import (
    MYSTICAL_SPACE_TYPHOON,
    safe_idle_own_ring_indices,
    safe_one_shot_response_indices,
    safe_optional_own_loss_indices,
    safe_target_indices,
)
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.evaluation.replay_review import (
    BLACK_LUSTER_SOLDIER,
    BREAKER_THE_MAGICAL_WARRIOR,
    CHAOS_SORCERER,
    HEAVY_STORM,
    NOBLEMAN_OF_CROSSOUT,
    THUNDER_DRAGON,
    TORRENTIAL_TRIBUTE,
    TRIBE_INFECTING_VIRUS,
    review_candidates,
    thunder_search_count,
)
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_decision_preferences, read_trajectory, verify_trajectory
from goat_ai.replay.fingerprint import sha256_file

RULE_SET_ID = "visible_audit_v1"
RULE_SET_V2 = "visible_audit_v2"
RULE_SET_V3 = "visible_resource_v3"
RULE_SET_V4 = "visible_material_choices_v4"
RULE_SET_V5 = "visible_material_avoidance_v5"
RULE_SET_V6 = "visible_optional_own_loss_v6"
RULE_SET_V7 = "visible_guard_distillation_v7"
RULE_SET_V8 = "visible_residual_guard_distillation_v8"
RULE_SET_V9 = "visible_optional_own_loss_v9"
RULE_SET_V10 = "visible_selected_own_loss_v10"
RULE_SET_V11 = "visible_selected_own_loss_with_responses_v11"
RULE_SET_V12 = "visible_selected_own_loss_with_own_mst_v12"
SUPPORTED_CATEGORIES_V1 = frozenset({
    "bls_targets_itself_with_enemy_option",
    "chaos_sorcerer_targets_itself_with_enemy_option",
    "thunder_empty_search_with_copies_available",
    "weak_flip_normal_summon_with_set_available",
    "pot_before_available_thunder_dragon",
    "ring_targets_own_with_safe_enemy_option",
})
SUPPORTED_CATEGORIES_V2 = SUPPORTED_CATEGORIES_V1 | {
    "nobleman_only_own_set_monster",
    "raigeki_break_targets_own_card_with_enemy_option",
}


def preferred_indices(record, category: str) -> list[int]:
    """Return legal alternatives justified by one player-visible audit flag."""
    seat = record.observation.acting_player
    actions = record.legal_actions
    if category in ("bls_targets_itself_with_enemy_option",
                    "chaos_sorcerer_targets_itself_with_enemy_option"):
        return [i for i, action in enumerate(actions)
                if action.kind == "select_card"
                and action.parameters.get("location") == 4
                and action.parameters.get("controller") == 1 - seat]
    if category == "thunder_empty_search_with_copies_available":
        counts = [thunder_search_count(action, seat) for action in actions]
        maximum = max(counts, default=0)
        return [i for i, count in enumerate(counts) if count == maximum] if maximum else []
    if category == "weak_flip_normal_summon_with_set_available":
        code = record.selected_action.parameters.get("code")
        return [i for i, action in enumerate(actions)
                if action.kind == "set_monster" and action.parameters.get("code") == code]
    if category == "pot_before_available_thunder_dragon":
        return [i for i, action in enumerate(actions)
                if action.kind == "activate" and action.parameters.get("code") == THUNDER_DRAGON]
    if category == "ring_targets_own_with_safe_enemy_option":
        enemy = {card.sequence: card for card in record.observation.field
                 if card.controller == 1 - seat and card.zone == "monster"
                 and card.position == "faceup"}
        return [i for i, action in enumerate(actions)
                if action.kind == "select_card"
                and action.parameters.get("controller") == 1 - seat
                and action.parameters.get("location") == 4
                and (card := enemy.get(action.parameters.get("sequence"))) is not None
                and card.attack is not None
                and card.attack < record.observation.life_points[seat]]
    if category == "nobleman_only_own_set_monster":
        phase_action = "battle_phase" if record.observation.phase == "main1" \
            else "end_phase"
        return [i for i, action in enumerate(actions) if action.kind == phase_action]
    if category == "raigeki_break_targets_own_card_with_enemy_option":
        return [i for i, action in enumerate(actions)
                if action.kind == "select_card"
                and action.parameters.get("controller") == 1 - seat
                and action.parameters.get("location") in (4, 8)]
    return []


def derive(trajectory, candidates, *, rule_set_id: str = RULE_SET_ID,
           card_facts=None
           ) -> tuple[list[dict], Counter]:
    """Keep one unambiguous automated comparison per recorded decision."""
    if rule_set_id == RULE_SET_V12:
        if card_facts is None:
            raise ValueError("v12 own-MST labels require printed card facts")
        existing, counts = derive(trajectory, candidates, rule_set_id=RULE_SET_V11,
                                  card_facts=card_facts)
        seat = (trajectory.skill_metadata or {}).get(
            "learner_seat" if trajectory.source == "self_play_rl"
            else "demonstrator_seat")
        if type(seat) is not int or seat not in (0, 1):
            raise ValueError("v12 labels require a recorded policy seat")
        seen = {item["decision_index"] for item in existing}
        additions = []
        for index, record in enumerate(trajectory.decisions):
            obs, chosen = record.observation, record.selected_action
            if (index in seen or obs.acting_player != seat
                    or chosen.kind not in ("activate", "chain")
                    or chosen.parameters.get("code") != MYSTICAL_SPACE_TYPHOON):
                continue
            own_mst_slot = (chosen.parameters.get("sequence")
                            if chosen.parameters.get("location") == 8 else None)
            other_backrow = [card for card in obs.field
                             if card.zone == "spell_trap"
                             and not (card.controller == seat
                                      and card.sequence == own_mst_slot
                                      and card.code == MYSTICAL_SPACE_TYPHOON)]
            if (len(other_backrow) != 1
                    or other_backrow[0].controller != seat
                    or other_backrow[0].position != "faceup"
                    or other_backrow[0].code is None
                    or card_facts.get(other_backrow[0].code, (0, 0, 0))[0]
                    not in (2, 4, 0x10002)):
                continue
            preferred = [i for i, action in enumerate(record.legal_actions)
                         if action.kind == "pass"]
            if not preferred:
                continue
            additions.append({"decision_index": index,
                              "preferred_action_indices": preferred,
                              "disfavored_action_indices": [
                                  record.legal_actions.index(chosen)]})
        counts["selected_own_faceup_mst"] = len(additions)
        return sorted(existing + additions, key=lambda item: item["decision_index"]), counts
    if rule_set_id == RULE_SET_V10:
        comparisons, _ = derive(trajectory, candidates, rule_set_id=RULE_SET_V9)
        selected_bad = [item for item in comparisons if trajectory.decisions[
            item["decision_index"]].legal_actions.index(trajectory.decisions[
                item["decision_index"]].selected_action) in item[
                    "disfavored_action_indices"]]
        return selected_bad, Counter({"selected_own_loss": len(selected_bad)})
    if rule_set_id == RULE_SET_V11:
        if card_facts is None:
            raise ValueError("v11 selected response labels require printed card facts")
        optional, _ = derive(trajectory, candidates, rule_set_id=RULE_SET_V10)
        response, _ = derive(trajectory, candidates, rule_set_id=RULE_SET_V8,
                             card_facts=card_facts)
        seen = {item["decision_index"] for item in optional}
        selected_response = [item for item in response if item["decision_index"] not in seen
                             and trajectory.decisions[item["decision_index"]]
                             .legal_actions.index(trajectory.decisions[
                                 item["decision_index"]].selected_action)
                             in item["disfavored_action_indices"]]
        return sorted(optional + selected_response,
                      key=lambda item: item["decision_index"]), Counter({
                          "selected_own_loss": len(optional),
                          "selected_ring_or_mst_response": len(selected_response)})
    if rule_set_id == RULE_SET_V7:
        return derive_guard_distillation(trajectory)
    if rule_set_id == RULE_SET_V8:
        if card_facts is None:
            raise ValueError("v8 residual guard labels require printed card facts")
        return derive_residual_guard_distillation(trajectory, card_facts)
    if rule_set_id == RULE_SET_V3:
        return derive_resource_counterfactuals(trajectory)
    if rule_set_id in (RULE_SET_V4, RULE_SET_V5, RULE_SET_V6, RULE_SET_V9):
        resource, resource_counts = derive_resource_counterfactuals(
            trajectory, all_safe_alternatives=rule_set_id in (RULE_SET_V5,
                                                               RULE_SET_V6,
                                                               RULE_SET_V9),
            optional_own_loss=rule_set_id in (RULE_SET_V6, RULE_SET_V9),
            ability_activate=rule_set_id == RULE_SET_V9)
        target, target_counts = derive_material_choice_counterfactuals(trajectory)
        overlap = {item["decision_index"] for item in resource} & {
            item["decision_index"] for item in target}
        if overlap:
            raise ValueError("resource and target comparisons overlap")
        return sorted(resource + target, key=lambda item: item["decision_index"]), (
            resource_counts + target_counts)
    categories = {RULE_SET_ID: SUPPORTED_CATEGORIES_V1,
                  RULE_SET_V2: SUPPORTED_CATEGORIES_V2}.get(rule_set_id)
    if categories is None:
        raise ValueError("unsupported visible audit rule set")
    result = []
    counts = Counter()
    seen = set()
    for candidate in candidates:
        if candidate.category not in categories \
                or candidate.decision_index in seen:
            continue
        record = trajectory.decisions[candidate.decision_index]
        disfavored = record.legal_actions.index(record.selected_action)
        preferred = sorted(set(preferred_indices(record, candidate.category)) - {disfavored})
        if not preferred:
            continue
        result.append({"decision_index": candidate.decision_index,
                       "preferred_action_indices": preferred,
                       "disfavored_action_indices": [disfavored]})
        counts[candidate.category] += 1
        seen.add(candidate.decision_index)
    return result, counts


def derive_guard_distillation(trajectory) -> tuple[list[dict], Counter]:
    """Distill exactly the opt-in visible own-loss guard's legal-action mask.

    Every preference partitions the entire offered set. This is an automated
    inference rule, not a claim that any surviving action is optimal.
    """
    metadata = trajectory.skill_metadata or {}
    seat = metadata.get("learner_seat" if trajectory.source == "self_play_rl"
                        else "demonstrator_seat")
    if type(seat) is not int or seat not in (0, 1):
        raise ValueError("guard distillation requires a recorded policy seat")
    result = []
    counts = Counter()
    for index, record in enumerate(trajectory.decisions):
        if record.observation.acting_player != seat or len(record.legal_actions) < 2:
            continue
        legal = record.legal_actions
        activation_kept = safe_optional_own_loss_indices(
            record.observation, legal, range(len(legal)))
        kept = safe_target_indices(record.observation, legal, activation_kept,
                                   protect_removal_targets=True)
        if len(kept) == len(legal):
            continue
        good = sorted(kept)
        bad = [choice for choice in range(len(legal)) if choice not in kept]
        result.append({"decision_index": index,
                       "preferred_action_indices": good,
                       "disfavored_action_indices": bad})
        counts["activation" if len(activation_kept) < len(legal) else "target"] += 1
    return result, counts


def derive_residual_guard_distillation(trajectory, card_facts) -> tuple[list[dict], Counter]:
    """Label only the extra action removals from the opt-in v5 versus v1 guard.

    All v5 survivors are acceptable in this synthetic comparison; none is
    asserted to be the best play or to win the duel.
    """
    metadata = trajectory.skill_metadata or {}
    seat = metadata.get("learner_seat" if trajectory.source == "self_play_rl"
                        else "demonstrator_seat")
    if type(seat) is not int or seat not in (0, 1):
        raise ValueError("residual guard distillation requires a recorded policy seat")
    result = []
    counts = Counter()
    for index, record in enumerate(trajectory.decisions):
        if record.observation.acting_player != seat or len(record.legal_actions) < 2:
            continue
        obs, legal = record.observation, record.legal_actions
        base = safe_optional_own_loss_indices(obs, legal, range(len(legal)))
        v1 = safe_target_indices(obs, legal, base, protect_removal_targets=True)
        one_shot = safe_one_shot_response_indices(obs, legal, base, card_facts)
        ring = safe_idle_own_ring_indices(obs, legal, one_shot)
        v5 = safe_target_indices(obs, legal, ring, protect_removal_targets=True)
        if not set(v5) <= set(v1):
            raise ValueError("v5 unexpectedly expanded the v1 action set")
        removed = sorted(set(v1) - set(v5))
        if not removed:
            continue
        chosen = legal.index(record.selected_action)
        if chosen not in (*v5, *removed):
            continue
        result.append({"decision_index": index,
                       "preferred_action_indices": sorted(v5),
                       "disfavored_action_indices": removed})
        counts["one_shot_mst" if any(choice not in one_shot for choice in removed)
               else "idle_own_ring"] += 1
    return result, counts


def derive_resource_counterfactuals(trajectory, *, all_safe_alternatives: bool = False,
                                   optional_own_loss: bool = False,
                                   ability_activate: bool = False,
                                   ) -> tuple[list[dict], Counter]:
    """Compare a visited safe choice or phase transition with visible resource loss.

    The chosen action can be on either side of the comparison. The opponent's
    Set-card identity and the simulator's private state are never inspected.
    """
    metadata = trajectory.skill_metadata or {}
    seat = metadata.get("learner_seat" if trajectory.source == "self_play_rl"
                        else "demonstrator_seat")
    if type(seat) is not int or seat not in (0, 1):
        raise ValueError("resource comparisons require a recorded policy seat")
    result = []
    counts = Counter()
    seen_contexts = set()
    for index, record in enumerate(trajectory.decisions):
        obs = record.observation
        if obs.acting_player != seat:
            continue
        own_main = (obs.turn_player == seat and obs.phase in ("main1", "main2"))
        if not own_main and not optional_own_loss:
            continue
        own_sets = any(card.controller == seat and card.zone == "monster"
                       and card.position == "facedown" for card in obs.field)
        enemy_sets = any(card.controller != seat and card.zone == "monster"
                         and card.position == "facedown" for card in obs.field)
        own_backrow = [card for card in obs.field
                       if card.controller == seat and card.zone == "spell_trap"]
        enemy_backrow_count = sum(card.controller != seat
                                  and card.zone == "spell_trap" for card in obs.field)
        bad = []
        categories = set()
        for action_index, action in enumerate(record.legal_actions):
            code = action.parameters.get("code")
            if (own_main and action.kind == "activate"
                    and code == NOBLEMAN_OF_CROSSOUT and own_sets and not enemy_sets):
                bad.append(action_index)
                categories.add("nobleman_only_own_set_monster")
            elif own_main and action.kind == "activate" and code == HEAVY_STORM:
                source_is_set = action.parameters.get("location") == 8 and any(
                    card.sequence == action.parameters.get("sequence")
                    and card.code == HEAVY_STORM for card in own_backrow)
                own_other_backrow = len(own_backrow) - int(source_is_set)
                if enemy_backrow_count <= own_other_backrow:
                    bad.append(action_index)
                    categories.add("heavy_storm_negative_visible_trade")
            elif optional_own_loss and (action.kind == "chain"
                                        or (ability_activate and action.kind == "activate")):
                if code == BREAKER_THE_MAGICAL_WARRIOR and own_backrow \
                        and enemy_backrow_count == 0:
                    bad.append(action_index)
                    categories.add("breaker_only_own_backrow")
                elif code in (BLACK_LUSTER_SOLDIER, CHAOS_SORCERER):
                    own_boss = any(card.controller == seat and card.owner == seat
                                   and card.zone == "monster" and card.position == "faceup"
                                   and card.code == code for card in obs.field)
                    enemy_monsters = any(card.controller != seat
                                         and card.zone == "monster" for card in obs.field)
                    if own_boss and not enemy_monsters:
                        bad.append(action_index)
                        categories.add("boss_only_own_monsters")
                elif code == TRIBE_INFECTING_VIRUS:
                    enemy_faceup = any(card.controller != seat
                                       and card.zone == "monster"
                                       and card.position == "faceup" for card in obs.field)
                    if not enemy_faceup:
                        bad.append(action_index)
                        categories.add("tribe_no_visible_enemy")
                elif code == TORRENTIAL_TRIBUTE:
                    own_monsters = any(card.controller == seat and card.zone == "monster"
                                       for card in obs.field)
                    enemy_monsters = any(card.controller != seat
                                         and card.zone == "monster" for card in obs.field)
                    if own_monsters and not enemy_monsters:
                        bad.append(action_index)
                        categories.add("torrential_only_own_monsters")
        if not bad:
            continue
        selected = record.legal_actions.index(record.selected_action)
        if all_safe_alternatives:
            preferred = [i for i in range(len(record.legal_actions)) if i not in bad]
        elif selected not in bad:
            preferred = [selected]
        else:
            if own_main:
                phase_kind = "battle_phase" if obs.phase == "main1" else "end_phase"
                preferred = [i for i, action in enumerate(record.legal_actions)
                             if action.kind == phase_kind]
            else:
                preferred = [i for i, action in enumerate(record.legal_actions)
                             if action.kind == "pass"]
        if not preferred:
            continue
        # Priority passes can revisit a near-identical resource choice many
        # times in one turn. Count each visible trade and chosen side once.
        context = (obs.turn, obs.phase, tuple(sorted(categories)),
                   len(own_backrow), enemy_backrow_count, own_sets, enemy_sets,
                   tuple(sorted((record.legal_actions[i].parameters.get("code"),
                                 record.legal_actions[i].parameters.get("location") == 8)
                                for i in bad)), selected in bad)
        if context in seen_contexts:
            continue
        seen_contexts.add(context)
        result.append({"decision_index": index,
                       "preferred_action_indices": preferred,
                       "disfavored_action_indices": bad})
        counts.update(categories)
    return result, counts


def derive_material_choice_counterfactuals(trajectory) -> tuple[list[dict], Counter]:
    """Compare clear target or Type choices after an effect was activated.

    These are visible, rule-derived hypotheses. They do not say whether the
    effect should have been activated in the first place or account for card
    quality, delayed effects, or a future control change.
    """
    metadata = trajectory.skill_metadata or {}
    seat = metadata.get("learner_seat" if trajectory.source == "self_play_rl"
                        else "demonstrator_seat")
    if type(seat) is not int or seat not in (0, 1):
        raise ValueError("material comparisons require a recorded policy seat")
    result = []
    counts = Counter()
    for index, record in enumerate(trajectory.decisions):
        obs = record.observation
        if obs.acting_player != seat or not obs.chain:
            continue
        source = obs.chain[-1]
        if source.controller != seat:
            continue
        chosen = record.legal_actions.index(record.selected_action)
        category = None
        preferred = []
        disfavored = []
        if source.card_code in (BLACK_LUSTER_SOLDIER, CHAOS_SORCERER):
            # A stolen boss may deliberately banish itself before returning.
            boss = next((card for card in obs.field
                         if card.zone == "monster" and card.controller == seat
                         and card.sequence == source.sequence), None)
            if boss is None or boss.owner != seat:
                continue
            for choice, action in enumerate(record.legal_actions):
                if (action.kind != "select_card"
                        or action.parameters.get("location") != 4):
                    continue
                controller = action.parameters.get("controller")
                if controller == 1 - seat:
                    preferred.append(choice)
                elif (controller == seat
                      and action.parameters.get("sequence") == source.sequence):
                    disfavored.append(choice)
            category = "boss_self_banish_vs_enemy"
        elif source.card_code == TRIBE_INFECTING_VIRUS:
            faceup = [card for card in obs.field
                      if card.zone == "monster" and card.position == "faceup"
                      and card.race is not None]
            scores = {}
            for choice, action in enumerate(record.legal_actions):
                if action.kind != "announce_race":
                    continue
                race = action.parameters.get("race")
                scores[choice] = sum(1 if card.controller != seat else -1
                                     for card in faceup if card.race == race)
            if scores:
                best = max(scores.values())
                if best >= 0:
                    preferred = [choice for choice, score in scores.items()
                                 if score == best]
                    disfavored = [choice for choice, score in scores.items()
                                  if score < 0]
            category = "tribe_avoids_friendly_only_type"
        if (preferred and disfavored
                and chosen in (*preferred, *disfavored)):
            result.append({"decision_index": index,
                           "preferred_action_indices": preferred,
                           "disfavored_action_indices": disfavored})
            counts[category] += 1
    return result, counts


def validate_automated_preferences(trajectory, preferences, weak_flip_attacks,
                                   card_facts=None) -> None:
    """Reject edits that no longer match the declared visible-rule output."""
    rule_set_id = getattr(preferences, "rule_set_id", None) or RULE_SET_ID
    candidates = (() if rule_set_id in (RULE_SET_V3, RULE_SET_V4, RULE_SET_V5,
                                       RULE_SET_V6, RULE_SET_V7, RULE_SET_V8,
                                       RULE_SET_V9, RULE_SET_V10, RULE_SET_V11,
                                       RULE_SET_V12)
                  else review_candidates(
        trajectory, weak_flip_attacks=weak_flip_attacks))
    expected, _ = derive(trajectory, candidates, rule_set_id=rule_set_id,
                         card_facts=card_facts)
    actual = [{"decision_index": item.decision_index,
               "preferred_action_indices": list(item.preferred_action_indices),
               "disfavored_action_indices": list(item.disfavored_action_indices)}
              for item in preferences.preferences]
    if actual != expected:
        raise ValueError(f"automated preferences do not match {rule_set_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replays", nargs="+", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--rule-set", choices=(RULE_SET_ID, RULE_SET_V2,
                                               RULE_SET_V3, RULE_SET_V4,
                                               RULE_SET_V5, RULE_SET_V6,
                                               RULE_SET_V7, RULE_SET_V8,
                                               RULE_SET_V9, RULE_SET_V10,
                                               RULE_SET_V11, RULE_SET_V12),
                        default=RULE_SET_ID)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        parser.error("output directory must be empty")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    weak_flip_attacks = load_weak_flip_monster_attack(args.native_root)
    card_facts = (load_card_facts(args.native_root)
                  if args.rule_set in (RULE_SET_V8, RULE_SET_V11,
                                       RULE_SET_V12) else None)
    report = []
    for path in args.replays:
        trajectory = read_trajectory(path)
        if trajectory.source not in ("policy_evaluation", "self_play_rl"):
            raise ValueError(f"{path}: expected a policy or self-play replay")
        verified = verify_trajectory(trajectory, ExperimentalOcgcoreEngine(args.native_root))
        audit_trajectory_visibility(trajectory)
        candidates = (() if args.rule_set in (RULE_SET_V3, RULE_SET_V4, RULE_SET_V5,
                                             RULE_SET_V6, RULE_SET_V7, RULE_SET_V8,
                                             RULE_SET_V9, RULE_SET_V10,
                                             RULE_SET_V11, RULE_SET_V12)
                      else review_candidates(
            trajectory, weak_flip_attacks=weak_flip_attacks))
        preferences, categories = derive(trajectory, candidates,
                                         rule_set_id=args.rule_set,
                                         card_facts=card_facts)
        if not preferences:
            continue
        seat = trajectory.skill_metadata.get("learner_seat" if trajectory.source
                                             == "self_play_rl" else "demonstrator_seat")
        payload = {
            "schema_version": 2 if args.rule_set in (RULE_SET_V3, RULE_SET_V4,
                                                     RULE_SET_V5, RULE_SET_V6,
                                                     RULE_SET_V7, RULE_SET_V8,
                                                     RULE_SET_V9, RULE_SET_V10,
                                                     RULE_SET_V11, RULE_SET_V12)
            else 1,
            "source_trajectory_sha256": sha256_file(path),
            "authorization": "automated_rule",
            "rule_set_id": args.rule_set,
            "reviewer": "GOAT AI automated visible-audit rules",
            "reviewed_seat": seat,
            "preferences": preferences,
        }
        output = args.output_dir / f"{path.stem}.preference.json"
        if output.exists():
            raise ValueError(f"duplicate replay basename would overwrite {output}")
        output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                          encoding="utf-8")
        read_decision_preferences(output, sha256_file(path), trajectory)
        report.append({"replay": str(path), "replay_sha256": sha256_file(path),
                       "verified_decisions": verified, "output": str(output),
                       "output_sha256": sha256_file(output),
                       "preferences": len(preferences), "categories": dict(categories)})
    manifest = {"schema_version": 1, "rule_set_id": args.rule_set,
                "labels_are_human_reviewed": False, "replays": report}
    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
    print(json.dumps({"output_dir": str(args.output_dir),
                      "replays_with_preferences": len(report),
                      "preferences": sum(item["preferences"] for item in report),
                      "manifest_sha256": sha256_file(manifest_path)}, indent=2))


if __name__ == "__main__":
    main()
