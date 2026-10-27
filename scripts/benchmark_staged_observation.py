"""Compare a full native duel with and without staged-observation reuse."""

import argparse
import json
import platform
import tempfile
from pathlib import Path
from time import perf_counter

from goat_ai.agents import RandomAgent
from goat_ai.engine import native_messages
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.ocgcore_probe import OcgcoreProbe
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import verify_trajectory
from goat_ai.replay.fingerprint import sha256_file

GRACEFUL = 79571449
SANGAN = 504700178


class ReferenceEngine(ExperimentalOcgcoreEngine):
    def _decision(self, pending_attack=None, *, reuse_observation=False):
        return super()._decision(pending_attack, reuse_observation=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--max-decisions", type=int, default=3000)
    args = parser.parse_args()
    if args.rounds < 1 or args.max_decisions < 1:
        parser.error("rounds and max-decisions must be positive")
    original_limit = native_messages.MAX_CARD_SELECTION_COMBINATIONS
    original_observation = OcgcoreProbe.observation
    native_messages.MAX_CARD_SELECTION_COMBINATIONS = 1
    calls = 0

    def counted_observation(self, viewer, *, terminal=False):
        nonlocal calls
        calls += 1
        return original_observation(self, viewer, terminal=terminal)

    OcgcoreProbe.observation = counted_observation
    try:
        with tempfile.TemporaryDirectory(prefix="goat-staged-benchmark-") as directory:
            deck = Path(directory) / "graceful.ydk"
            deck.write_text("#main\n" + "\n".join(map(str, (
                GRACEFUL, SANGAN, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
            opponent = "examples/decks/vanilla_probe.ydk"

            def run(engine_type):
                nonlocal calls
                calls = 0
                started = perf_counter()
                with GoatEnvironment(str(deck), opponent, seed=18,
                                     engine=engine_type(args.native_root)) as env:
                    observation = env.reset()
                    agents = (RandomAgent(18), RandomAgent(19))
                    activated = staged_picks = 0
                    for _ in range(args.max_decisions):
                        actions = env.legal_actions()
                        action = None
                        if not activated and observation.acting_player == 0:
                            action = next((candidate for candidate in actions
                                           if candidate.kind == "activate"
                                           and candidate.parameters.get("code") == GRACEFUL), None)
                            activated = int(action is not None)
                        if action is None:
                            action = agents[observation.acting_player].select_action(
                                observation, actions)
                        if action.kind == "select_card" and action.parameters.get(
                                "selection_maximum") == 2:
                            staged_picks += 1
                        observation = env.step(action)
                        if env.is_terminal():
                            break
                    else:
                        raise RuntimeError("duel exceeded decision cap")
                    trajectory = env.trajectory()
                if not activated or staged_picks < 1:
                    raise RuntimeError("Graceful Charity staged selection was not exercised")
                return {"wall_seconds": perf_counter() - started,
                        "observation_builds": calls,
                        "decisions": len(trajectory.decisions),
                        "staged_picks": staged_picks}, trajectory

            rounds = []
            for round_index in range(args.rounds):
                order = (("reference", ReferenceEngine),
                         ("reused", ExperimentalOcgcoreEngine))
                if round_index % 2:
                    order = order[::-1]
                reports = {}
                trajectories = {}
                for label, engine_type in order:
                    reports[label], trajectories[label] = run(engine_type)
                if trajectories["reference"] != trajectories["reused"]:
                    raise AssertionError("staged reuse changed a native trajectory")
                rounds.append({"order": [label for label, _ in order], **reports,
                               "wall_speedup": reports["reference"]["wall_seconds"]
                               / reports["reused"]["wall_seconds"]})
            verified = verify_trajectory(trajectories["reused"],
                                         ExperimentalOcgcoreEngine(args.native_root))
            audit_trajectory_visibility(trajectories["reused"])
            cpu = next((line.split(":", 1)[1].strip()
                        for line in Path("/proc/cpuinfo").read_text().splitlines()
                        if line.startswith("model name")), platform.processor())
            print(json.dumps({
                "platform": platform.platform(), "cpu": cpu,
                "native_core_sha256": sha256_file(
                    args.native_root / "build/libocgcore.so"),
                "deck_sha256": [sha256_file(deck), sha256_file(opponent)],
                "seed": 18, "rounds": rounds, "verified_decisions": verified,
            }, indent=2))
    finally:
        native_messages.MAX_CARD_SELECTION_COMBINATIONS = original_limit
        OcgcoreProbe.observation = original_observation


if __name__ == "__main__":
    main()
