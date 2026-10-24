"""Record a real Ground Collapse duel with its two-zone choice exercised."""

import argparse
from pathlib import Path

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import verify_trajectory, write_trajectory

ROOT = Path(__file__).resolve().parent.parent
GROUND_COLLAPSE = 90502999
CHOSEN_ZONES = [
    {"controller": 0, "location": 4, "sequence": 0},
    {"controller": 0, "location": 4, "sequence": 1},
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=ROOT / ".cache/goat-ai")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "replays/ground_collapse_3.json")
    args = parser.parse_args()
    deck1 = ROOT / "examples/decks/ground_collapse_probe.ydk"
    deck2 = ROOT / "examples/decks/vanilla_probe.ydk"
    with GoatEnvironment(str(deck1), str(deck2), seed=3,
                         engine=ExperimentalOcgcoreEngine(args.native_root)) as env:
        observation = env.reset()
        agents = (RandomAgent(3), RandomAgent(4))
        activated = disabled = False
        for _ in range(5000):
            choices = env.legal_actions()
            action = None
            if not activated:
                action = next((choice for choice in choices
                               if choice.kind == "activate"
                               and choice.parameters.get("code") == GROUND_COLLAPSE), None)
                activated |= action is not None
            if action is None and choices[0].kind == "disable_zones":
                action = next((choice for choice in choices
                               if choice.parameters.get("zones") == CHOSEN_ZONES), None)
                if action is None:
                    raise RuntimeError("expected Ground Collapse zone choice was unavailable")
                disabled = True
            if action is None:
                action = agents[observation.acting_player].select_action(observation, choices)
            observation = env.step(action)
            if env.is_terminal():
                break
        else:
            raise RuntimeError("duel exceeded 5000 decisions")
        if not activated or not disabled:
            raise RuntimeError("duel did not exercise Ground Collapse")
        trajectory = env.trajectory()
    verified = verify_trajectory(trajectory, ExperimentalOcgcoreEngine(args.native_root))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_trajectory(args.output, trajectory)
    print(f"wrote {args.output}: winner={trajectory.winner}, "
          f"decisions={verified}, schema={trajectory.schema_version}")


if __name__ == "__main__":
    main()
