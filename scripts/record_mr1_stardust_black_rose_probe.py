"""Record the narrow MR1 Stardust response to Black Rose Dragon's wipe."""

import argparse
from pathlib import Path

from goat_ai.agents import RandomAgent
from goat_ai.engine.mr1_synchro_probe import (
    BLACK_ROSE_DRAGON,
    CURSE_OF_DRAGON,
    JUNK_SYNCHRON,
    STARDUST_DRAGON,
    Mr1SynchroProbeEngine,
)
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import write_trajectory

KABAZAULS = 51934376
GEMINI_ELF = 69140098
SURVIVING_NORMAL = 79182538
SETUP = (
    (1, 0, "normal_summon", KABAZAULS),
    (2, 1, "normal_summon", GEMINI_ELF),
    (3, 0, "normal_summon", CURSE_OF_DRAGON),
    (4, 1, "normal_summon", SURVIVING_NORMAL),
    (5, 0, "normal_summon", JUNK_SYNCHRON),
    (5, 0, "special_summon", STARDUST_DRAGON),
    (6, 1, "normal_summon", JUNK_SYNCHRON),
    (6, 1, "special_summon", BLACK_ROSE_DRAGON),
)


def select_setup_action(view, actions, completed, *, negate: bool):
    """Choose only the fixture line; all remaining play uses RandomAgent."""
    for step in SETUP:
        turn, seat, kind, code = step
        if step in completed or view.turn != turn or view.acting_player != seat:
            continue
        action = next((item for item in actions if item.kind == kind
                       and item.parameters.get("code") == code), None)
        if action is not None:
            completed.add(step)
            return action, False
    if view.turn == 6 and view.acting_player == 1:
        action = next((item for item in actions if item.kind == "yes"
                       and item.parameters.get("code") == BLACK_ROSE_DRAGON), None)
        if action is not None:
            return action, False
    if view.turn == 6 and view.acting_player == 0 and any(
            item.kind == "chain" and item.parameters.get("code") == STARDUST_DRAGON
            for item in actions):
        kind = "chain" if negate else "pass"
        action = next(item for item in actions if item.kind == kind
                      and (kind == "pass" or
                           item.parameters.get("code") == STARDUST_DRAGON))
        return action, True
    preferences = ("yes", "select_card", "finish_selection", "place",
                   "select_position", "end_phase", "pass", "no")
    return next((item for kind in preferences for item in actions
                 if item.kind == kind), actions[0]), False


def record_probe(native_root: Path, *, negate: bool, seed: int = 955,
                 max_decisions: int = 5000):
    fixtures = Path(__file__).resolve().parents[1] / "examples/decks"
    decks = (fixtures / "mr1_stardust_probe.ydk",
             fixtures / "mr1_black_rose_probe.ydk")
    agents = (RandomAgent(seed), RandomAgent(seed + 1))
    completed = set()
    choice = resolution = returned = None
    with GoatEnvironment(*(str(deck) for deck in decks), seed=seed,
                         engine=Mr1SynchroProbeEngine(native_root)) as env:
        view = env.reset()
        for index in range(max_decisions):
            actions = env.legal_actions()
            if resolution is None or negate and returned is None:
                action, response = select_setup_action(view, actions, completed,
                                                       negate=negate)
                if response:
                    choice = (action.kind, index + 1)
            else:
                action = agents[view.acting_player].select_action(view, actions)
            view = env.step(action)
            field = {(card.code, card.controller) for card in view.field}
            own_grave = {card.code for card in view.graveyards[0]}
            opposing_grave = {card.code for card in view.graveyards[1]}
            if (choice is not None and resolution is None
                    and STARDUST_DRAGON in own_grave
                    and BLACK_ROSE_DRAGON in opposing_grave
                    and ((SURVIVING_NORMAL, 1) in field) == negate):
                resolution = index + 1
            if (negate and resolution is not None and returned is None
                    and (STARDUST_DRAGON, 0) in field):
                returned = index + 1
            if env.is_terminal():
                break
        else:
            raise RuntimeError("MR1 Stardust/Black Rose duel exceeded decision cap")
        if (set(SETUP) != completed or choice is None or resolution is None
                or choice[0] != ("chain" if negate else "pass")
                or (negate and returned is None)):
            raise RuntimeError(f"MR1 Stardust/Black Rose branch was not reached: "
                               f"completed={completed}, choice={choice}, "
                               f"resolution={resolution}, returned={returned}")
        return env.trajectory(), (choice, resolution, returned)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--seed", type=int, default=955)
    parser.add_argument("--max-decisions", type=int, default=5000)
    parser.add_argument("--decline", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    trajectory, events = record_probe(args.native_root, negate=not args.decline,
                                      seed=args.seed, max_decisions=args.max_decisions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_trajectory(args.output, trajectory)
    print(f"MR1 Stardust/Black Rose: {events}, terminal after "
          f"{len(trajectory.decisions)}, winner={trajectory.winner}")


if __name__ == "__main__":
    main()
