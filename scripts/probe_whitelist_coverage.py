"""Cover every canonical GOAT whitelist card in isolated headless duels.

Deck inclusion is protocol coverage, not proof that a card effect was used or
historically correct. All generated artifacts stay in the ignored cache.
"""

import argparse
import json
import os
import random
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import perf_counter

from goat_ai.actions import Action
from goat_ai.agents import RandomAgent
from goat_ai.engine.decks import (
    Decklist,
    read_goat_whitelist,
    validate_goat_deck,
)
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory
from goat_ai.replay.fingerprint import sha256_file
from scripts.evaluate_native import card_scripts_sha256, source_code_sha256
from scripts.probe_random_decks import write_deck

REPO = Path(__file__).resolve().parents[1]


class FirstActivationProbeAgent(RandomAgent):
    """Exercise each offered card activation once, using only legal actions."""

    def __init__(self, seed: int = 0) -> None:
        super().__init__(seed)
        self.activated: set[int] = set()

    def select_action(self, observation, legal_actions) -> Action:
        candidates = [action for action in legal_actions
                      if action.kind in ("activate", "chain")
                      and type(action.parameters.get("code")) is int
                      and action.parameters["code"] not in self.activated]
        if candidates:
            selected = self.rng.choice(candidates)
            self.activated.add(selected.parameters["code"])
            return selected
        return super().select_action(observation, legal_actions)


