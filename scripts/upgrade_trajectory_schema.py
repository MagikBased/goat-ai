"""Replay a verified older duel into a separate current-schema trajectory."""

import argparse
from dataclasses import replace
from pathlib import Path

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory
from goat_ai.replay.fingerprint import sha256_file


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trajectory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--engine", choices=("restricted", "experimental"),
                        default="experimental")
    args = parser.parse_args()
    if args.trajectory.resolve() == args.output.resolve():
        parser.error("output must differ from the original replay")
    if args.output.exists():
        parser.error("output already exists")
    original = read_trajectory(args.trajectory)
    if original.schema_version != 23:
        parser.error("this upgrader accepts schema-v23 trajectories only")
    engine_type = (RestrictedOcgcoreEngine if args.engine == "restricted"
                   else ExperimentalOcgcoreEngine)
    verify_trajectory(original, engine_type(args.native_root))
    with GoatEnvironment(*original.decks, original.seed,
                         engine=engine_type(args.native_root)) as env:
        env.reset()
        for index, record in enumerate(original.decisions):
            legal = env.legal_actions()
            if legal != record.legal_actions:
                raise ValueError(f"decision {index}: legal actions changed during upgrade")
            env.step(legal[record.legal_actions.index(record.selected_action)])
        if not env.is_terminal() or env.result() != original.winner:
            raise ValueError("upgraded duel outcome differs")
        metadata = dict(original.skill_metadata or {})
        metadata["upgraded_from_schema"] = original.schema_version
        metadata["upgraded_from_sha256"] = sha256_file(args.trajectory)
        upgraded = replace(env.trajectory(), source=original.source,
                           skill_metadata=metadata)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_trajectory(args.output, upgraded)
    verified = verify_trajectory(read_trajectory(args.output),
                                 engine_type(args.native_root))
    print(f"{args.output}: schema v{upgraded.schema_version}, "
          f"{verified} verified decisions")


if __name__ == "__main__":
    main()
