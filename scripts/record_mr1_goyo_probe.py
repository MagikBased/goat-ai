"""Record an MR1 Goyo line using its 2010 generic-Tuner material text."""

import argparse
from pathlib import Path

from goat_ai.agents import RandomAgent
from goat_ai.engine.mr1_synchro_probe import GOYO_GUARDIAN, JUNK_SYNCHRON, Mr1SynchroProbeEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import write_trajectory

GIANT_SOLDIER = 13039848
DARK_BLADE = 11321183


def select_setup_action(view, actions, *, activate: bool):
    """Force the native material, battle, and optional-effect branches."""
    wanted = None
    if view.turn == 1 and view.acting_player == 0 and view.phase == "main1":
        wanted = next((a for a in actions if a.kind == "set_monster"
                       and a.parameters.get("code") == GIANT_SOLDIER), None)
    if view.turn == 2 and view.acting_player == 1:
        if view.phase == "main1":
            wanted = (next((a for a in actions if a.kind == "normal_summon"
                            and a.parameters.get("code") == DARK_BLADE), None)
                      or next((a for a in actions if a.kind == "battle_phase"), None))
        elif view.phase.startswith("battle"):
            wanted = next((a for a in actions if a.kind == "attack"), None)
    if view.turn == 3 and view.acting_player == 0:
        if view.phase == "main1":
            wanted = (next((a for a in actions if a.kind == "normal_summon"
                            and a.parameters.get("code") == JUNK_SYNCHRON), None)
                      or next((a for a in actions if a.kind == "special_summon"
                               and a.parameters.get("code") == GOYO_GUARDIAN), None)
                      or next((a for a in actions if a.kind == "battle_phase"), None))
        elif view.phase.startswith("battle"):
            wanted = next((a for a in actions if a.kind == "attack"), None)
    wanted = wanted or next((a for a in actions
                             if a.kind == ("yes" if activate else "no")
                             and a.parameters.get("code") == GOYO_GUARDIAN), None)
    return wanted or next((a for a in actions if a.kind in (
        "select_card", "finish_selection", "place", "select_position",
        "pass", "end_phase", "no")), actions[0])


def record_probe(native_root: Path, *, activate: bool, seed: int = 5,
                 max_decisions: int = 5000):
    fixtures = Path(__file__).resolve().parents[1] / "examples/decks"
    decks = (fixtures / "mr1_goyo_probe.ydk", fixtures / "vanilla_reverse.ydk")
    agents = (RandomAgent(seed), RandomAgent(seed + 1))
    with GoatEnvironment(*(str(deck) for deck in decks), seed=seed,
                         engine=Mr1SynchroProbeEngine(native_root)) as env:
        view = env.reset()
        effect_choice = None
        board_checked = False
        loaded_script = None
        for index in range(max_decisions):
            actions = env.legal_actions()
            action = (agents[view.acting_player].select_action(view, actions)
                      if board_checked else
                      select_setup_action(view, actions, activate=activate))
            if (effect_choice is None and action.kind in ("yes", "no")
                    and action.parameters.get("code") == GOYO_GUARDIAN):
                effect_choice = (action.kind, index + 1)
            view = env.step(action)
            if effect_choice is not None and not board_checked:
                own_goyo = any(card.code == GOYO_GUARDIAN and card.controller == 0
                               for card in view.field)
                stolen = any(card.code == DARK_BLADE and card.controller == 0
                             and card.orientation == "defense" for card in view.field)
                discarded = any(card.code == DARK_BLADE for card in view.graveyards[1])
                board_checked = own_goyo and (stolen if activate else discarded)
                if board_checked:
                    loaded_script = env.engine.probe.loaded_script_sha256.get(
                        f"official/c{GOYO_GUARDIAN}.lua")
            if env.is_terminal():
                break
        else:
            raise RuntimeError("MR1 Goyo probe exceeded decision cap")
        if effect_choice is None or not board_checked or loaded_script is None:
            raise RuntimeError("MR1 Goyo effect branch was not reached")
        return env.trajectory(), effect_choice, loaded_script


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--seed", type=int, default=5)
    parser.add_argument("--decline", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    trajectory, choice, script_sha256 = record_probe(
        args.native_root, activate=not args.decline, seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_trajectory(args.output, trajectory)
    print(f"MR1 Goyo protocol: {choice[0]} at decision {choice[1]}, "
          f"terminal after {len(trajectory.decisions)}, winner={trajectory.winner}, "
          f"patched_script_sha256={script_sha256}")


if __name__ == "__main__":
    main()
