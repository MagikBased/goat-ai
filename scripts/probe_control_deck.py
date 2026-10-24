"""Exercise a 40-card deck through the unaudited full-script native adapter."""

import argparse
import json
from pathlib import Path

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments.goat import GoatEnvironment


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--deck", default="examples/decks/control_probe.ydk")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-decisions", type=int, default=3000)
    args = parser.parse_args()
    with GoatEnvironment(args.deck, args.deck, args.seed,
                         ExperimentalOcgcoreEngine(args.native_root)) as env:
        observation = env.reset()
        agent = RandomAgent(seed=args.seed)
        decisions = 0
        while not env.is_terminal() and decisions < args.max_decisions:
            action = agent.select_action(observation, env.legal_actions())
            observation = env.step(action)
            decisions += 1
        print(json.dumps({"seed": args.seed, "decisions": decisions,
                          "terminal": env.is_terminal(),
                          "winner": env.result() if env.is_terminal() else None}))


if __name__ == "__main__":
    main()
