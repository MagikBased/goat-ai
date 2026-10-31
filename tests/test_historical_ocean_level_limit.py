"""A Legendary Ocean changes which WATER monsters Level Limit turns to Defense."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

OCEAN = 295517
GAGAGIGO = 49003308
LEVEL_LIMIT = 3136426


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("activate_ocean", (False, True), ids=("without_ocean", "ocean"))
def test_ocean_changes_level_limit_position_effect(tmp_path, activate_ocean):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{OCEAN}.lua", f"official/c{LEVEL_LIMIT}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required pinned card scripts not installed")
    remaining = list(VANILLA_DECK)
    remaining.remove(GAGAGIGO)
    attacker = tmp_path / "water.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        OCEAN, GAGAGIGO, *remaining[:38]))) + "\n#extra\n!side\n")
    defender = tmp_path / "level_limit.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        LEVEL_LIMIT, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {OCEAN, GAGAGIGO} <= {c.code for c in obs.hand}
        assert LEVEL_LIMIT in {c.code for c in env.engine.probe.observation(1).hand}
        ocean_used = summoned = limit_used = checked = False
        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(3000):
            if env.is_terminal():
                break
            actions = env.legal_actions()
            action = None
            if not checked:
                if obs.turn == 1 and obs.acting_player == 0:
                    if activate_ocean and not ocean_used:
                        action = next((a for a in actions if a.kind == "activate"
                                       and a.parameters.get("code") == OCEAN), None)
                        ocean_used |= action is not None
                    if not summoned and action is None:
                        action = next((a for a in actions if a.kind == "normal_summon"
                                       and a.parameters.get("code") == GAGAGIGO), None)
                        summoned |= action is not None
                if obs.turn == 2 and obs.acting_player == 1 and not limit_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == LEVEL_LIMIT), None)
                    limit_used |= action is not None
                if (limit_used and not obs.chain and obs.acting_player == 1
                        and any(c.code == LEVEL_LIMIT and c.position == "faceup"
                                for c in obs.field)):
                    monster = next(c for c in obs.field if c.code == GAGAGIGO)
                    assert monster.level == (3 if activate_ocean else 4)
                    assert monster.orientation == ("attack" if activate_ocean else "defense")
                    checked = True
            if action is None:
                action = (next((a for a in actions if a.kind in
                               ("place", "pass", "end_phase")), actions[0]) if not checked
                          else agents[obs.acting_player].select_action(obs, actions))
            obs = env.step(action)
        assert checked and env.is_terminal(), "Ocean/Level Limit duel did not finish"
        assert scripts <= env.engine.probe.loaded_script_sha256.keys()
        path = tmp_path / f"level_limit_{activate_ocean}.json"
        write_trajectory(path, env.trajectory())
    replay = read_trajectory(path)
    assert audit_trajectory_visibility(replay)["decisions"] == len(replay.decisions)
    assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(replay.decisions)
