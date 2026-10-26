"""Export a replay-verified Scapegoat End Phase timing diagnostic.

This scripted synthetic scenario is an evaluation probe, not human gameplay.
"""

import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path

from goat_ai.agents import RandomAgent, TacticalHeuristicAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SCAPEGOAT = 504700123
DECKS = Path(__file__).resolve().parent.parent / "examples/decks"


def timing_records(trajectory):
    """Yield the three scripted End Phase windows before random continuation."""
    for index, record in enumerate(trajectory.decisions):
        observation = record.observation
        if (observation.turn in (3, 4, 5) and observation.phase == "end"
                and observation.acting_player == 1
                and any(action.kind == "chain"
                        and action.parameters.get("code") == SCAPEGOAT
                        for action in record.legal_actions)):
            yield index, record


def curriculum_records(trajectory):
    """Include early Scapegoat opportunities and the later activation."""
    for index, record in enumerate(trajectory.decisions):
        observation = record.observation
        if (observation.turn <= 5 and observation.acting_player == 1
                and len(record.legal_actions) > 1
                and any(action.kind in ("activate", "chain", "set_spell_trap")
                        and action.parameters.get("code") == SCAPEGOAT
                        for action in record.legal_actions)):
            yield index, record


def write_scripted_labels(label_path: Path, trajectory_path: Path, records) -> None:
    labels = {
        "schema_version": 1,
        "source_trajectory_sha256": hashlib.sha256(trajectory_path.read_bytes()).hexdigest(),
        "authorization": "scripted_scenario",
        "reviewer": "GOAT AI deterministic timing probe",
        "choices": [{"decision_index": index,
                     "action_index": record.legal_actions.index(record.selected_action)}
                    for index, record in records],
    }
    label_path.write_text(json.dumps(labels, indent=2) + "\n")


def run_probe(native_root: Path, output: Path, *, seed: int = 52,
              deck_a: Path | None = None, deck_b: Path | None = None):
    """Complete and verify a native duel with both turn-owner timing windows."""
    plain = deck_a or DECKS / "vanilla_probe.ydk"
    goat = deck_b or DECKS / "scapegoat_timing_probe.ydk"
    with GoatEnvironment(str(plain), str(goat), seed=seed,
                         engine=ExperimentalOcgcoreEngine(native_root)) as env:
        observation = env.reset()
        tactical = TacticalHeuristicAgent()
        random_agents = (RandomAgent(7), RandomAgent(8))
        set_goat = False
        for _ in range(5000):
            if env.is_terminal():
                break
            legal = env.legal_actions()
            action = None
            goat_response = next((candidate for candidate in legal
                                  if candidate.kind == "chain"
                                  and candidate.parameters.get("code") == SCAPEGOAT), None)
            if (observation.turn == 2 and observation.acting_player == 1
                    and not set_goat):
                action = next((candidate for candidate in legal
                               if candidate.kind == "set_spell_trap"
                               and candidate.parameters.get("code") == SCAPEGOAT), None)
                set_goat |= action is not None
            if (goat_response is not None and observation.phase == "end"
                    and observation.acting_player == 1):
                if observation.turn == 3:
                    action = next(candidate for candidate in legal
                                  if candidate.kind == "pass")
                elif observation.turn in (4, 5):
                    action = tactical.select_action(observation, legal)
            if observation.turn <= 5 and action is None:
                action = next((candidate for candidate in legal
                               if candidate.kind in ("place", "pass", "end_phase", "main2")),
                              None)
            if action is None:
                action = random_agents[observation.acting_player].select_action(
                    observation, legal)
            observation = env.step(action)
        if not env.is_terminal() or not set_goat:
            raise RuntimeError("Scapegoat timing probe did not finish its scripted duel")
        trajectory = replace(env.trajectory(), source="scripted_timing_probe",
                             skill_metadata={"scenario": "scapegoat_end_turn_owner"})
    choices = [(record.observation.turn, record.observation.turn_player,
                record.selected_action.kind) for _, record in timing_records(trajectory)]
    if choices != [(3, 0, "pass"), (4, 1, "pass"), (5, 0, "chain")]:
        raise RuntimeError(f"unexpected Scapegoat timing decisions: {choices}")
    write_trajectory(output, trajectory)
    verified = verify_trajectory(read_trajectory(output),
                                 ExperimentalOcgcoreEngine(native_root))
    if verified != len(trajectory.decisions):
        raise RuntimeError("Scapegoat timing replay was not fully verified")
    write_scripted_labels(output.with_suffix(".labels.json"), output,
                          timing_records(trajectory))
    write_scripted_labels(output.with_suffix(".curriculum.labels.json"), output,
                          curriculum_records(trajectory))
    return trajectory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--seed", type=int, default=52)
    parser.add_argument("--deck-a", type=Path)
    parser.add_argument("--deck-b", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--checkpoint", type=Path, action="append", default=[])
    args = parser.parse_args()
    if (args.deck_a or args.deck_b) and args.output is None:
        parser.error("--output is required when choosing custom decks")
    output = args.output or Path(f"replays/scapegoat_end_timing_probe_seed{args.seed}.json")
    trajectory = run_probe(args.native_root, output, seed=args.seed,
                           deck_a=args.deck_a, deck_b=args.deck_b)
    report = {"replay": str(output),
              "labels": str(output.with_suffix(".labels.json")),
              "curriculum_labels": str(output.with_suffix(".curriculum.labels.json")),
              "verified_decisions": len(trajectory.decisions),
              "scripted_choices": [{"decision": i, "turn": record.observation.turn,
                                    "turn_player": record.observation.turn_player,
                                    "selected": record.selected_action.kind}
                                   for i, record in timing_records(trajectory)],
              "checkpoints": []}
    if args.checkpoint:
        from goat_ai.training import load_policy_agent

        for checkpoint in args.checkpoint:
            agent = load_policy_agent(checkpoint)
            guarded = load_policy_agent(checkpoint, tactical_guard=True)
            report["checkpoints"].append({
                "path": str(checkpoint),
                "choices": [{"decision": i, "selected": agent.select_action(
                    record.observation, record.legal_actions).kind}
                    for i, record in timing_records(trajectory)],
                "guarded_choices": [{"decision": i, "selected": guarded.select_action(
                    record.observation, record.legal_actions).kind}
                    for i, record in timing_records(trajectory)],
            })
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
