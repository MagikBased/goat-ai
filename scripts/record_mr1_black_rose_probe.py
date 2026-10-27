"""Record an MR1 Black Rose Dragon Synchro and optional field-wipe branch."""

import argparse
from pathlib import Path

from goat_ai.agents import RandomAgent
from goat_ai.engine.mr1_synchro_probe import (
    BLACK_ROSE_DRAGON,
    JUNK_SYNCHRON,
    Mr1SynchroProbeEngine,
)
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import write_trajectory

KABAZAULS = 51934376
GEMINI_ELF = 69140098


def select_setup_action(view, actions, *, activate: bool):
    """Force a test line through the native choices; not an AI strategy."""
    wanted = None
    if view.turn == 1 and view.acting_player == 0 and view.phase == "main1":
        wanted = next((a for a in actions if a.kind == "normal_summon"
                       and a.parameters.get("code") == KABAZAULS), None)
    if view.turn == 2 and view.acting_player == 1 and view.phase == "main1":
        wanted = next((a for a in actions if a.kind == "normal_summon"
                       and a.parameters.get("code") == GEMINI_ELF), None)
    if view.turn == 3 and view.acting_player == 0 and view.phase == "main1":
        wanted = (next((a for a in actions if a.kind == "normal_summon"
                        and a.parameters.get("code") == JUNK_SYNCHRON), None)
                  or next((a for a in actions if a.kind == "special_summon"
                           and a.parameters.get("code") == BLACK_ROSE_DRAGON), None))
    wanted = wanted or next((a for a in actions
                             if a.kind == ("yes" if activate else "no")
                             and a.parameters.get("code") == BLACK_ROSE_DRAGON), None)
    if wanted is None:
        wanted = next((a for a in actions if a.kind in (
            "select_card", "finish_selection", "place", "select_position",
            "pass", "end_phase", "no")), actions[0])
    return wanted


def record_probe(native_root: Path, seed: int, *, activate: bool,
                 max_decisions: int = 5000):
    fixtures = Path(__file__).resolve().parents[1] / "examples/decks"
    decks = (fixtures / "mr1_black_rose_probe.ydk", fixtures / "vanilla_reverse.ydk")
    agents = (RandomAgent(seed), RandomAgent(seed + 1))
    with GoatEnvironment(*(str(deck) for deck in decks), seed=seed,
                         engine=Mr1SynchroProbeEngine(native_root)) as env:
        view = env.reset()
        effect_choice = None
        board_checked = False
        for index in range(max_decisions):
            actions = env.legal_actions()
            if board_checked:
                action = agents[view.acting_player].select_action(view, actions)
            elif effect_choice is not None:
                action = next((a for a in actions if a.kind in ("pass", "no")), actions[0])
            else:
                action = select_setup_action(view, actions, activate=activate)
            if (action.kind in ("yes", "no")
                    and action.parameters.get("code") == BLACK_ROSE_DRAGON):
                effect_choice = (action.kind, index + 1)
            view = env.step(action)
            if effect_choice is not None and not board_checked:
                field_codes = {card.code for card in view.field}
                grave_codes = {card.code for pile in view.graveyards for card in pile}
                if activate:
                    board_checked = (BLACK_ROSE_DRAGON not in field_codes
                                     and GEMINI_ELF not in field_codes
                                     and {BLACK_ROSE_DRAGON, GEMINI_ELF} <= grave_codes)
                else:
                    board_checked = {BLACK_ROSE_DRAGON, GEMINI_ELF} <= field_codes
                if board_checked and view.life_points != (8000, 8000):
                    raise AssertionError("Black Rose setup changed Life Points")
            if env.is_terminal():
                break
        else:
            raise RuntimeError("MR1 Black Rose probe exceeded decision cap")
        if effect_choice is None or not board_checked:
            raise RuntimeError("MR1 Black Rose effect branch was not reached")
        return env.trajectory(), effect_choice


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--seed", type=int, default=3)
    parser.add_argument("--max-decisions", type=int, default=5000)
    parser.add_argument("--decline", action="store_true", help="decline the optional wipe")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    trajectory, choice = record_probe(args.native_root, args.seed,
                                      activate=not args.decline,
                                      max_decisions=args.max_decisions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_trajectory(args.output, trajectory)
    print(f"MR1 Black Rose protocol: {choice[0]} at decision {choice[1]}, "
          f"terminal after {len(trajectory.decisions)}, winner={trajectory.winner}")


if __name__ == "__main__":
    main()
