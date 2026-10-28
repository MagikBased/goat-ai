"""Generate reproducible whitelist-legal decks and probe native decision coverage.

This is protocol triage, not evidence that a sampled duel is GOAT-correct.
Decks and reports are written under the ignored .cache directory by default.
"""

import argparse
import json
import random
import sqlite3
import subprocess
import sys
from collections import Counter
from pathlib import Path

from goat_ai.agents import (
    RandomAgent,
    TacticalHeuristicAgent,
    load_card_facts,
    load_card_races,
    load_flip_monster_codes,
)
from goat_ai.engine.decks import (
    Decklist,
    read_goat_whitelist,
    read_ydk,
    validate_goat_deck,
)
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.card_actions import count_chain_response, count_source_actions
from goat_ai.evaluation.competitive_corpus import (
    INDIANAPOLIS_2005_MAIN_DECKS,
    TOURNAMENT_MAIN_DECKS,
)
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import verify_trajectory
from goat_ai.replay.fingerprint import sha256_file

SCAPEGOAT = 504700123
METAMORPHOSIS = 46411259
THOUSAND_EYES_RESTRICT = 504700102
FUSION_STRESS_MAIN = (SCAPEGOAT, METAMORPHOSIS)


def generate_deck(root: Path, seed: int, *, include_random_extra: bool = False,
                  fusion_stress: bool = False) -> Decklist:
    """Choose distinct whitelist cards, optionally including 15 Fusion cards."""
    if fusion_stress and not include_random_extra:
        raise ValueError("Fusion stress requires a random Extra Deck")
    limits = read_goat_whitelist(root / "banlist/GOAT.lflist.conf")
    database = root / "database/cards.cdb"
    goat = root / "database/goat-entries.cdb"
    unofficial = root / "database/cards-unofficial.cdb"
    with sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True) as connection:
        connection.execute("ATTACH DATABASE ? AS goat", (f"file:{goat.resolve()}?mode=ro",))
        connection.execute("ATTACH DATABASE ? AS unofficial",
                           (f"file:{unofficial.resolve()}?mode=ro",))
        candidates = []
        fusion_candidates = []
        for code, limit in sorted(limits.items()):
            if not limit:
                continue
            row = None
            for schema in ("goat", "main", "unofficial"):
                row = connection.execute(f"SELECT alias, type FROM {schema}.datas WHERE id=?",
                                         (code,)).fetchone()
                if row is not None:
                    break
            if row is not None and not row[1] & 0x4000:
                (fusion_candidates if row[1] & 0x40 else candidates).append(
                    (code, row[0] or code))
    random.Random(seed).shuffle(candidates)
    chosen = []
    canonical = set()
    enabler_names = {name_code for code, name_code in candidates
                     if code in FUSION_STRESS_MAIN} if fusion_stress else set()
    target_main_size = 34 if fusion_stress else 40
    for code, name_code in candidates:
        if name_code in canonical or name_code in enabler_names:
            continue
        chosen.append(code)
        canonical.add(name_code)
        if len(chosen) == target_main_size:
            break
    if len(chosen) != target_main_size or fusion_stress and len(enabler_names) != 2:
        raise ValueError("GOAT card pool lacks Fusion stress Main Deck cards")
    if fusion_stress:
        chosen = [*(code for code in FUSION_STRESS_MAIN for _ in range(3)), *chosen]
    extra = []
    if include_random_extra:
        random.Random(seed + 2_000_000).shuffle(fusion_candidates)
        extra_canonical = set()
        if fusion_stress:
            restrict = next(((code, name_code) for code, name_code in fusion_candidates
                             if code == THOUSAND_EYES_RESTRICT), None)
            if restrict is None:
                raise ValueError("GOAT Fusion stress card is absent from whitelist")
            extra.append(restrict[0])
            extra_canonical.add(restrict[1])
        for code, name_code in fusion_candidates:
            if name_code in extra_canonical:
                continue
            extra.append(code)
            extra_canonical.add(name_code)
            if len(extra) == 15:
                break
        if len(extra) != 15:
            raise ValueError("GOAT card pool contains fewer than 15 distinct Fusion cards")
    deck = Decklist(tuple(chosen), tuple(extra))
    validate_goat_deck(deck, limits, database, goat, unofficial)
    return deck


