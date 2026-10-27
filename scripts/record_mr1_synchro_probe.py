"""Record a seeded Junk Synchron → Junk Warrior MR1 protocol fixture."""

import argparse
from pathlib import Path

from goat_ai.agents import RandomAgent
from goat_ai.engine.mr1_synchro_probe import (
    BOKOICHI,
    JUNK_SYNCHRON,
    JUNK_WARRIOR,
    Mr1SynchroProbeEngine,
)
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import write_trajectory


def select_setup_action(view, actions):
    """Force one Synchro test path; not an agent or a playing strategy."""
    wanted = None
    if view.turn == 1 and view.acting_player == 0 and view.phase == "main1":
        wanted = next((a for a in actions if a.kind == "set_monster"
                       and a.parameters.get("code") == BOKOICHI), None)
    if view.turn == 2 and view.acting_player == 1 and view.phase == "main1":
        wanted = (next((a for a in actions if a.kind == "normal_summon"
                        and a.parameters.get("code") == 69140098), None)
                  or next((a for a in actions if a.kind == "battle_phase"), None))
    if view.turn == 2 and view.acting_player == 1 and view.phase.startswith("battle"):
        wanted = next((a for a in actions if a.kind == "attack"), None)
    if view.turn == 3 and view.acting_player == 0 and view.phase == "main1":
        wanted = (next((a for a in actions if a.kind == "normal_summon"
                        and a.parameters.get("code") == JUNK_SYNCHRON), None)
                  or next((a for a in actions if a.kind == "special_summon"
                           and a.parameters.get("code") == JUNK_WARRIOR), None))
    if wanted is None:
        wanted = next((a for a in actions if a.kind in (
            "yes", "select_card", "finish_selection")), None)
    if wanted is None:
        wanted = next((a for a in actions if a.kind in ("end_phase", "pass")), actions[0])
    return wanted


def select_attack_probe_action(view, actions):
    """Leave a second Level 2 monster on field for Junk Warrior's trigger."""
    wanted = None
    if view.turn == 1 and view.acting_player == 0 and view.phase == "main1":
        wanted = next((a for a in actions if a.kind == "set_monster"
                       and a.parameters.get("code") == BOKOICHI), None)
    if view.turn == 2 and view.acting_player == 1:
        if view.phase == "main1":
            wanted = (next((a for a in actions if a.kind == "normal_summon"
                            and a.parameters.get("code") == 49881766), None)
                      or next((a for a in actions if a.kind == "battle_phase"), None))
        elif view.phase.startswith("battle"):
            wanted = next((a for a in actions if a.kind == "attack"), None)
    if view.turn == 3 and view.acting_player == 0 and view.phase == "main1":
        wanted = next((a for a in actions if a.kind == "normal_summon"
                       and a.parameters.get("code") == BOKOICHI), None)
    if view.turn == 5 and view.acting_player == 0 and view.phase == "main1":
        wanted = (next((a for a in actions if a.kind == "normal_summon"
                        and a.parameters.get("code") == JUNK_SYNCHRON), None)
                  or next((a for a in actions if a.kind == "special_summon"
                           and a.parameters.get("code") == JUNK_WARRIOR), None))
    if wanted is None:
        wanted = next((a for a in actions if a.kind in (
            "yes", "select_card", "finish_selection", "place", "select_position",
            "end_phase", "pass")), actions[0])
    return wanted


def record_attack_probe(native_root: Path, max_decisions: int = 5000):
    """Return a complete seeded duel after checking the native +500 ATK line."""
    fixtures = Path(__file__).resolve().parents[1] / "examples/decks"
    decks = (fixtures / "mr1_junk_warrior_probe.ydk",
             fixtures / "vanilla_reverse.ydk")
    seed = 18  # opening hand contains two Bokoichi and Junk Synchron
    agents = (RandomAgent(seed), RandomAgent(seed + 1))
    with GoatEnvironment(*(str(deck) for deck in decks), seed=seed,
                         engine=Mr1SynchroProbeEngine(native_root)) as env:
        view = env.reset()
        summoned_at = None
        boosted_at = None
        for index in range(max_decisions):
            actions = env.legal_actions()
            action = (select_attack_probe_action(view, actions) if boosted_at is None else
                      agents[view.acting_player].select_action(view, actions))
            view = env.step(action)
            warrior = next((card for card in view.field
                            if card.code == JUNK_WARRIOR and card.controller == 0), None)
            if warrior is not None and summoned_at is None:
                summoned_at = index + 1
                if warrior.attack != 2300:
                    raise AssertionError("Junk Warrior's pre-trigger ATK changed")
            if warrior is not None and warrior.attack == 2800 and boosted_at is None:
                boosted_at = index + 1
                if not any(card.code == BOKOICHI and card.controller == 0
                           for card in view.field):
                    raise AssertionError("Junk Warrior gained ATK without the Level 2 card")
            if env.is_terminal():
                break
        else:
            raise RuntimeError("MR1 Junk Warrior ATK probe exceeded decision cap")
        if summoned_at is None or boosted_at is None:
            raise RuntimeError("MR1 Junk Warrior ATK trigger was not resolved")
        return env.trajectory(), (summoned_at, boosted_at)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--seed", type=int, default=3)
    parser.add_argument("--max-decisions", type=int, default=5000)
    parser.add_argument("--attack-probe", action="store_true",
                        help="record seed 18 with a surviving Level 2 monster")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.attack_probe:
        trajectory, (summoned_at, boosted_at) = record_attack_probe(
            args.native_root, args.max_decisions)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_trajectory(args.output, trajectory)
        print(f"MR1 Junk Warrior ATK: summoned at decision {summoned_at}, "
              f"boosted at {boosted_at}, terminal after {len(trajectory.decisions)}, "
              f"winner={trajectory.winner}")
        return
    fixtures = Path(__file__).resolve().parents[1] / "examples/decks"
    decks = (fixtures / "mr1_junk_warrior_probe.ydk",
             fixtures / "vanilla_reverse.ydk")
    agents = (RandomAgent(args.seed), RandomAgent(args.seed + 1))
    with GoatEnvironment(*(str(deck) for deck in decks), seed=args.seed,
                         engine=Mr1SynchroProbeEngine(args.native_root)) as env:
        view = env.reset()
        summoned_at = None
        for index in range(args.max_decisions):
            actions = env.legal_actions()
            action = (select_setup_action(view, actions) if summoned_at is None else
                      agents[view.acting_player].select_action(view, actions))
            view = env.step(action)
            if summoned_at is None and any(card.code == JUNK_WARRIOR
                                           for card in view.field):
                summoned_at = index + 1
            if env.is_terminal():
                break
        else:
            raise RuntimeError("MR1 Synchro probe exceeded decision cap")
        trajectory = env.trajectory()
    if summoned_at is None:
        raise RuntimeError("probe duel ended without summoning Junk Warrior")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_trajectory(args.output, trajectory)
    print(f"MR1 Synchro protocol: summoned at decision {summoned_at}, "
          f"terminal after {len(trajectory.decisions)}, winner={trajectory.winner}")


if __name__ == "__main__":
    main()
