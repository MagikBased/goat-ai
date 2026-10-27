"""Prepare a diverse human-review queue from verified policy/teacher disagreements.

The teacher supplies review candidates, not correctness labels. No teacher
choice is used for training until a person reviews the recorded visible state.
"""

import argparse
import json
from collections import Counter
from html import escape
from pathlib import Path
from urllib.parse import quote

import torch

from goat_ai.agents import (
    TacticalHeuristicAgent,
    load_card_facts,
    load_card_races,
    load_flip_monster_codes,
)
from goat_ai.agents.card_metadata import load_weak_flip_monster_attack
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.evaluation.replay_review import review_candidates
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.training import load_policy_agent
from goat_ai.training.policy import POLICY_INFERENCE_VERSION, encode_decision
from scripts.render_replay import _card_names, render_replay


def select_diverse_candidates(candidates: list[dict], limit: int,
                              per_replay: int) -> list[dict]:
    """Take confident disagreements without letting one prompt dominate."""
    if limit < 1 or per_replay < 1:
        raise ValueError("review limits must be positive")
    chosen = []
    fingerprints = set()
    replay_counts: Counter[str] = Counter()
    for candidate in sorted(candidates, key=lambda item: (
            not item["audit_flags"], -item["probability_margin"],
            item["trajectory"], item["decision_index"])):
        fingerprint = candidate["_fingerprint"]
        replay = candidate["trajectory"]
        if fingerprint in fingerprints or replay_counts[replay] >= per_replay:
            continue
        fingerprints.add(fingerprint)
        replay_counts[replay] += 1
        chosen.append({key: value for key, value in candidate.items()
                       if key != "_fingerprint"})
        if len(chosen) == limit:
            break
    return chosen


def action_summary(action) -> dict:
    """Present only the structured action the agent could already select."""
    return {"kind": action.kind, "parameters": action.parameters}


def disagreement_fingerprint(record, teacher_action) -> tuple:
    selected = record.selected_action
    # A response card such as Ring can be offered on many chains. Keep one
    # review example per offered card, while target/announcement prompts need
    # their resolving source to distinguish unrelated choices.
    chain_source = (record.observation.chain[-1].card_code
                    if record.observation.chain and selected.kind in (
                        "select_card", "select_cards", "announce_race",
                        "announce_attribute", "announce_number") else None)
    phase = None if selected.kind == "pass" and teacher_action.kind == "chain" else (
        record.observation.phase)
    return (phase, chain_source,
            selected.kind, selected.parameters.get("code"),
            teacher_action.kind, teacher_action.parameters.get("code"))


