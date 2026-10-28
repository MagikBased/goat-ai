"""Refresh an existing local review queue with the current replay viewer layout.

This keeps the candidate selection and queue JSON unchanged. Source trajectories
must still match the hashes recorded when the queue was created.
"""

import argparse
import json
from pathlib import Path

from goat_ai.replay.fingerprint import sha256_file
from scripts.render_replay import render_replay
from scripts.shortlist_policy_disagreements import write_review_index


def refresh_review_queue(queue: Path, native_root: Path, *,
                         index_only: bool = False,
                         skip_reviewer_reveal: bool = False) -> tuple[int, int]:
    report = json.loads(queue.read_text(encoding="utf-8"))
    selected = report.get("selected", [])
    if not selected:
        raise ValueError("review queue has no selected decisions")
    viewers: dict[Path, tuple[Path, str]] = {}
    for item in selected:
        source = Path(item["trajectory"])
        expected = item["trajectory_sha256"]
        if sha256_file(source) != expected:
            raise ValueError(f"{source}: trajectory hash differs from queue")
        viewer = Path(item["viewer"].split("#", 1)[0])
        if not viewer.resolve().is_relative_to(queue.parent.resolve()):
            raise ValueError(f"{viewer}: viewer is outside queue directory")
        previous = viewers.setdefault(viewer, (source, expected))
        if previous != (source, expected):
            raise ValueError(f"{viewer}: conflicting trajectory references")
    if not index_only:
        for viewer, (source, _) in viewers.items():
            render_replay(source, viewer, native_root)
            # Existing verified reviewer pages are refreshed as well. Older queues
            # without a reviewer page remain player-visible only.
            reveal = viewer.with_suffix(".review.html")
            if reveal.is_file() and not skip_reviewer_reveal:
                render_replay(source, reveal, native_root, reviewer_reveal=True)
    write_review_index(selected, queue, native_root)
    return len(selected), len(viewers)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queues", nargs="+", type=Path,
                        help="existing review queue JSON files")
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--index-only", action="store_true",
                        help="refresh queue navigation without rebuilding duel pages")
    parser.add_argument("--skip-reviewer-reveal", action="store_true",
                        help="refresh player-visible pages, preserving existing verified "
                             "reveal files whose historical native assets may be unavailable")
    args = parser.parse_args()
    for queue in args.queues:
        items, viewers = refresh_review_queue(queue, args.native_root,
                                              index_only=args.index_only,
                                              skip_reviewer_reveal=args.skip_reviewer_reveal)
        verb = "linked" if args.index_only else "refreshed"
        print(f"{queue.with_suffix('.html')}: {items} items, {viewers} {verb} duels")


if __name__ == "__main__":
    main()
