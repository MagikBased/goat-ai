"""Record a narrow MR1 Junk Warrior / Bottomless Trap Hole response probe."""

import argparse
from pathlib import Path

from goat_ai.agents import RandomAgent
from goat_ai.engine.mr1_synchro_probe import (
    BOKOICHI,
    BOTTOMLESS_TRAP_HOLE,
    JUNK_SYNCHRON,
    JUNK_WARRIOR,
    Mr1SynchroProbeEngine,
)
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import write_trajectory

SEED = 52
SETUP = (
    (1, 0, "set_monster", BOKOICHI),
    (2, 1, "set_spell_trap", BOTTOMLESS_TRAP_HOLE),
    (3, 0, "flip_summon", BOKOICHI),
    (3, 0, "normal_summon", JUNK_SYNCHRON),
    (3, 0, "special_summon", JUNK_WARRIOR),
)


def record_probe(native_root: Path, *, chain_bottomless: bool,
                 max_decisions: int = 5000):
    fixtures = Path(__file__).resolve().parents[1] / "examples/decks"
    decks = (fixtures / "mr1_junk_warrior_probe.ydk",
             fixtures / "mr1_bottomless_probe.ydk")
    agents = (RandomAgent(SEED), RandomAgent(SEED + 1))
    completed = set()
    offered_at = None
    resolved_at = None
    with GoatEnvironment(*(str(deck) for deck in decks), seed=SEED,
                         engine=Mr1SynchroProbeEngine(native_root)) as env:
        view = env.reset()
        for index in range(max_decisions):
            actions = env.legal_actions()
            if resolved_at is not None:
                action = agents[view.acting_player].select_action(view, actions)
            else:
                action = None
                for step in SETUP:
                    turn, seat, kind, code = step
                    if step in completed or (view.turn, view.acting_player) != (turn, seat):
                        continue
                    action = next((item for item in actions if item.kind == kind
                                   and item.parameters.get("code") == code), None)
                    if action is not None:
                        completed.add(step)
                        break
                response = next((item for item in actions if item.kind == "chain"
                                 and item.parameters.get("code") == BOTTOMLESS_TRAP_HOLE),
                                None)
                if response is not None and offered_at is None:
                    if set(completed) != set(SETUP):
                        raise AssertionError("Bottomless offered before the Synchro setup")
                    offered_at = index
                    action = response if chain_bottomless else next(
                        item for item in actions if item.kind == "pass")
                if action is None:
                    action = next((item for kind in (
                        "yes", "select_card", "finish_selection", "place",
                        "select_position", "end_phase", "pass", "no")
                        for item in actions if item.kind == kind), actions[0])
            view = env.step(action)
            if offered_at is not None and resolved_at is None:
                if chain_bottomless and any(card.code == BOTTOMLESS_TRAP_HOLE
                                            for card in view.graveyards[1]):
                    resolved_at = index + 1
                    if not any(card.code == JUNK_WARRIOR for card in view.banished[0]):
                        raise AssertionError("Bottomless did not banish Junk Warrior")
                elif (not chain_bottomless and index > offered_at
                      and not view.chain and any(card.code == JUNK_WARRIOR
                                                 for card in view.field)):
                    resolved_at = index + 1
                    if not any(card.position == "facedown" and card.code is None
                               and card.controller == 1 for card in view.field):
                        raise AssertionError("declined Bottomless was not left Set")
            if env.is_terminal():
                break
        else:
            raise RuntimeError("MR1 Bottomless probe exceeded decision cap")
        if set(completed) != set(SETUP) or offered_at is None or resolved_at is None:
            raise RuntimeError("MR1 Bottomless Synchro line did not complete")
        loaded_script = env.engine.probe.loaded_script_sha256.get(
            f"official/c{BOTTOMLESS_TRAP_HOLE}.lua")
        return env.trajectory(), offered_at, resolved_at, loaded_script


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--pass-bottomless", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    trajectory, offered, resolved, script = record_probe(
        args.native_root, chain_bottomless=not args.pass_bottomless)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_trajectory(args.output, trajectory)
    print(f"{args.output}: {len(trajectory.decisions)} decisions, "
          f"offered at {offered}, resolved at {resolved}, script {script}")


if __name__ == "__main__":
    main()