def generate_tournament_mix(root: Path, seed: int, *,
                            source_names: tuple[str, ...] = TOURNAMENT_MAIN_DECKS
                            ) -> Decklist:
    """Sample a legal 40-card list from copies in a sourced deck corpus."""
    if not source_names:
        raise ValueError("tournament mix requires sourced Main Decks")
    limits = read_goat_whitelist(root / "banlist/GOAT.lflist.conf")
    fixtures = Path(__file__).resolve().parents[1] / "examples/decks"
    sources = tuple(read_ydk(fixtures / name) for name in source_names)
    candidates = [code for deck in sources for code in deck.main]
    random.Random(seed).shuffle(candidates)
    chosen = []
    counts: Counter[int] = Counter()
    for code in candidates:
        if counts[code] >= limits.get(code, 0):
            continue
        chosen.append(code)
        counts[code] += 1
        if len(chosen) == 40:
            break
    if len(chosen) != 40:
        raise ValueError("tournament corpus cannot supply a legal 40-card Main Deck")
    deck = Decklist(tuple(chosen), sources[seed % len(sources)].extra)
    validate_goat_deck(deck, limits, root / "database/cards.cdb",
                       root / "database/goat-entries.cdb",
                       root / "database/cards-unofficial.cdb")
    return deck


def write_deck(path: Path, deck: Decklist) -> None:
    path.write_text("#main\n" + "\n".join(map(str, deck.main))
                    + "\n#extra\n"
                    + "".join(f"{code}\n" for code in deck.extra)
                    + "!side\n")


