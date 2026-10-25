"""Skill Drain negates D.D. Warrior Lady's optional Damage Step banish."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

DD_WARRIOR_LADY = 7572887
GEMINI_ELF = 69140098
SKILL_DRAIN = 82732705


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("activate_drain", [False, True])
def test_skill_drain_before_damage_step_negates_warrior_lady_banish(
        tmp_path, activate_drain):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (DD_WARRIOR_LADY, SKILL_DRAIN)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("D.D. Warrior Lady / Skill Drain scripts not installed")
    own = tmp_path / "warrior_lady.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        DD_WARRIOR_LADY, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    other = tmp_path / "elf_drain.ydk"
    remaining = list(VANILLA_DECK[4:])
    remaining[remaining.index(GEMINI_ELF)] = VANILLA_DECK[0]
    other.write_text("#main\n" + "\n".join(map(str, (
        GEMINI_ELF, *([SKILL_DRAIN] * 3), *remaining))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(other), seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert DD_WARRIOR_LADY in {c.code for c in obs.hand}
        assert {GEMINI_ELF, SKILL_DRAIN} <= {
            c.code for c in env.engine.probe.observation(1).hand}
        lady_summoned = elf_summoned = drain_set = attacked = drain_window = False
        lady_effect = False
        for _ in range(100):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not lady_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == DD_WARRIOR_LADY), None)
                lady_summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not elf_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == GEMINI_ELF), None)
                    elf_summoned |= action is not None
                elif not drain_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == SKILL_DRAIN), None)
                    drain_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not attacked:
                if obs.phase == "main1":
                    action = next((a for a in actions if a.kind == "battle_phase"), action)
                elif obs.phase in ("battle_start", "battle_step"):
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == DD_WARRIOR_LADY), action)
                    attacked |= action is not None and action.kind == "attack"
            if attacked and obs.acting_player == 1 and not drain_window:
                drain = next((a for a in actions if a.kind == "chain"
                              and a.parameters.get("code") == SKILL_DRAIN), None)
                if drain is not None:
                    assert obs.phase == "battle_step"
                    action = drain if activate_drain else next(
                        a for a in actions if a.kind == "pass")
                    drain_window = True
            if attacked and obs.acting_player == 0 and obs.phase == "damage_step" \
                    and not lady_effect:
                effect = next((a for a in actions if a.kind == "yes"
                               and a.parameters.get("code") == DD_WARRIOR_LADY), None)
                if effect is not None:
                    action = effect
                    lady_effect = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "main2", "end_phase")), actions[0])
            obs = env.step(action)
            if lady_effect and obs.turn == 3 and obs.phase == "main2":
                own_view = env.engine.probe.observation(0)
                assert drain_window and own_view.life_points == (
                    7600, 7000 if activate_drain else 8000)
                assert not any(c.code == DD_WARRIOR_LADY for c in own_view.field)
                if activate_drain:
                    assert DD_WARRIOR_LADY in {
                        c.code for c in own_view.graveyards[0]}
                    assert GEMINI_ELF in {c.code for c in own_view.field}
                    assert not any(c.code in (DD_WARRIOR_LADY, GEMINI_ELF)
                                   for cards in own_view.banished for c in cards)
                    assert SKILL_DRAIN in {c.code for c in own_view.field}
                else:
                    assert DD_WARRIOR_LADY in {
                        c.code for c in own_view.banished[0]}
                    assert GEMINI_ELF in {c.code for c in own_view.banished[1]}
                    assert not any(c.code == SKILL_DRAIN for c in own_view.field)
                required = (scripts if activate_drain else
                            {f"official/c{DD_WARRIOR_LADY}.lua"})
                assert required <= env.engine.probe.loaded_script_sha256.keys()
                agents = (RandomAgent(52), RandomAgent(53))
                for _ in range(5000):
                    obs = env.step(agents[obs.acting_player].select_action(
                        obs, env.legal_actions()))
                    if env.is_terminal():
                        path = tmp_path / f"lady_drain_{activate_drain}.json"
                        write_trajectory(path, env.trajectory())
                        assert verify_trajectory(read_trajectory(path),
                                                 ExperimentalOcgcoreEngine(root)) == len(
                                                     env.trajectory().decisions)
                        return
                pytest.fail("D.D. Warrior Lady / Skill Drain duel did not finish")
    pytest.fail(f"battle did not resolve: turn={obs.turn} phase={obs.phase} "
                f"summons={(lady_summoned, elf_summoned)} set={drain_set} "
                f"attacked={attacked} drain_window={drain_window} "
                f"effect={lady_effect}")
