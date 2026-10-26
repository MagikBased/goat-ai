"""Record labeled heuristic decisions in real native duels for a baseline."""

import argparse
import json
from dataclasses import replace
from pathlib import Path

from goat_ai.agents import (
    CombatFlipHeuristicAgent,
    CombatHeuristicAgent,
    HeuristicAgent,
    RandomAgent,
    TacticalHeuristicAgent,
    load_card_facts,
    load_card_races,
    load_flip_monster_codes,
)
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import write_trajectory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--engine", choices=("restricted", "experimental"), default="restricted")
    parser.add_argument("--teacher", choices=("heuristic", "combat_heuristic",
                                              "combat_flip", "tactical", "tactical_v12",
                                              "tactical_v11", "tactical_v10",
                                              "tactical_v9", "tactical_v8"),
                        default="heuristic")
    parser.add_argument("--opponent", choices=("random", "heuristic",
                                               "combat_heuristic", "tactical",
                                               "tactical_v12", "tactical_v11", "tactical_v10", "tactical_v9",
                                               "tactical_v8"), default="random")
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
    teacher_type = {"heuristic": HeuristicAgent,
                    "combat_heuristic": CombatHeuristicAgent,
                    "combat_flip": CombatFlipHeuristicAgent,
                    "tactical": TacticalHeuristicAgent,
                    "tactical_v12": TacticalHeuristicAgent,
                    "tactical_v11": TacticalHeuristicAgent,
                    "tactical_v10": TacticalHeuristicAgent,
                    "tactical_v9": TacticalHeuristicAgent,
                    "tactical_v8": TacticalHeuristicAgent}[args.teacher]
    tactical_teacher = args.teacher in ("tactical", "tactical_v12", "tactical_v11", "tactical_v10",
                                         "tactical_v9", "tactical_v8")
    tactical_opponent = args.opponent in ("tactical", "tactical_v12", "tactical_v11", "tactical_v10",
                                           "tactical_v9", "tactical_v8")
    flip_codes = (load_flip_monster_codes(args.native_root)
                  if args.teacher == "combat_flip" or tactical_teacher
                  or tactical_opponent else frozenset())
    card_races = (load_card_races(args.native_root)
                  if tactical_teacher or tactical_opponent else {})
    card_facts = (load_card_facts(args.native_root)
                  if args.teacher in ("tactical", "tactical_v12", "tactical_v11", "tactical_v10", "tactical_v9")
                  or args.opponent in ("tactical", "tactical_v12", "tactical_v11", "tactical_v10",
                                      "tactical_v9") else {})
    args.output_dir.mkdir(parents=True, exist_ok=True)
    games = []
    for seed in range(args.seed, args.seed + args.seeds):
        for teacher_seat in (0, 1):
            decks = (deck_a, deck_b) if teacher_seat == 0 else (deck_b, deck_a)
            with GoatEnvironment(*(str(deck) for deck in decks), seed=seed,
                                 engine=engine_type(args.native_root)) as env:
                observation = env.reset()
                teacher = (TacticalHeuristicAgent(flip_codes, card_races,
                                                  card_facts=card_facts,
                                                  v9_guards=args.teacher in (
                                                      "tactical", "tactical_v12", "tactical_v11", "tactical_v10",
                                                      "tactical_v9"),
                                                  v10_guards=args.teacher in (
                                                      "tactical", "tactical_v12", "tactical_v11", "tactical_v10"),
                                                  v11_guards=args.teacher in (
                                                      "tactical", "tactical_v12", "tactical_v11"),
                                                  v12_guards=args.teacher in ("tactical", "tactical_v12"),
                                                  v13_guards=args.teacher == "tactical")
                           if tactical_teacher else teacher_type(flip_codes))
                opponent = (RandomAgent(seed) if args.opponent == "random" else
                            TacticalHeuristicAgent(flip_codes, card_races,
                                                   card_facts=card_facts,
                                                   v9_guards=args.opponent in (
                                                       "tactical", "tactical_v12", "tactical_v11", "tactical_v10",
                                                       "tactical_v9"),
                                                   v10_guards=args.opponent in (
                                                       "tactical", "tactical_v12", "tactical_v11", "tactical_v10"),
                                                   v11_guards=args.opponent in (
                                                       "tactical", "tactical_v12", "tactical_v11"),
                                                   v12_guards=args.opponent in ("tactical", "tactical_v12"),
                                                   v13_guards=args.opponent == "tactical")
                            if tactical_opponent else {
                                "heuristic": HeuristicAgent,
                                "combat_heuristic": CombatHeuristicAgent,
                            }[args.opponent]())
                agents = (teacher if teacher_seat == 0 else opponent,
                          teacher if teacher_seat == 1 else opponent)
                for _ in range(args.max_decisions):
                    action = agents[observation.acting_player].select_action(
                        observation, env.legal_actions())
                    observation = env.step(action)
                    if env.is_terminal():
                        trajectory = replace(
                            env.trajectory(), source=("tactical" if tactical_teacher
                                                      else args.teacher),
                            skill_metadata={"demonstrator_seat": teacher_seat,
                                            "teacher": teacher_type.__name__,
                                            "teacher_version": (8 if args.teacher == "tactical_v8"
                                                                else 9 if args.teacher == "tactical_v9"
                                                                else 10 if args.teacher == "tactical_v10"
                                                                else 11 if args.teacher == "tactical_v11"
                                                                else 12 if args.teacher == "tactical_v12"
                                                                else teacher_type.teacher_version),
                                            "opponent": type(opponent).__name__,
                                            "opponent_version": (8 if args.opponent == "tactical_v8"
                                                                 else 9 if args.opponent == "tactical_v9"
                                                                 else 10 if args.opponent == "tactical_v10"
                                                                 else 11 if args.opponent == "tactical_v11"
                                                                 else 12 if args.opponent == "tactical_v12"
                                                                 else getattr(
                                                                     opponent, "teacher_version", 1))},
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
