"""Record a narrow MR1 Junk Warrior / Bottomless Trap Hole response probe."""

import argparse
from pathlib import Path

from goat_ai.agents import RandomAgent
from goat_ai.engine.mr1_synchro_probe import (
    BOKOICHI,
    BOOK_OF_MOON,
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
                 book_response: bool | None = None,
                 max_decisions: int = 5000):
    if book_response is not None and not chain_bottomless:
        raise ValueError("Book response requires chaining Bottomless")
    fixtures = Path(__file__).resolve().parents[1] / "examples/decks"
    decks = (fixtures / ("mr1_junk_book_probe.ydk" if book_response is not None
                        else "mr1_junk_warrior_probe.ydk"),
             fixtures / "mr1_bottomless_probe.ydk")
    setup = (SETUP + ((1, 0, "set_spell_trap", BOOK_OF_MOON),)
             if book_response is not None else SETUP)
    agents = (RandomAgent(SEED), RandomAgent(SEED + 1))
    completed = set()
    offered_at = None
    resolved_at = None
    book_offered_at = None
    book_targeted = False
    with GoatEnvironment(*(str(deck) for deck in decks), seed=SEED,
                         engine=Mr1SynchroProbeEngine(native_root)) as env:
        view = env.reset()
        for index in range(max_decisions):
            actions = env.legal_actions()
            if resolved_at is not None:
                action = agents[view.acting_player].select_action(view, actions)
            else:
                action = None
                for step in setup:
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
                    if set(completed) != set(setup):
                        raise AssertionError("Bottomless offered before the Synchro setup")
                    offered_at = index
                    action = response if chain_bottomless else next(
                        item for item in actions if item.kind == "pass")
                if (book_response is not None and offered_at is not None
                        and book_offered_at is None and view.acting_player == 0):
                    book = next((item for item in actions if item.kind == "chain"
                                 and item.parameters.get("code") == BOOK_OF_MOON), None)
                    if book is not None:
                        book_offered_at = index
                        action = book if book_response else next(
                            item for item in actions if item.kind == "pass")
                if (book_response and book_offered_at is not None and not book_targeted
                        and actions[0].kind == "select_card"):
                    target = next((item for item in actions
                                   if item.parameters.get("code") == JUNK_WARRIOR
                                   and item.parameters.get("controller") == 0), None)
                    if target is not None:
                        action = target
                        book_targeted = True
                if action is None:
                    action = next((item for kind in (
                        "yes", "select_card", "finish_selection", "place",
                        "select_position", "end_phase", "pass", "no")
                        for item in actions if item.kind == kind), actions[0])
            view = env.step(action)
            if offered_at is not None and resolved_at is None:
                if (book_response is not None and book_offered_at is not None
                        and not view.chain
                        and any(card.code == BOTTOMLESS_TRAP_HOLE
                                for card in view.graveyards[1])):
                    resolved_at = index + 1
                    protected = any(card.code == JUNK_WARRIOR
                                    and card.position == "facedown"
                                    for card in view.field)
                    if protected != book_response:
                        raise AssertionError("Book/Bottomless Synchro result disagrees")
                elif chain_bottomless and any(card.code == BOTTOMLESS_TRAP_HOLE
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
        if set(completed) != set(setup) or offered_at is None or resolved_at is None:
            raise RuntimeError("MR1 Bottomless Synchro line did not complete")
        if book_response is not None and (book_offered_at is None
                                          or book_targeted != book_response):
            raise RuntimeError("MR1 Book response was not offered or targeted")
        loaded_script = env.engine.probe.loaded_script_sha256.get(
            f"official/c{BOTTOMLESS_TRAP_HOLE}.lua")
        return env.trajectory(), offered_at, resolved_at, loaded_script


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--pass-bottomless", action="store_true")
    parser.add_argument("--chain-book", action="store_true",
                        help="chain a pre-Set Book of Moon to Bottomless")
    parser.add_argument("--pass-book", action="store_true",
                        help="offer the same Book response but pass it")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if ((args.chain_book and args.pass_book)
            or (args.pass_bottomless and (args.chain_book or args.pass_book))):
        parser.error("Book response choices require chaining Bottomless; choose one Book branch")
    book_response = (True if args.chain_book else False if args.pass_book else None)
    trajectory, offered, resolved, script = record_probe(
        args.native_root, chain_bottomless=not args.pass_bottomless,
        book_response=book_response)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_trajectory(args.output, trajectory)
    print(f"{args.output}: {len(trajectory.decisions)} decisions, "
          f"offered at {offered}, resolved at {resolved}, script {script}")


if __name__ == "__main__":
    main()
