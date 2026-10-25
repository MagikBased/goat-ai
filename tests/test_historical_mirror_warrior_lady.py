"""Mirror Force stops D.D. Warrior Lady before the Damage Step."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

MIRROR_FORCE = 44095762
WARRIOR_LADY = 7572887


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_mirror_force_destroys_attacking_warrior_lady_before_battle_effect(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (MIRROR_FORCE, WARRIOR_LADY):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")

    paths = []
    for name, code in (("warrior", WARRIOR_LADY), ("mirror", MIRROR_FORCE)):
        path = tmp_path / f"{name}.ydk"
        path.write_text("#main\n" + "\n".join(map(str, (
            code, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
        paths.append(path)

    with GoatEnvironment(*(str(path) for path in paths), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        summoned = set_mirror = attacked = chained = checked = False
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / "mirror_warrior_lady.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == WARRIOR_LADY), None)
                summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not set_mirror:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == MIRROR_FORCE), None)
                set_mirror |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and set_mirror and not attacked:
                action = next((a for a in actions if a.kind in ("battle_phase", "attack")
                               and (a.kind != "attack" or
                                    a.parameters.get("code") == WARRIOR_LADY)), None)
                if action is not None and action.kind == "attack":
                    attacked = True
            if attacked and obs.acting_player == 1 and not chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == MIRROR_FORCE), None)
                if action is not None:
                    assert obs.phase == "battle_step"
                    chained = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if chained and not checked and any(
                    c.code == MIRROR_FORCE for c in obs.graveyards[1]):
                assert summoned and set_mirror and attacked
                assert any(c.code == WARRIOR_LADY for c in obs.graveyards[0])
                assert not any(c.code == WARRIOR_LADY for c in obs.banished[0])
                assert not any(c.code == WARRIOR_LADY for c in obs.field)
                assert obs.life_points == (8000, 8000)
                assert obs.chain == ()
                loaded = env.engine.probe.loaded_script_sha256
                assert f"official/c{WARRIOR_LADY}.lua" in loaded
                assert f"official/c{MIRROR_FORCE}.lua" in loaded
                checked = True
    pytest.fail("Mirror Force / Warrior Lady duel did not finish")