def canonical_pool(root: Path) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Return one legal ID per printed-card alias, split by deck type."""
    limits = read_goat_whitelist(root / "banlist/GOAT.lflist.conf")
    databases = tuple(root / "database" / name for name in (
        "goat-entries.cdb", "cards.cdb", "cards-unofficial.cdb"))
    with sqlite3.connect(f"file:{databases[1].resolve()}?mode=ro", uri=True) as db:
        for schema, path in (("goat", databases[0]), ("unofficial", databases[2])):
            db.execute(f"ATTACH DATABASE ? AS {schema}",
                       (f"file:{path.resolve()}?mode=ro",))
        main: dict[int, int] = {}
        fusion: dict[int, int] = {}
        for code, limit in sorted(limits.items()):
            if limit == 0:
                continue
            row = next((found for schema in ("goat", "main", "unofficial")
                        if (found := db.execute(
                            f"SELECT alias, type FROM {schema}.datas WHERE id=?",
                            (code,)).fetchone()) is not None), None)
            if row is None:
                raise ValueError(f"whitelisted card {code} lacks metadata")
            alias, card_type = row
            if card_type & 0x4000:  # Tokens are generated, never placed in decks.
                continue
            destination = fusion if card_type & 0x40 else main
            destination.setdefault(alias or code, code)
    return tuple(sorted(main.values())), tuple(sorted(fusion.values()))


def coverage_decks(root: Path, seed: int) -> tuple[Decklist, ...]:
    """Partition canonical Main cards, then distribute Fusion IDs across Extras."""
    main, fusion = canonical_pool(root)
    if len(main) < 40:
        raise ValueError("GOAT whitelist has fewer than 40 Main Deck cards")
    main = list(main)
    fusion = list(fusion)
    random.Random(seed).shuffle(main)
    random.Random(seed + 1_000_000).shuffle(fusion)
    chunks = [main[index:index + 40] for index in range(0, len(main), 40)]
    if len(chunks[-1]) < 40:
        chunks[-1].extend(main[:40 - len(chunks[-1])])
    if len(fusion) > 15 * len(chunks):
        raise ValueError("Fusion pool exceeds generated Extra Deck capacity")
    extras = [fusion[index::len(chunks)] for index in range(len(chunks))]
    limits = read_goat_whitelist(root / "banlist/GOAT.lflist.conf")
    decks = tuple(Decklist(tuple(cards), tuple(extras[index]))
                  for index, cards in enumerate(chunks))
    for deck in decks:
        validate_goat_deck(deck, limits, root / "database/cards.cdb",
                           root / "database/goat-entries.cdb",
                           root / "database/cards-unofficial.cdb")
    assert set(main) == {code for deck in decks for code in deck.main}
    assert set(fusion) == {code for deck in decks for code in deck.extra}
    return decks


def run_duel(root: Path, deck_a: Path, deck_b: Path, seed: int,
             max_decisions: int, trajectory_path: Path,
             agent_mode: str = "random") -> dict:
    """Run in a dedicated process; verify the exact completed trajectory."""
    started = perf_counter()
    with GoatEnvironment(str(deck_a), str(deck_b), seed,
                         ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        agent_type = {"random": RandomAgent,
                      "first_activation": FirstActivationProbeAgent}.get(agent_mode)
        if agent_type is None:
            raise ValueError(f"unknown coverage agent mode: {agent_mode}")
        agents = (agent_type(seed * 2), agent_type(seed * 2 + 1))
        decisions = 0
        offered_codes: set[int] = set()
        selected_codes: set[int] = set()
        offered_activations: set[int] = set()
        selected_activations: set[int] = set()
        while not env.is_terminal() and decisions < max_decisions:
            actions = env.legal_actions()
            offered_codes.update(action.parameters["code"] for action in actions
                                 if type(action.parameters.get("code")) is int)
            offered_activations.update(action.parameters["code"] for action in actions
                                       if action.kind in ("activate", "chain")
                                       and type(action.parameters.get("code")) is int)
            selected = agents[observation.acting_player].select_action(
                observation, actions)
            if type(selected.parameters.get("code")) is int:
                selected_codes.add(selected.parameters["code"])
                if selected.kind in ("activate", "chain"):
                    selected_activations.add(selected.parameters["code"])
            observation = env.step(selected)
            decisions += 1
        if not env.is_terminal():
            raise RuntimeError(f"duel exceeded {max_decisions} decisions")
        write_trajectory(trajectory_path, env.trajectory())
        replay = read_trajectory(trajectory_path)
        verified = verify_trajectory(replay, ExperimentalOcgcoreEngine(root))
        if verified != decisions:
            raise RuntimeError("native replay decision count changed")
        audit_trajectory_visibility(replay)
        return {"seed": seed, "deck_a": str(deck_a), "deck_b": str(deck_b),
                "winner": env.result(), "decisions": decisions,
                "replay_verified_decisions": verified,
                "trajectory_sha256": sha256_file(trajectory_path),
                "offered_card_codes": sorted(offered_codes),
                "selected_card_codes": sorted(selected_codes),
                "offered_activation_codes": sorted(offered_activations),
                "selected_activation_codes": sorted(selected_activations),
                "seconds": perf_counter() - started, "error": None}


def run_suite(root: Path, output: Path, seed: int, max_decisions: int,
              workers: int, agent_mode: str = "random") -> dict:
    if workers < 1 or max_decisions < 1:
        raise ValueError("workers and max_decisions must be positive")
    if agent_mode not in ("random", "first_activation"):
        raise ValueError("unknown coverage agent mode")
    if output.exists() and any(output.iterdir()):
        raise ValueError("coverage output must be empty")
    output.mkdir(parents=True, exist_ok=True)
    decks = coverage_decks(root, seed)
    for index, deck in enumerate(decks):
        write_deck(output / f"deck_{index:02d}.ydk", deck)
    main, fusion = canonical_pool(root)
    pairings = [(index, index + 1 if index + 1 < len(decks) else 0)
                for index in range(0, len(decks), 2)]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join((str(REPO / "src"), str(REPO)))

    def worker(pair_number: int, left: int, right: int) -> dict:
        duel_seed = seed + pair_number
        trajectory = output / f"duel_{pair_number:02d}.json"
        command = [sys.executable, str(Path(__file__).resolve()),
                   "--worker", "--native-root", str(root),
                   "--deck-a", str(output / f"deck_{left:02d}.ydk"),
                   "--deck-b", str(output / f"deck_{right:02d}.ydk"),
                   "--seed", str(duel_seed), "--max-decisions", str(max_decisions),
                   "--trajectory", str(trajectory), "--agent-mode", agent_mode]
        completed = subprocess.run(command, check=False, cwd=REPO, env=environment,
                                   capture_output=True, text=True)
        if completed.returncode == 0:
            result = json.loads(completed.stdout)
            if result["seed"] != duel_seed or not trajectory.is_file():
                raise ValueError("coverage worker returned the wrong duel")
            return result
        return {"seed": duel_seed, "deck_a": command[6], "deck_b": command[8],
                "winner": None, "decisions": None,
                "replay_verified_decisions": None,
                "trajectory_sha256": None, "offered_card_codes": [],
                "selected_card_codes": [], "seconds": None,
                "offered_activation_codes": [], "selected_activation_codes": [],
                "error": f"worker exit {completed.returncode}: "
                         f"{completed.stderr[-1000:]}"}

    started = perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(worker, i, left, right)
                   for i, (left, right) in enumerate(pairings)]
        games = [future.result() for future in futures]
    report = {"seed": seed, "max_decisions": max_decisions, "workers": workers,
              "agent_mode": agent_mode,
              "wall_seconds": perf_counter() - started,
              "canonical_main_cards": len(main), "canonical_fusion_cards": len(fusion),
              "decks": len(decks), "duels": len(games),
              "complete_duels": sum(game["error"] is None for game in games),
              "verified_decisions": sum(game["replay_verified_decisions"] or 0
                                        for game in games),
              "offered_card_codes": len({code for game in games
                                         for code in game["offered_card_codes"]}),
              "selected_card_codes": len({code for game in games
                                          for code in game["selected_card_codes"]}),
              "offered_activation_codes": len({code for game in games
                                                for code in game["offered_activation_codes"]}),
              "selected_activation_codes": len({code for game in games
                                                 for code in game["selected_activation_codes"]}),
              "deck_sha256": {f"deck_{index:02d}.ydk": sha256_file(
                  output / f"deck_{index:02d}.ydk") for index in range(len(decks))},
              "asset_sha256": {name: sha256_file(root / relative)
                               for name, relative in {
                                   "core_library": "build/libocgcore.so",
                                   "cards_database": "database/cards.cdb",
                                   "goat_database": "database/goat-entries.cdb",
                                   "unofficial_database": "database/cards-unofficial.cdb",
                                   "goat_whitelist": "banlist/GOAT.lflist.conf",
                                   "global_constants": "scripts/constant.lua",
                                   "global_utility": "scripts/utility.lua",
                               }.items()},
              "source_sha256": source_code_sha256(REPO),
              "probe_script_sha256": sha256_file(Path(__file__)),
              "card_scripts_sha256": card_scripts_sha256(root),
              "games": games}
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--output", type=Path,
                        default=Path(".cache/goat-ai/whitelist_coverage"))
    parser.add_argument("--seed", type=int, default=120000)
    parser.add_argument("--max-decisions", type=int, default=3000)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--agent-mode", choices=("random", "first_activation"),
                        default="random")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--deck-a", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--deck-b", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--trajectory", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    root = args.native_root.resolve()
    if args.worker:
        if not all((args.deck_a, args.deck_b, args.trajectory)):
            parser.error("worker requires both decks and a trajectory path")
        print(json.dumps(run_duel(root, args.deck_a, args.deck_b, args.seed,
                                  args.max_decisions, args.trajectory,
                                  args.agent_mode)))
    else:
        result = run_suite(root, args.output.resolve(), args.seed,
                           args.max_decisions, args.workers, args.agent_mode)
        print(json.dumps({key: result[key] for key in (
            "decks", "duels", "complete_duels", "verified_decisions",
            "offered_card_codes", "selected_card_codes",
            "offered_activation_codes", "selected_activation_codes",
            "wall_seconds")}))


if __name__ == "__main__":
    main()
