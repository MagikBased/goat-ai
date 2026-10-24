"""Record labeled heuristic decisions in real native duels for a baseline."""

import argparse
import json
from dataclasses import replace
from pathlib import Path

from goat_ai.agents import HeuristicAgent, RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import write_trajectory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--engine", choices=("restricted", "experimental"), default="restricted")
    parser.add_argument("--deck-a", type=Path)
    parser.add_argument("--deck-b", type=Path)
    parser.add_argument("--seed", type=int, default=1000)
    parser.add_argument("--seeds", type=int, default=4)
    parser.add_argument("--max-decisions", type=int, default=5000)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.seeds < 1 or args.max_decisions < 1:
        parser.error("seeds and max decisions must be positive")
    fixtures = Path(__file__).resolve().parent.parent / "examples/decks"
    deck_a = args.deck_a or fixtures / "vanilla_probe.ydk"
    deck_b = args.deck_b or fixtures / "vanilla_reverse.ydk"
    engine_type = (RestrictedOcgcoreEngine if args.engine == "restricted"
                   else ExperimentalOcgcoreEngine)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    games = []
    for seed in range(args.seed, args.seed + args.seeds):
        for teacher_seat in (0, 1):
            decks = (deck_a, deck_b) if teacher_seat == 0 else (deck_b, deck_a)
            with GoatEnvironment(*(str(deck) for deck in decks), seed=seed,
                                 engine=engine_type(args.native_root)) as env:
                observation = env.reset()
                agents = (HeuristicAgent() if teacher_seat == 0 else RandomAgent(seed),
                          HeuristicAgent() if teacher_seat == 1 else RandomAgent(seed))
                for _ in range(args.max_decisions):
                    action = agents[observation.acting_player].select_action(
                        observation, env.legal_actions())
                    observation = env.step(action)
                    if env.is_terminal():
                        trajectory = replace(
                            env.trajectory(), source="heuristic",
                            skill_metadata={"demonstrator_seat": teacher_seat,
                                            "teacher": "HeuristicAgent",
                                            "opponent": "RandomAgent"},
                        )
                        path = args.output_dir / f"seed_{seed}_seat_{teacher_seat}.json"
                        write_trajectory(path, trajectory)
                        games.append({"seed": seed, "teacher_seat": teacher_seat,
                                      "winner": env.result(),
                                      "decisions": len(trajectory.decisions),
                                      "teacher_decisions": sum(
                                          record.observation.acting_player == teacher_seat
                                          for record in trajectory.decisions),
                                      "path": str(path)})
                        break
                else:
                    raise RuntimeError(f"duel exceeded {args.max_decisions} decisions: "
                                       f"seed={seed}, teacher seat={teacher_seat}")
    print(json.dumps({"games": games, "teacher_wins": sum(
        game["winner"] == game["teacher_seat"] for game in games)}, indent=2))


if __name__ == "__main__":
    main()
