"""Record one MR1 Normal Monster duel; this is not Edison gameplay."""

import argparse
from pathlib import Path

from goat_ai.agents import RandomAgent
from goat_ai.engine.mr1_vanilla_adapter import Mr1VanillaEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import write_trajectory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    fixtures = Path(__file__).resolve().parent / "decks"
    parser.add_argument("--deck1", type=Path, default=fixtures / "vanilla_probe.ydk")
    parser.add_argument("--deck2", type=Path, default=fixtures / "vanilla_reverse.ydk")
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-decisions", type=int, default=5000)
    parser.add_argument("--trajectory", type=Path)
    args = parser.parse_args()
    agents = (RandomAgent(args.seed), RandomAgent(args.seed + 1))
    with GoatEnvironment(str(args.deck1), str(args.deck2), args.seed,
                         engine=Mr1VanillaEngine(args.native_root)) as env:
        view = env.reset()
        for _ in range(args.max_decisions):
            action = agents[view.acting_player].select_action(view, env.legal_actions())
            view = env.step(action)
            if env.is_terminal():
                break
        else:
            raise RuntimeError("MR1 vanilla duel exceeded decision cap")
        trajectory = env.trajectory()
    if args.trajectory is not None:
        args.trajectory.parent.mkdir(parents=True, exist_ok=True)
        write_trajectory(args.trajectory, trajectory)
    print(f"MR1 vanilla protocol: winner={trajectory.winner}, "
          f"decisions={len(trajectory.decisions)}")


if __name__ == "__main__":
    main()
