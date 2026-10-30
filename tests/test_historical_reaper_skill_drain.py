"""Skill Drain removes Spirit Reaper's battle destruction immunity."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SPIRIT_REAPER = 504700038
SKILL_DRAIN = 82732705
GEMINI_ELF = 69140098


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("activate_drain", [False, True])
def test_skill_drain_allows_reaper_to_be_destroyed_by_battle(tmp_path, activate_drain):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"goat/c{SPIRIT_REAPER}.lua", f"official/c{SKILL_DRAIN}.lua")
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("GOAT Spirit Reaper / Skill Drain scripts not installed")

    defender = tmp_path / "reaper.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        SPIRIT_REAPER, SPIRIT_REAPER, SPIRIT_REAPER, *VANILLA_DECK[3:])))
        + "\n#extra\n!side\n")
    filler = list(VANILLA_DECK[4:])
    filler[filler.index(GEMINI_ELF)] = VANILLA_DECK[0]
    attacker = tmp_path / "elf_drain.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        GEMINI_ELF, SKILL_DRAIN, SKILL_DRAIN, SKILL_DRAIN, *filler)))
        + "\n#extra\n!side\n")

    with GoatEnvironment(str(defender), str(attacker), seed=11,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert SPIRIT_REAPER in {card.code for card in obs.hand}
        assert {GEMINI_ELF, SKILL_DRAIN} <= {
            card.code for card in env.engine.probe.observation(1).hand}
        reaper_set = elf_summoned = drain_set = drain_used = attacked = False
        target_chosen = damage_step_seen = checked = False
        agents = (RandomAgent(71), RandomAgent(72))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"reaper_drain_{activate_drain}.json"
                write_trajectory(path, env.trajectory())
                trajectory = read_trajectory(path)
                assert verify_trajectory(trajectory,
                                         ExperimentalOcgcoreEngine(root)) == len(
                    trajectory.decisions)
                audit_trajectory_visibility(trajectory)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not reaper_set:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == SPIRIT_REAPER), None)
                reaper_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not elf_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == GEMINI_ELF), None)
                    elf_summoned |= action is not None
                if elf_summoned and not drain_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == SKILL_DRAIN), None)
                    drain_set |= action is not None
            if obs.acting_player == 1 and drain_set and not drain_used:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SKILL_DRAIN), None)
                if option is not None:
                    action = (option if activate_drain and obs.turn == 3 else
                              next(a for a in actions if a.kind == "pass"))
                    drain_used = action is option
            if obs.turn == 4 and obs.acting_player == 1 and not attacked:
                if obs.phase == "main1":
                    action = next((a for a in actions if a.kind == "battle_phase"), action)
                elif obs.phase in ("battle_start", "battle_step"):
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == GEMINI_ELF), action)
                    attacked |= action is not None and action.kind == "attack"
            if attacked and not target_chosen and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 0
                               and a.parameters.get("location") == 4), None)
                target_chosen |= action is not None
            if target_chosen and obs.turn == 4 and obs.phase == "damage_step":
                damage_step_seen = True
            if damage_step_seen and obs.turn == 4 and obs.phase == "battle_step" \
                    and obs.acting_player == 1 and not checked:
                assert attacked and reaper_set and elf_summoned and drain_set
                assert drain_used == activate_drain
                assert obs.life_points == (8000, 7000 if activate_drain else 8000)
                assert (SPIRIT_REAPER in {c.code for c in obs.graveyards[0]}) \
                    == activate_drain
                assert any(c.code == SPIRIT_REAPER for c in obs.field) \
                    != activate_drain
                assert any(c.code == SKILL_DRAIN and c.position == (
                    "faceup" if activate_drain else "facedown") for c in obs.field)
                assert scripts[0] in env.engine.probe.loaded_script_sha256
                if activate_drain:
                    assert scripts[1] in env.engine.probe.loaded_script_sha256
                checked = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "main2", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
    pytest.fail(f"Reaper / Skill Drain branch did not finish: checked={checked} "
                f"turn={obs.turn} phase={obs.phase} attacked={attacked}")
