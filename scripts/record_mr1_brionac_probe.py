"""Record a narrow MR1 Brionac double-activation and own-target probe."""

import argparse
from pathlib import Path

from goat_ai.agents import RandomAgent
from goat_ai.engine.mr1_synchro_probe import BRIONAC, JUNK_SYNCHRON, Mr1SynchroProbeEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import write_trajectory
from scripts.record_mr1_goyo_probe import DARK_BLADE, GIANT_SOLDIER


def setup_action(view, actions, activations: int):
    wanted = None
    if view.turn == 1 and view.acting_player == 0 and view.phase == "main1":
        wanted = next((a for a in actions if a.kind == "set_monster"
                       and a.parameters.get("code") == GIANT_SOLDIER), None)
    elif view.turn == 2 and view.acting_player == 1:
        if view.phase == "main1":
            wanted = (next((a for a in actions if a.kind == "normal_summon"
                            and a.parameters.get("code") == DARK_BLADE), None)
                      or next((a for a in actions if a.kind == "battle_phase"), None))
        elif view.phase.startswith("battle"):
            wanted = next((a for a in actions if a.kind == "attack"), None)
    elif view.turn == 3 and view.acting_player == 0 and view.phase == "main1":
        wanted = (next((a for a in actions if a.kind == "normal_summon"
                        and a.parameters.get("code") == JUNK_SYNCHRON), None)
                  or next((a for a in actions if a.kind == "special_summon"
                           and a.parameters.get("code") == BRIONAC), None)
                  or (next((a for a in actions if a.kind == "activate"
                            and a.parameters.get("code") == BRIONAC), None)
                      if activations < 2 else None))
    if wanted is not None:
        return wanted
    # One discarded card per activation, then one field target. The first
    # target is opposing Dark Blade; the second is Brionac itself.
    finish = next((a for a in actions if a.kind == "finish_selection"), None)
    if finish is not None:
        return finish
    target = next((a for a in actions if a.kind == "select_card"
                   and a.parameters.get("location") == 4
                   and a.parameters.get("controller") == (1 if activations == 1 else 0)), None)
    if target is not None:
        return target
    return next((a for a in actions if a.kind in (
        "select_card", "select_cards", "place", "select_position", "pass",
        "end_phase", "no")), actions[0])


def record_probe(native_root: Path, *, seed: int = 5, max_decisions: int = 5000):
    fixtures = Path(__file__).resolve().parents[1] / "examples/decks"
    decks = (fixtures / "mr1_brionac_probe.ydk", fixtures / "vanilla_reverse.ydk")
    agents = (RandomAgent(seed), RandomAgent(seed + 1))
    activations = []
    targets = []
    with GoatEnvironment(*(str(deck) for deck in decks), seed=seed,
                         engine=Mr1SynchroProbeEngine(native_root)) as env:
        view = env.reset()
        script_hash = None
        for index in range(max_decisions):
            actions = env.legal_actions()
            action = (setup_action(view, actions, len(activations))
                      if len(targets) < 2 else
                      agents[view.acting_player].select_action(view, actions))
            if action.kind == "activate" and action.parameters.get("code") == BRIONAC:
                activations.append(index + 1)
            if (action.kind == "select_card" and action.parameters.get("location") == 4
                    and len(activations) > len(targets)):
                targets.append((action.parameters.get("controller"),
                                action.parameters.get("code"), index + 1))
            view = env.step(action)
            if script_hash is None:
                script_hash = env.engine.probe.loaded_script_sha256.get(
                    f"official/c{BRIONAC}.lua")
            if env.is_terminal():
                break
        else:
            raise RuntimeError("MR1 Brionac probe exceeded decision cap")
        if len(activations) != 2 or len(targets) != 2 or script_hash is None:
            raise RuntimeError("MR1 Brionac double-activation branch not reached")
        return env.trajectory(), tuple(activations), tuple(targets), script_hash


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--seed", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    trajectory, activations, targets, script_hash = record_probe(
        args.native_root, seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_trajectory(args.output, trajectory)
    print(f"MR1 Brionac: activations={activations}, targets={targets}, "
          f"terminal after {len(trajectory.decisions)}, winner={trajectory.winner}, "
          f"patched_script_sha256={script_hash}")


if __name__ == "__main__":
    main()