def write_review_index(selected: list[dict], output: Path,
                       native_root: Path) -> Path:
    """Link selected frames without loading private reviewer reveals."""
    codes = {action["parameters"].get("code")
             for item in selected for action in (
                 item["policy_action"], item["teacher_action"])}
    names = _card_names({code for code in codes if type(code) is int and code > 0},
                        native_root)

    def action_label(action: dict) -> str:
        code = action["parameters"].get("code")
        name = names.get(code, f"Card {code}") if code else ""
        return escape(f"{action['kind']} {name}".strip())

    rows = []
    for item in selected:
        viewer, fragment = item["viewer"].split("#", 1)
        relative = Path(viewer).relative_to(output.parent.resolve())
        href = quote(str(relative), safe="/") + "#" + fragment
        reasons = ", ".join(item["audit_flags"]) or "Tactical disagreement"
        rows.append(
            f'<tr><td><a href="{escape(href, quote=True)}">'
            f'{item["turn"]} · {escape(item["phase"])} · frame {item["viewer_frame"]}'
            f'</a></td><td>{action_label(item["policy_action"])}</td>'
            f'<td>{action_label(item["teacher_action"])}</td>'
            f'<td>{escape(reasons)}</td>'
            f'<td>{item["probability_margin"]:.3f}</td></tr>')
    html = ("<!doctype html><html lang=\"en\"><meta charset=\"utf-8\">"
            "<title>GOAT AI review queue</title><style>"
            "body{font:16px system-ui;background:#071925;color:#f1f6f8;"
            "max-width:1100px;margin:2rem auto;padding:0 1rem}"
            "table{border-collapse:collapse;width:100%}th,td{padding:.7rem;"
            "border-bottom:1px solid #42606b;text-align:left}a{color:#8bd9ee}"
            "</style><h1>GOAT AI review queue</h1>"
            "<p>Visible-state audit flags come first, followed by diverse"
            " policy and Tactical-v14 disagreements. These are review prompts,"
            " not correct-play labels. Open a frame to inspect the complete duel."
            " The viewer preserves each player's information boundary.</p>"
            "<table><thead><tr><th>Replay frame</th><th>Policy played</th>"
            "<th>Tactical suggested</th><th>Review reason</th>"
            "<th>Model margin</th></tr></thead><tbody>"
            + "".join(rows) + "</tbody></table></html>\n")
    index = output.with_suffix(".html")
    index.write_text(html, encoding="utf-8")
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("replays", nargs="+", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--per-replay", type=int, default=2)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--render-viewers", action="store_true",
                        help="write offline HTML for replays represented in the queue")
    args = parser.parse_args()
    if args.limit < 1 or args.per_replay < 1:
        parser.error("review limits must be positive")
    if len({path.resolve() for path in args.replays}) != len(args.replays):
        parser.error("duplicate replay path")
    checkpoint_hash = sha256_file(args.checkpoint)
    agent = load_policy_agent(args.checkpoint)
    model = agent.model.eval()
    flip_codes = load_flip_monster_codes(args.native_root)
    card_races = load_card_races(args.native_root)
    weak_flip_attacks = load_weak_flip_monster_attack(args.native_root)
    card_facts = load_card_facts(args.native_root)

    def fresh_teacher():
        # A counterfactual attack choice was not necessarily executed in the
        # recorded policy duel. Do not carry its private pending-attack cache
        # into the next review decision; real context is in the observation.
        return TacticalHeuristicAgent(
            flip_codes, card_races, card_facts=card_facts,
            v8_guards=True, v9_guards=True, v10_guards=True, v11_guards=True,
            v12_guards=True, v13_guards=True, v14_guards=True)
    candidates = []
    replay_report = []
    for path in args.replays:
        source_hash = sha256_file(path)
        trajectory = read_trajectory(path)
        metadata = trajectory.skill_metadata or {}
        seat = metadata.get("demonstrator_seat")
        if (trajectory.source != "policy_evaluation" or type(seat) is not int
                or seat not in (0, 1)
                or metadata.get("policy_checkpoint_sha256") != checkpoint_hash
                or metadata.get("policy_inference") != "greedy"
                or metadata.get("policy_inference_version") != POLICY_INFERENCE_VERSION
                or metadata.get("policy_feature_version") != model.feature_version):
            raise ValueError(f"{path}: expected a plain greedy replay from this checkpoint")
        verified = verify_trajectory(
            trajectory, ExperimentalOcgcoreEngine(args.native_root))
        audit_trajectory_visibility(trajectory)
        if sha256_file(path) != source_hash:
            raise ValueError(f"{path}: replay changed during verification")
        audit_by_index: dict[int, list[str]] = {}
        for finding in review_candidates(trajectory, card_races, weak_flip_attacks):
            audit_by_index.setdefault(finding.decision_index, []).append(finding.category)
        disagreements = 0
        policy_choices = 0
        replay_agent = load_policy_agent(args.checkpoint)
        for index, record in enumerate(trajectory.decisions):
            if record.observation.acting_player != seat:
                continue
            policy_choices += 1
            legal = record.legal_actions
            if replay_agent.select_action(record.observation, legal) != record.selected_action:
                raise ValueError(f"{path}: greedy policy choice differs at {index}")
            if len(legal) == 1:
                continue
            features = encode_decision(record.observation, legal, agent.vocabulary,
                                       model.feature_version)
            with torch.inference_mode():
                logits = model(features.to(next(model.parameters()).device))
                probabilities = torch.softmax(logits, 0).cpu()
            policy_index = legal.index(record.selected_action)
            alternative = fresh_teacher().select_action(record.observation, legal)
            if alternative not in legal:
                raise ValueError(f"{path}: teacher choice is illegal at {index}")
            disagreed = alternative != record.selected_action
            audit_flags = audit_by_index.get(index, [])
            if not disagreed and not audit_flags:
                continue
            disagreements += disagreed
            teacher_index = legal.index(alternative)
            margin = float(probabilities[policy_index] - probabilities[teacher_index])
            candidates.append({
                "trajectory": str(path.resolve()),
                "trajectory_sha256": source_hash,
                "decision_index": index,
                "viewer_frame": index + 1,
                "seat": seat,
                "turn": record.observation.turn,
                "phase": record.observation.phase,
                "legal_action_count": len(legal),
                "policy_action": action_summary(record.selected_action),
                "teacher_action": action_summary(alternative),
                "policy_probability": round(float(probabilities[policy_index]), 6),
                "teacher_probability": round(float(probabilities[teacher_index]), 6),
                "probability_margin": round(margin, 6),
                "audit_flags": audit_flags,
                "teacher_disagrees": disagreed,
                "_fingerprint": (("audit", tuple(audit_flags),
                                  record.selected_action.kind,
                                  record.selected_action.parameters.get("code"))
                                 if audit_flags else
                                 disagreement_fingerprint(record, alternative)),
            })
        replay_report.append({"trajectory": str(path.resolve()),
                              "trajectory_sha256": source_hash,
                              "verified_decisions": verified,
                              "policy_choices": policy_choices,
                              "disagreements": disagreements})
    selected = select_diverse_candidates(candidates, args.limit, args.per_replay)
    if args.render_viewers:
        viewer_dir = args.output.parent / (args.output.stem + "_viewers")
        for path in sorted({item["trajectory"] for item in selected}):
            source = Path(path)
            digest = next(item["trajectory_sha256"] for item in selected
                          if item["trajectory"] == path)
            if sha256_file(source) != digest:
                raise ValueError(f"{path}: replay changed before rendering")
            output = viewer_dir / f"{source.stem}_{digest[:12]}.html"
            render_replay(source, output, args.native_root)
            for item in selected:
                if item["trajectory"] == path:
                    item["viewer"] = str(output.resolve()) + f"#decision={item['viewer_frame']}"
    report = {"schema_version": 1,
              "purpose": "human_review_candidates_not_training_labels",
              "checkpoint_sha256": checkpoint_hash,
              "teacher": "TacticalHeuristicAgent_v14",
              "selection": "visible_audit_then_model_margin_distinct_prompt_max_per_replay",
              "replays": replay_report,
              "candidate_count": len(candidates),
              "selected": selected}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    if args.render_viewers:
        write_review_index(selected, args.output, args.native_root)
    print(json.dumps({"output": str(args.output), "replays": len(replay_report),
                      "candidate_count": len(candidates), "selected": len(selected),
                      "verified_decisions": sum(item["verified_decisions"]
                                                for item in replay_report)}))


if __name__ == "__main__":
    main()
