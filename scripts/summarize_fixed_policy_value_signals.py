"""Summarize a fixed-policy visible-margin audit with seed-group uncertainty."""

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

from goat_ai.replay.fingerprint import sha256_file
from scripts.audit_visible_value_signals import win_loss_auc


def margin_aucs(rows: list[dict]) -> tuple[float | None, float | None]:
    wins = [row for row in rows if row["won"]]
    losses = [row for row in rows if not row["won"]]
    return (win_loss_auc([row["cards"] for row in wins],
                         [row["cards"] for row in losses]),
            win_loss_auc([row["life_points_thousands"] for row in wins],
                         [row["life_points_thousands"] for row in losses]))


def seed_bootstrap_interval(groups: dict[int, list[dict]], *, seed: int,
                            replicates: int) -> dict:
    """Resample whole seeds, keeping their deck and seat outcomes together."""
    if not groups or replicates < 100:
        raise ValueError("seed bootstrap requires games and at least 100 replicates")
    seeds = sorted(groups)
    rng = random.Random(seed)
    samples = []
    for _ in range(replicates):
        chosen = [row for _ in seeds
                  for row in groups[seeds[rng.randrange(len(seeds))]]]
        cards, life_points = margin_aucs(chosen)
        if cards is not None and life_points is not None:
            samples.append((cards, life_points, life_points - cards))
    if not samples:
        raise ValueError("bootstrap needs both wins and losses")

    def interval(index: int) -> list[float]:
        values = sorted(sample[index] for sample in samples)
        return [values[int(0.025 * len(values))],
                values[min(int(0.975 * len(values)), len(values) - 1)]]

    return {"card_auc_95pct": interval(0), "life_points_auc_95pct": interval(1),
            "lp_minus_card_auc_95pct": interval(2),
            "valid_replicates": len(samples)}


def summarize(audit: dict, manifest: dict, *, seed: int = 171,
              replicates: int = 10000) -> dict:
    """Bind player-visible snapshots to verified fixed-policy replay rows."""
    source = {str(Path(row["trajectory"]).resolve()): row
              for row in manifest["games"]}
    if (not source or len(source) != len(manifest["games"])
            or manifest.get("verified_games") != len(source)
            or audit.get("files") != len(source)
            or not audit.get("samples")
            or audit.get("sampled_games") != len(audit["samples"])):
        raise ValueError("audit and manifest game counts differ")
    source_roles: dict[int, set[tuple[int, int]]] = defaultdict(set)
    for row in source.values():
        role = (row["matchup_index"], row["policy_seat"])
        if role in source_roles[row["seed"]]:
            raise ValueError("manifest duplicates a seed, matchup, and seat")
        source_roles[row["seed"]].add(role)
    if len({frozenset(roles) for roles in source_roles.values()}) != 1:
        raise ValueError("manifest seeds do not cover the same deck and seat roles")
    grouped: dict[int, list[dict]] = defaultdict(list)
    by_matchup: dict[int, list[dict]] = defaultdict(list)
    seen = set()
    for sample in audit["samples"]:
        path = str(Path(sample["path"]).resolve())
        if path not in source or path in seen:
            raise ValueError("audit contains an unknown or duplicate replay")
        seen.add(path)
        row = source[path]
        if (sample["sha256"] != row["trajectory_sha256"]
                or sample["won"] != (row["winner"] == row["policy_seat"])):
            raise ValueError("audit snapshot disagrees with replay manifest")
        grouped[row["seed"]].append(sample)
        by_matchup[row["matchup_index"]].append(sample)
    overall_cards, overall_lp = margin_aucs(audit["samples"])
    if (audit.get("card_margin_auc") is not None
            and audit["card_margin_auc"] != overall_cards
            or audit.get("lp_margin_auc") is not None
            and audit["lp_margin_auc"] != overall_lp):
        raise ValueError("audit AUC differs from its source snapshots")
    return {
        "source_games": len(source), "sampled_games": len(seen),
        "snapshot_turn_minimum": min(sample["snapshot_turn"]
                                     for sample in audit["samples"]),
        "wins": sum(sample["won"] for sample in audit["samples"]),
        "losses": sum(not sample["won"] for sample in audit["samples"]),
        "card_margin_auc": overall_cards, "lp_margin_auc": overall_lp,
        "seed_bootstrap": seed_bootstrap_interval(grouped, seed=seed,
                                                   replicates=replicates),
        "matchups": {
            str(matchup): {
                "games": len(rows), "wins": sum(row["won"] for row in rows),
                "card_margin_auc": margin_aucs(rows)[0],
                "lp_margin_auc": margin_aucs(rows)[1],
            }
            for matchup, rows in sorted(by_matchup.items())
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audit", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--seed", type=int, default=171)
    parser.add_argument("--replicates", type=int, default=10000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if (args.output.resolve() in (args.audit.resolve(), args.manifest.resolve())
            or args.replicates < 100):
        parser.error("output must be distinct and bootstrap needs at least 100 replicates")
    audit_hash = sha256_file(args.audit)
    manifest_hash = sha256_file(args.manifest)
    audit = json.loads(args.audit.read_text())
    manifest = json.loads(args.manifest.read_text())
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("games"), list):
        raise ValueError("unsupported fixed-policy manifest")
    result = summarize(audit, manifest, seed=args.seed, replicates=args.replicates)
    result.update({"audit_sha256": audit_hash, "manifest_sha256": manifest_hash,
                   "bootstrap_seed": args.seed, "bootstrap_replicates": args.replicates})
    if sha256_file(args.audit) != audit_hash or sha256_file(args.manifest) != manifest_hash:
        raise ValueError("source report changed during summarization")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