def probe(root: Path, output: Path, first_seed: int, seeds: int,
          max_decisions: int, card_pool: str = "whitelist",
          verify_replays: bool = False,
          distinct_opponents: bool = False,
          count_card_actions: bool = False,
          repeat_seeds: bool = False,
          random_extra: bool = False,
          fusion_stress: bool = False,
          agent_name: str = "random") -> dict:
    if card_pool not in ("whitelist", "tournament", "indianapolis-2005"):
        raise ValueError("unknown card pool")
    if agent_name not in ("random", "tactical"):
        raise ValueError("unknown probe agent")
    if random_extra and card_pool != "whitelist":
        raise ValueError("random Extra Decks require the whitelist card pool")
    if fusion_stress and not random_extra:
        raise ValueError("Fusion stress requires random Extra Decks")
    output.mkdir(parents=True, exist_ok=True)
    games = []
    offered: Counter[tuple[int, str]] = Counter()
    selected: Counter[tuple[int, str]] = Counter()
    responses: Counter[tuple[int, int]] = Counter()
    visibility_counts: Counter[str] = Counter()
    visibility_games = 0
    repeated_games = 0
    repeated_decisions = 0
    loaded_assets: dict[str, str] = {}
    rules_profile = None
    tactical_metadata = ((load_flip_monster_codes(root), load_card_races(root),
                          load_card_facts(root)) if agent_name == "tactical" else None)
    source_names = (INDIANAPOLIS_2005_MAIN_DECKS if card_pool == "indianapolis-2005"
                    else TOURNAMENT_MAIN_DECKS)

    def agents_for(seed: int):
        if tactical_metadata is None:
            agent = RandomAgent(seed)
            return agent, agent
        flips, races, facts = tactical_metadata
        return (TacticalHeuristicAgent(flips, races, card_facts=facts),
                TacticalHeuristicAgent(flips, races, card_facts=facts))

    for seed in range(first_seed, first_seed + seeds):
        generator = (lambda deck_seed: generate_deck(
            root, deck_seed, include_random_extra=random_extra,
            fusion_stress=fusion_stress)
            if card_pool == "whitelist" else generate_tournament_mix(
                root, deck_seed, source_names=source_names))
        deck = generator(seed)
        path = output / f"seed_{seed}.ydk"
        write_deck(path, deck)
        opponent_path = path
        if distinct_opponents:
            opponent_path = output / f"seed_{seed}_opponent.ydk"
            write_deck(opponent_path, generator(seed + 1_000_000))
        decisions = 0
        verified = None
        kinds = set()
        try:
            with GoatEnvironment(str(path), str(opponent_path), seed,
                                 ExperimentalOcgcoreEngine(root)) as env:
                observation = env.reset()
                agents = agents_for(seed)
                while not env.is_terminal() and decisions < max_decisions:
                    actions = env.legal_actions()
                    kinds.update(action.kind for action in actions)
                    observation = env.step(agents[observation.acting_player].select_action(
                        observation, actions))
                    decisions += 1
                terminal = env.is_terminal()
                winner = env.result() if terminal else None
                trajectory = env.trajectory() if terminal else None
                verified = (verify_trajectory(trajectory,
                                              ExperimentalOcgcoreEngine(root))
                            if trajectory is not None and verify_replays else None)
                if verified is not None and verified != decisions:
                    raise RuntimeError("replay verifier returned a partial decision count")
                if verified is not None:
                    visibility_counts.update(audit_trajectory_visibility(trajectory))
                    visibility_games += 1
                if trajectory is not None and (card_pool in ("tournament", "indianapolis-2005")
                                               or verify_replays):
                    if rules_profile is None:
                        rules_profile = trajectory.rules_profile
                    elif rules_profile != trajectory.rules_profile:
                        raise RuntimeError("rules profile changed within probe")
                    for asset, digest in (trajectory.asset_sha256 or {}).items():
                        if asset in loaded_assets and loaded_assets[asset] != digest:
                            raise RuntimeError(f"native asset changed within probe: {asset}")
                        loaded_assets[asset] = digest
                if trajectory is not None and count_card_actions:
                    for record in trajectory.decisions:
                        count_source_actions(record.legal_actions,
                                             record.selected_action, offered, selected)
                        count_chain_response(record.observation,
                                             record.selected_action, responses)
            if repeat_seeds:
                if trajectory is None:
                    raise RuntimeError("cannot repeat a duel that did not reach terminal")
                with GoatEnvironment(str(path), str(opponent_path), seed,
                                     ExperimentalOcgcoreEngine(root)) as repeated:
                    repeated_observation = repeated.reset()
                    repeated_agents = agents_for(seed)
                    for _ in range(decisions):
                        if repeated.is_terminal():
                            raise RuntimeError("seeded repeat ended before the original duel")
                        repeated_actions = repeated.legal_actions()
                        repeated_observation = repeated.step(
                            repeated_agents[repeated_observation.acting_player].select_action(
                                repeated_observation, repeated_actions))
                    repeated_trajectory = repeated.trajectory() if repeated.is_terminal() else None
                    if (repeated_trajectory is None
                            or repeated_trajectory.decisions != trajectory.decisions
                            or repeated_trajectory.terminal_observation
                            != trajectory.terminal_observation
                            or repeated.result() != winner):
                        raise RuntimeError("seeded repeat changed decisions, state, or outcome")
                repeated_games += 1
                repeated_decisions += decisions
            error = None
        except (OSError, RuntimeError, ValueError) as exc:
            terminal, winner = False, None
            error = f"{type(exc).__name__}: {exc}"
        game = {"seed": seed, "deck": str(path), "deck_sha256": sha256_file(path),
                "decisions": decisions, "terminal": terminal, "winner": winner,
                "action_kinds": sorted(kinds), "error": error}
        if distinct_opponents:
            game["opponent_deck"] = str(opponent_path)
            game["opponent_deck_sha256"] = sha256_file(opponent_path)
        if verify_replays:
            game["replay_verified_decisions"] = verified if error is None else None
        if repeat_seeds:
            game["deterministic_repeat"] = error is None
        games.append(game)
    report = {"max_decisions": max_decisions, "games": games}
    if agent_name != "random":
        report["agent"] = agent_name
        report["agent_version"] = TacticalHeuristicAgent.teacher_version
    if card_pool != "whitelist":
        report["card_pool"] = card_pool
    if distinct_opponents:
        report["distinct_opponents"] = True
        report["opponent_seed_offset"] = 1_000_000
    if random_extra:
        report["random_extra"] = True
        report["extra_seed_offset"] = 2_000_000
    if fusion_stress:
        report["fusion_stress"] = True
    if card_pool in ("tournament", "indianapolis-2005") or verify_replays:
        report["rules_profile"] = rules_profile
        report["loaded_asset_sha256"] = dict(sorted(loaded_assets.items()))
        report["asset_sha256"] = {
            name: sha256_file(root / relative)
            for name, relative in {
                "core_library": "build/libocgcore.so",
                "cards_database": "database/cards.cdb",
                "goat_database": "database/goat-entries.cdb",
                "goat_whitelist": "banlist/GOAT.lflist.conf",
                "global_constants": "scripts/constant.lua",
                "global_utility": "scripts/utility.lua",
            }.items()
        }
    if card_pool in ("tournament", "indianapolis-2005"):
        source_root = Path(__file__).resolve().parents[1] / "examples/decks"
        report["source_deck_sha256"] = {
            name: sha256_file(source_root / name) for name in (
                INDIANAPOLIS_2005_MAIN_DECKS if card_pool == "indianapolis-2005"
                else TOURNAMENT_MAIN_DECKS)
        }
    if verify_replays:
        report["replay_verification"] = {
            "verified_games": sum(game["replay_verified_decisions"] is not None
                                  for game in games),
            "verified_decisions": sum(game["replay_verified_decisions"] or 0
                                      for game in games),
        }
        report["visibility_audit"] = {
            "audited_games": visibility_games,
            **dict(sorted(visibility_counts.items())),
        }
    if repeat_seeds:
        report["determinism"] = {"repeated_games": repeated_games,
                                 "identical_decisions": repeated_decisions}
    if count_card_actions:
        report["card_actions"] = [
            {"code": code, "kind": kind, "offered_decisions": offered[code, kind],
             "selected_decisions": selected[code, kind]}
            for code, kind in sorted(offered)
        ]
        report["chain_responses"] = [
            {"responder_code": responder, "preceding_link_code": preceding,
             "selected_decisions": count}
            for (responder, preceding), count in sorted(
                responses.items(), key=lambda item: (-item[1], item[0]))
        ]
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def probe_isolated(root: Path, output: Path, first_seed: int, seeds: int,
                   max_decisions: int, card_pool: str = "whitelist",
                   verify_replays: bool = False,
                   distinct_opponents: bool = False,
                   count_card_actions: bool = False,
                   repeat_seeds: bool = False,
                   random_extra: bool = False,
                   fusion_stress: bool = False,
                   agent_name: str = "random") -> dict:
    """Run each native duel in a child process so one crash does not erase the sweep."""
    if agent_name not in ("random", "tactical"):
        raise ValueError("unknown probe agent")
    if output.exists() and any(output.iterdir()):
        raise ValueError("isolated probe output must be empty")
    output.mkdir(parents=True, exist_ok=True)
    reports = []
    games = []
    for seed in range(first_seed, first_seed + seeds):
        directory = output / "isolated" / f"seed_{seed}"
        command = [sys.executable, str(Path(__file__).resolve()),
                   "--native-root", str(root.resolve()), "--output", str(directory.resolve()),
                   "--seed", str(seed), "--seeds", "1", "--max-decisions", str(max_decisions),
                   "--card-pool", card_pool]
        if agent_name != "random":
            command.extend(("--agent", agent_name))
        for enabled, flag in ((verify_replays, "--verify-replays"),
                              (distinct_opponents, "--distinct-opponents"),
                              (count_card_actions, "--count-card-actions"),
                              (repeat_seeds, "--repeat-seeds"),
                              (random_extra, "--random-extra"),
                              (fusion_stress, "--fusion-stress")):
            if enabled:
                command.append(flag)
        completed = subprocess.run(command, capture_output=True, text=True,
                                   check=False)
        report_path = directory / "report.json"
        if completed.returncode in (0, 1) and report_path.is_file():
            report = json.loads(report_path.read_text())
            if len(report.get("games", ())) != 1 or report["games"][0]["seed"] != seed:
                raise ValueError(f"isolated worker returned the wrong seed: {seed}")
            reports.append(report)
            games.extend(report["games"])
        else:
            deck = directory / f"seed_{seed}.ydk"
            opponent = directory / f"seed_{seed}_opponent.ydk"
            game = {"seed": seed, "deck": str(deck),
                    "deck_sha256": sha256_file(deck) if deck.is_file() else None,
                    "decisions": 0, "terminal": False, "winner": None,
                    "action_kinds": [],
                    "error": f"isolated worker exited {completed.returncode}"}
            if distinct_opponents:
                game["opponent_deck"] = str(opponent)
                game["opponent_deck_sha256"] = (sha256_file(opponent)
                                                 if opponent.is_file() else None)
            if verify_replays:
                game["replay_verified_decisions"] = None
            if repeat_seeds:
                game["deterministic_repeat"] = False
            games.append(game)
    merged = {"max_decisions": max_decisions, "games": games, "isolated_games": True,
              "worker_reports": [str(output / "isolated" / f"seed_{seed}" / "report.json")
                                 for seed in range(first_seed, first_seed + seeds)]}
    for flag, value in (("card_pool", card_pool if card_pool != "whitelist" else None),
                        ("distinct_opponents", distinct_opponents),
                        ("random_extra", random_extra), ("fusion_stress", fusion_stress)):
        if value:
            merged[flag] = value
    if agent_name != "random":
        merged["agent"] = agent_name
        merged["agent_version"] = TacticalHeuristicAgent.teacher_version
    if any((report.get("agent", "random") != agent_name
            or agent_name == "tactical" and report.get("agent_version")
            != TacticalHeuristicAgent.teacher_version) for report in reports):
        raise ValueError("isolated worker used a different probe agent")
    if distinct_opponents:
        merged["opponent_seed_offset"] = 1_000_000
    if random_extra:
        merged["extra_seed_offset"] = 2_000_000
    if reports:
        for field in ("rules_profile", "asset_sha256", "source_deck_sha256"):
            values = [report[field] for report in reports
                      if field in report and report[field] is not None]
            if values:
                if any(value != values[0] for value in values[1:]):
                    raise ValueError(f"isolated worker {field} changed within sweep")
                merged[field] = values[0]
        loaded = {}
        for report in reports:
            for asset, digest in report.get("loaded_asset_sha256", {}).items():
                if asset in loaded and loaded[asset] != digest:
                    raise ValueError(f"isolated worker changed native asset: {asset}")
                loaded[asset] = digest
        if loaded:
            merged["loaded_asset_sha256"] = dict(sorted(loaded.items()))
    if verify_replays:
        merged["replay_verification"] = {
            "verified_games": sum(r["replay_verification"]["verified_games"] for r in reports),
            "verified_decisions": sum(r["replay_verification"]["verified_decisions"]
                                      for r in reports)}
        counts: Counter[str] = Counter()
        for report in reports:
            counts.update(report["visibility_audit"])
        merged["visibility_audit"] = dict(sorted(counts.items()))
    if repeat_seeds:
        merged["determinism"] = {
            "repeated_games": sum(r["determinism"]["repeated_games"] for r in reports),
            "identical_decisions": sum(r["determinism"]["identical_decisions"]
                                       for r in reports)}
    if count_card_actions:
        actions: dict[tuple[int, str], list[int]] = {}
        responses: Counter[tuple[int, int]] = Counter()
        for report in reports:
            for row in report["card_actions"]:
                item = actions.setdefault((row["code"], row["kind"]), [0, 0])
                item[0] += row["offered_decisions"]
                item[1] += row["selected_decisions"]
            for row in report["chain_responses"]:
                responses[row["responder_code"], row["preceding_link_code"]] += (
                    row["selected_decisions"])
        merged["card_actions"] = [
            {"code": code, "kind": kind, "offered_decisions": values[0],
             "selected_decisions": values[1]}
            for (code, kind), values in sorted(actions.items())]
        merged["chain_responses"] = [
            {"responder_code": responder, "preceding_link_code": preceding,
             "selected_decisions": count}
            for (responder, preceding), count in sorted(
                responses.items(), key=lambda item: (-item[1], item[0]))]
    (output / "report.json").write_text(json.dumps(merged, indent=2) + "\n")
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--output", type=Path, default=Path(".cache/goat-ai/random-probe"))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--seeds", type=int, default=10)
    parser.add_argument("--max-decisions", type=int, default=500)
    parser.add_argument("--card-pool", choices=("whitelist", "tournament",
                                                "indianapolis-2005"),
                        default="whitelist")
    parser.add_argument("--agent", choices=("random", "tactical"), default="random",
                        help="visible-observation agent used by both seats")
    parser.add_argument("--verify-replays", action="store_true")
    parser.add_argument("--distinct-opponents", action="store_true",
                        help="generate an independent legal opponent deck per seed")
    parser.add_argument("--count-card-actions", action="store_true",
                        help="count source-card options and selected chain responses")
    parser.add_argument("--repeat-seeds", action="store_true",
                        help="rerun each complete duel and require identical decisions, terminal state, and outcome")
    parser.add_argument("--random-extra", action="store_true",
                        help="add 15 random whitelist-legal Fusion cards to each generated Extra Deck")
    parser.add_argument("--fusion-stress", action="store_true",
                        help="with --random-extra, add three Scapegoat/Metamorphosis copies and Thousand-Eyes Restrict")
    parser.add_argument("--isolate-games", action="store_true",
                        help="run each seed in a separate process and keep going after a native crash")
    args = parser.parse_args()
    if args.seeds < 1 or args.max_decisions < 1:
        parser.error("--seeds and --max-decisions must be positive")
    runner = probe_isolated if args.isolate_games else probe
    report = runner(args.native_root, args.output, args.seed, args.seeds,
                    args.max_decisions, args.card_pool, args.verify_replays,
                    args.distinct_opponents, args.count_card_actions,
                    args.repeat_seeds, args.random_extra, args.fusion_stress,
                    args.agent)
    for game in report["games"]:
        status = "error" if game["error"] else "terminal" if game["terminal"] else "limit"
        suffix = f" error={game['error']}" if game["error"] else ""
        print(f"seed={game['seed']} decisions={game['decisions']} status={status}{suffix}")
    print(f"report={args.output / 'report.json'}")
    if any(game["error"] or ((args.verify_replays or args.repeat_seeds)
                             and not game["terminal"])
           for game in report["games"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
