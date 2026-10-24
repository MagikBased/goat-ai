"""Play a real GOAT-mode vanilla fixture with two random-policy seats."""

import argparse
from pathlib import Path

from goat_ai.agents import RandomAgent
from goat_ai.engine.vanilla_adapter import VanillaOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import write_trajectory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--trajectory", type=Path)
    args = parser.parse_args()
    deck1 = Path(__file__).parent / "decks/vanilla_probe.ydk"
    deck2 = Path(__file__).parent / "decks/vanilla_reverse.ydk"
    with GoatEnvironment(str(deck1), str(deck2), args.seed,
                         engine=VanillaOcgcoreEngine(args.native_root)) as env:
        observation = env.reset()
        agent = RandomAgent(args.seed)
        for _ in range(5000):
            action = agent.select_action(observation, env.legal_actions())
            observation = env.step(action)
            if env.is_terminal():
                trajectory = env.trajectory()
                print(f"winner={env.result()} decisions={len(trajectory.decisions)}")
                if args.trajectory:
                    args.trajectory.parent.mkdir(parents=True, exist_ok=True)
                    write_trajectory(args.trajectory, trajectory)
                    print(f"trajectory={args.trajectory}")
                return
    raise SystemExit("duel did not finish within 5000 decisions")


if __name__ == "__main__":
    main()
