"""Measure exact native replay-prefix reconstruction, including reset.

This uses the recorded hidden deal and is only an offline feasibility benchmark.
It does not provide a player-consistent belief sampler or an online search.
"""

import argparse
import hashlib
import json
import statistics
import time
from pathlib import Path

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory
from goat_ai.replay.fingerprint import sha256_file


def benchmark_prefixes(source_path: Path, native_root: Path,
                       depths: tuple[int, ...] | None, repeats: int) -> dict:
    if repeats < 1:
        raise ValueError("repeats must be positive")
    source = read_trajectory(source_path)
    if source.ruleset != "tcg-goat-2005-08-17" or source.seed is None:
        raise ValueError("a seeded GOAT trajectory is required")
    count = len(source.decisions)
    if depths is None:
        depths = tuple(sorted({0, count // 4, count // 2, 3 * count // 4, count}))
    if not depths or any(type(depth) is not int or not 0 <= depth <= count
                         for depth in depths) or len(set(depths)) != len(depths):
        raise ValueError("depths must be distinct decision counts in the trajectory")
    verified = verify_trajectory(source, ExperimentalOcgcoreEngine(native_root))
    visibility = audit_trajectory_visibility(source)
    if verified != count or visibility["decisions"] != count:
        raise ValueError("source replay did not verify fully")
    results = []
    for depth in sorted(depths):
        seconds = []
        for _ in range(repeats):
            start = time.perf_counter()
            with GoatEnvironment(*source.decks, source.seed,
                                 ExperimentalOcgcoreEngine(native_root)) as env:
                env.reset()
                for index in range(depth):
                    env.step(source.decisions[index].selected_action)
                if env.is_terminal() != (depth == count):
                    raise ValueError(f"prefix endpoint differs at decision {depth}")
                if depth < count:
                    if env.legal_actions() != source.decisions[depth].legal_actions:
                        raise ValueError(f"legal actions differ at decision {depth}")
                elif env.result() != source.winner:
                    raise ValueError("terminal result differs from source")
            seconds.append(time.perf_counter() - start)
        results.append({"depth": depth, "seconds": seconds,
                        "median_seconds": statistics.median(seconds),
                        "decisions_per_second": (depth / statistics.median(seconds)
                                                 if depth else None)})
    asset_manifest = json.dumps(source.asset_sha256, sort_keys=True,
                                separators=(",", ":")).encode("utf-8")
    return {"source": str(source_path), "source_sha256": sha256_file(source_path),
            "asset_manifest_sha256": hashlib.sha256(asset_manifest).hexdigest(),
            "verified_decisions": count, "repeats": repeats,
            "includes_reset_and_endpoint_legal_actions": True,
            "source_fully_verified_before_timing": True,
            "offline_actual_hidden_deal": True, "results": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--depth", type=int, action="append",
                        help="repeat for distinct prefix lengths; default 0/25/50/75/100 percent")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = benchmark_prefixes(args.source, args.native_root,
                                tuple(args.depth) if args.depth else None,
                                args.repeats)
    payload = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
