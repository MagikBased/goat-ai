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


def select_attack_probe_action(view, actions, *, opposing_level_two: bool = False):
    """Leave a Level 2 monster on one side after Junk Warrior's Synchro Summon."""
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
    if (not opposing_level_two and view.turn == 3 and view.acting_player == 0
            and view.phase == "main1"):
        wanted = next((a for a in actions if a.kind == "normal_summon"
                       and a.parameters.get("code") == BOKOICHI), None)
    if (opposing_level_two and view.turn == 4 and view.acting_player == 1
            and view.phase == "main1"):
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


def record_attack_probe(native_root: Path, max_decisions: int = 5000, *,
                        opposing_level_two: bool = False):
    """Check whether only the controller's surviving Level 2 contributes ATK."""
    fixtures = Path(__file__).resolve().parents[1] / "examples/decks"
    decks = (fixtures / "mr1_junk_warrior_probe.ydk",
             fixtures / ("mr1_junk_warrior_opposing_level2.ydk" if opposing_level_two
                         else "vanilla_reverse.ydk"))
    seed = 100 if opposing_level_two else 18
    agents = (RandomAgent(seed), RandomAgent(seed + 1))
    with GoatEnvironment(*(str(deck) for deck in decks), seed=seed,
                         engine=Mr1SynchroProbeEngine(native_root)) as env:
        view = env.reset()
        summoned_at = None
        resolved_at = None
        for index in range(max_decisions):
            actions = env.legal_actions()
            action = (select_attack_probe_action(
                view, actions, opposing_level_two=opposing_level_two)
                if resolved_at is None else
                      agents[view.acting_player].select_action(view, actions))
            view = env.step(action)
            warrior = next((card for card in view.field
                            if card.code == JUNK_WARRIOR and card.controller == 0), None)
            if warrior is not None and summoned_at is None:
                summoned_at = index + 1
                if warrior.attack != 2300:
                    raise AssertionError("Junk Warrior's pre-trigger ATK changed")
            if (warrior is not None and summoned_at is not None
                    and index + 1 == summoned_at + 4):
                resolved_at = index + 1
                expected = 2300 if opposing_level_two else 2800
                if warrior.attack != expected:
                    raise AssertionError("Junk Warrior counted the wrong Level 2 monsters")
                if sum(card.code == BOKOICHI and card.controller == int(opposing_level_two)
                       for card in view.field) != 1:
                    raise AssertionError("the Level 2 witness did not survive on its side")
            if env.is_terminal():
                break
        else:
            raise RuntimeError("MR1 Junk Warrior ATK probe exceeded decision cap")
        if summoned_at is None or resolved_at is None:
            raise RuntimeError("MR1 Junk Warrior ATK trigger was not resolved")
        return env.trajectory(), (summoned_at, resolved_at)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--seed", type=int, default=3)
    parser.add_argument("--max-decisions", type=int, default=5000)
    probe = parser.add_mutually_exclusive_group()
    probe.add_argument("--attack-probe", action="store_true",
                       help="record seed 18 with a surviving Level 2 monster")
    probe.add_argument("--opposing-level-two", action="store_true",
                       help="record seed 100 with an opposing Level 2 monster")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.attack_probe or args.opposing_level_two:
        trajectory, (summoned_at, resolved_at) = record_attack_probe(
            args.native_root, args.max_decisions,
            opposing_level_two=args.opposing_level_two)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_trajectory(args.output, trajectory)
        print(f"MR1 Junk Warrior ATK: summoned at decision {summoned_at}, "
              f"resolved at {resolved_at}, terminal after {len(trajectory.decisions)}, "
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
