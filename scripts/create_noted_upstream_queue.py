"""Shortlist earlier optional activations behind saved upstream-mistake notes.

Candidates are review prompts, not labels. A human must inspect the earlier
visible state and choose among its legal actions before it enters training.
"""

import argparse
import json
from pathlib import Path

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory
from goat_ai.replay.fingerprint import sha256_file
from scripts.create_upstream_review import upstream_candidate
from scripts.serve_review_queue import ROOT, ReviewStore
from scripts.shortlist_policy_disagreements import (
    activation_matches_chain_source,
    write_review_index,
)
from scripts.validate_review_queue_labels import queue_sources, verify_queue_items


def create_noted_upstream_queue(queue_path: Path, output: Path, native_root: Path,
                                *, labels_dir: Path | None = None,
                                max_per_note: int = 3,
                                include_context_notes: bool = False) -> tuple[Path, int]:
    if max_per_note < 1:
        raise ValueError("max_per_note must be positive")
    queue_path, output = queue_path.resolve(), output.resolve()
    if output == queue_path or output.parent != queue_path.parent:
        raise ValueError("upstream queue must have a new name beside the source queue")
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    sources = queue_sources(queue, queue_path)
    label_folder = labels_dir or ROOT / ".cache/goat-ai/review_labels" / sha256_file(queue_path)[:12]
    store = ReviewStore(queue_path, label_folder)
    reviewed = {}
    saved_notes = {}
    selected = []
    seen = set()
    unmatched = 0
    for item_number, item in enumerate(queue["selected"], 1):
        digest = item["trajectory_sha256"]
        if digest not in saved_notes:
            saved_notes[digest] = {
                note["decision_index"]: note
                for note in store.note_state(digest)["notes"]}
        notes = saved_notes[digest]
        note = notes.get(item["decision_index"])
        if not note or note["kind"] not in (
                ("upstream_mistake", "context") if include_context_notes
                else ("upstream_mistake",)):
            continue
        if digest not in reviewed:
            replay_path, offered = sources[digest]
            if sha256_file(replay_path) != digest:
                raise ValueError("source replay changed")
            trajectory = read_trajectory(replay_path)
            verify_queue_items(trajectory, offered, queue["checkpoint_sha256"])
            verify_trajectory(trajectory, ExperimentalOcgcoreEngine(native_root))
            audit_trajectory_visibility(trajectory)
            reviewed[digest] = trajectory
        trajectory = reviewed[digest]
        target = trajectory.decisions[item["decision_index"]].observation
        source = target.chain[-1] if target.chain else None
        found = 0
        for prior_index in range(item["decision_index"] - 1, -1, -1):
            prior = trajectory.decisions[prior_index]
            observation = prior.observation
            if observation.turn < target.turn:
                break
            if (observation.turn != target.turn
                    or observation.acting_player != target.acting_player
                    or prior.selected_action.kind not in ("activate", "chain")
                    or source is not None and not activation_matches_chain_source(
                        prior.selected_action, source)
                    or not any(action.kind in ("pass", "battle_phase", "main2",
                                               "end_phase", "phase_transition")
                               and action != prior.selected_action
                               for action in prior.legal_actions)):
                continue
            key = (digest, prior_index)
            if key in seen:
                continue
            replay_path, _ = sources[digest]
            candidate = upstream_candidate(trajectory, item, digest, replay_path,
                                           queue_path, prior_index)
            candidate["source_item_number"] = item_number
            candidate["source_decision_index"] = item["decision_index"]
            candidate["review_note"] = note["text"]
            candidate["source_note_kind"] = note["kind"]
            selected.append(candidate)
            seen.add(key)
            found += 1
            if found == max_per_note:
                break
        if found == 0:
            unmatched += 1
    if not selected:
        raise ValueError("no earlier optional activations found for saved upstream-mistake notes")
    result = {
        "schema_version": 1,
        "purpose": "human_review_candidates_not_training_labels",
        "checkpoint_sha256": queue["checkpoint_sha256"],
        "source_queue_sha256": sha256_file(queue_path),
        "included_note_kinds": (["context", "upstream_mistake"]
                                if include_context_notes else ["upstream_mistake"]),
        "unmatched_note_count": unmatched,
        "selected": selected,
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if output.exists() and output.read_text(encoding="utf-8") != rendered:
        raise ValueError("upstream queue already exists with different contents")
    output.write_text(rendered, encoding="utf-8")
    write_review_index(selected, output, native_root,
                       comparison_label="Alternative candidate")
    return output, unmatched


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queue", type=Path)
    parser.add_argument("--output", type=Path,
                        help="new JSON beside source queue; defaults to noted_upstream.json")
    parser.add_argument("--labels-dir", type=Path,
                        help="saved label folder; defaults to the source queue hash folder")
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--max-per-note", type=int, default=3)
    parser.add_argument("--include-context-notes", action="store_true",
                        help="also offer matched earlier activations from context notes; "
                             "these remain unlabeled review prompts")
    args = parser.parse_args()
    output, unmatched = create_noted_upstream_queue(
        args.queue, args.output or args.queue.parent / "noted_upstream.json",
        args.native_root, labels_dir=args.labels_dir, max_per_note=args.max_per_note,
        include_context_notes=args.include_context_notes)
    print(f"{output} ({unmatched} notes without an eligible earlier activation)")


if __name__ == "__main__":
    main()
