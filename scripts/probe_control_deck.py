"""Exercise legal decks through the unaudited full-script native adapter."""

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
    parser.add_argument("--opponent-deck", help="defaults to --deck")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--seeds", type=int, default=1)
    parser.add_argument("--max-decisions", type=int, default=3000)
    args = parser.parse_args()
    if args.seeds < 1 or args.max_decisions < 1:
        parser.error("--seeds and --max-decisions must be positive")
    results = []
    for seed in range(args.seed, args.seed + args.seeds):
        decisions = 0
        try:
            with GoatEnvironment(args.deck, args.opponent_deck or args.deck, seed,
                                 ExperimentalOcgcoreEngine(args.native_root)) as env:
                observation = env.reset()
                agent = RandomAgent(seed=seed)
                while not env.is_terminal() and decisions < args.max_decisions:
                    action = agent.select_action(observation, env.legal_actions())
                    observation = env.step(action)
                    decisions += 1
                terminal = env.is_terminal()
                results.append({"seed": seed, "decisions": decisions,
                                "terminal": terminal,
                                "winner": env.result() if terminal else None,
                                "error": None if terminal else "decision limit reached"})
        except (OSError, RuntimeError, ValueError) as exc:
            results.append({"seed": seed, "decisions": decisions, "terminal": False,
                            "winner": None, "error": f"{type(exc).__name__}: {exc}"})
    completed = sum(game["terminal"] for game in results)
    print(json.dumps({"completed": completed, "games": results}, indent=2))
    if completed != args.seeds:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
