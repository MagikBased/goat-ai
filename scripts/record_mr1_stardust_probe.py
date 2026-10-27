"""Record an MR1 Stardust Dragon versus Mirror Force protocol interaction."""

import argparse
from pathlib import Path

from goat_ai.agents import RandomAgent
from goat_ai.engine.mr1_synchro_probe import (
    CURSE_OF_DRAGON,
    JUNK_SYNCHRON,
    MIRROR_FORCE,
    STARDUST_DRAGON,
    Mr1SynchroProbeEngine,
)
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import write_trajectory

KABAZAULS = 51934376


def select_setup_action(view, actions, completed, *, negate: bool):
    """Choose only the scripted setup and response; this is not an agent."""
    steps = (
        (1, 0, "normal_summon", KABAZAULS),
        (2, 1, "set_spell_trap", MIRROR_FORCE),
        (3, 0, "normal_summon", CURSE_OF_DRAGON),
        (5, 0, "normal_summon", JUNK_SYNCHRON),
        (5, 0, "special_summon", STARDUST_DRAGON),
        (5, 1, "chain", MIRROR_FORCE),
        (5, 0, "chain" if negate else "pass", STARDUST_DRAGON),
    )
    for step in steps:
        turn, seat, kind, code = step
        if view.turn != turn or view.acting_player != seat or step in completed:
            continue
        action = next((item for item in actions if item.kind == kind
                       and (item.parameters.get("code") == code
                            if kind != "pass" else any(
                                option.kind == "chain"
                                and option.parameters.get("code") == code
                                for option in actions))), None)
        if action is not None:
            completed.add(step)
            return action
    if view.turn == 5 and view.acting_player == 0:
        preferences = ("yes", "select_card", "finish_selection", "place",
                       "select_position", "battle_phase", "attack", "end_phase",
                       "pass", "no")
    else:
        preferences = ("yes", "select_card", "finish_selection", "place",
                       "select_position", "end_phase", "pass", "no")
    return next((item for kind in preferences for item in actions
                 if item.kind == kind), actions[0])


def record_probe(native_root: Path, seed: int = 536, *, negate: bool,
                 max_decisions: int = 5000):
    fixtures = Path(__file__).resolve().parents[1] / "examples/decks"
    decks = (fixtures / "mr1_stardust_probe.ydk",
             fixtures / "mr1_mirror_force_probe.ydk")
    agents = (RandomAgent(seed), RandomAgent(seed + 1))
    completed = set()
    choice = None
    destroyed = None
    revived = None
    with GoatEnvironment(*(str(deck) for deck in decks), seed=seed,
                         engine=Mr1SynchroProbeEngine(native_root)) as env:
        view = env.reset()
        for index in range(max_decisions):
            actions = env.legal_actions()
            if destroyed is not None and (not negate or revived is not None):
                action = agents[view.acting_player].select_action(view, actions)
            else:
                action = select_setup_action(view, actions, completed, negate=negate)
            if (view.turn == 5 and view.phase == "battle_step"
                    and view.acting_player == 0 and choice is None
                    and any(item.kind == "chain"
                            and item.parameters.get("code") == STARDUST_DRAGON
                            for item in actions)):
                choice = (action.kind, index + 1)
            view = env.step(action)
            field = {card.code for card in view.field if card.controller == 0}
            own_grave = {card.code for card in view.graveyards[0]}
            opposing_grave = {card.code for card in view.graveyards[1]}
            if (choice is not None and destroyed is None
                    and MIRROR_FORCE in opposing_grave
                    and STARDUST_DRAGON in own_grave):
                destroyed = index + 1
            if (negate and destroyed is not None and revived is None
                    and STARDUST_DRAGON in field):
                revived = index + 1
            if env.is_terminal():
                break
        else:
            raise RuntimeError("MR1 Stardust probe exceeded decision cap")
        required = {
            (1, 0, "normal_summon", KABAZAULS),
            (2, 1, "set_spell_trap", MIRROR_FORCE),
            (3, 0, "normal_summon", CURSE_OF_DRAGON),
            (5, 0, "normal_summon", JUNK_SYNCHRON),
            (5, 0, "special_summon", STARDUST_DRAGON),
            (5, 1, "chain", MIRROR_FORCE),
        }
        if (not required <= completed or choice is None
                or choice[0] != ("chain" if negate else "pass")
                or destroyed is None or (negate and revived is None)):
            raise RuntimeError("MR1 Stardust/Mirror Force branch was not reached")
        return env.trajectory(), (choice, destroyed, revived)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--seed", type=int, default=536)
    parser.add_argument("--max-decisions", type=int, default=5000)
    parser.add_argument("--decline", action="store_true",
                        help="decline Stardust's destruction negation")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    trajectory, (choice, destroyed, revived) = record_probe(
        args.native_root, args.seed, negate=not args.decline,
        max_decisions=args.max_decisions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_trajectory(args.output, trajectory)
    print(f"MR1 Stardust protocol: response={choice}, destroyed={destroyed}, "
          f"revived={revived}, terminal after {len(trajectory.decisions)}, "
          f"winner={trajectory.winner}")


if __name__ == "__main__":
    main()
