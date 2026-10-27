"""Compare legacy and shallow dataclass JSON encoding on one saved replay.

This isolates in-memory serialization; replay loading and file I/O are excluded.
Both encoders must produce exactly the same UTF-8 bytes on every round.
"""

import argparse
import json
import platform
import subprocess
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

from goat_ai.replay import read_trajectory
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.replay.trajectory import _json_dataclass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trajectory", type=Path)
    parser.add_argument("--rounds", type=int, default=4)
    args = parser.parse_args()
    if args.rounds < 1:
        parser.error("rounds must be positive")

    trajectory = read_trajectory(args.trajectory)
    timings = []
    for round_number in range(args.rounds):
        order = (("legacy", "shallow") if round_number % 2 == 0
                 else ("shallow", "legacy"))
        outputs = {}
        elapsed = {}
        for mode in order:
            started = perf_counter()
            payload = json.dumps(
                asdict(trajectory) if mode == "legacy" else trajectory,
                default=_json_dataclass, separators=(",", ":")) + "\n"
            elapsed[mode] = perf_counter() - started
            outputs[mode] = payload.encode("utf-8")
        if outputs["legacy"] != outputs["shallow"]:
            raise AssertionError("serializers produced different replay bytes")
        timings.append({"order": order, "legacy_seconds": elapsed["legacy"],
                        "shallow_seconds": elapsed["shallow"],
                        "speedup": elapsed["legacy"] / elapsed["shallow"],
                        "bytes": len(outputs["shallow"]),
                        "matches_original": outputs["shallow"] == args.trajectory.read_bytes()})
    print(json.dumps({
        "project_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True).strip(),
        "worktree_dirty": bool(subprocess.check_output(
            ["git", "status", "--porcelain"], text=True).strip()),
        "platform": platform.platform(),
        "cpu": next((line.split(":", 1)[1].strip()
                     for line in Path("/proc/cpuinfo").read_text().splitlines()
                     if line.startswith("model name")), platform.processor()),
        "trajectory": str(args.trajectory),
        "trajectory_sha256": sha256_file(args.trajectory),
        "schema_version": trajectory.schema_version,
        "decisions": len(trajectory.decisions),
        "rounds": timings,
    }, indent=2))


if __name__ == "__main__":
    main()
