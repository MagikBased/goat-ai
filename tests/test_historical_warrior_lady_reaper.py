"""D.D. Warrior Lady can banish a Reaper that survives battle destruction."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

WARRIOR_LADY = 7572887
SPIRIT_REAPER = 504700038


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("banish", [False, True])
def test_warrior_lady_can_banish_battle_immune_reaper(tmp_path, banish):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{WARRIOR_LADY}.lua").is_file():
        pytest.skip("D.D. Warrior Lady script not installed")
    if not (root / f"scripts/goat/c{SPIRIT_REAPER}.lua").is_file():
        pytest.skip("GOAT Spirit Reaper script not installed")
    decks = []
    for name, code in (("warrior", WARRIOR_LADY), ("reaper", SPIRIT_REAPER)):
        path = tmp_path / f"{name}.ydk"
        path.write_text("#main\n" + "\n".join(map(str, (
            code, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
        decks.append(str(path))

    with GoatEnvironment(*decks, seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        summoned = reaper_set = attacked = targeted = choice_seen = checked = False
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(5000):
            if env.is_terminal():
                assert checked, (summoned, reaper_set, attacked, targeted,
                                 choice_seen, obs.turn, obs.phase, obs.life_points)
                path = tmp_path / f"warrior_lady_reaper_{banish}.json"
                write_trajectory(path, env.trajectory())
                trajectory = read_trajectory(path)
                assert verify_trajectory(trajectory,
                                         ExperimentalOcgcoreEngine(root)) == len(
                    trajectory.decisions)
                audit_trajectory_visibility(trajectory)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == WARRIOR_LADY), None)
                summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not reaper_set:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == SPIRIT_REAPER), None)
                reaper_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and reaper_set and not attacked:
                action = next((a for a in actions if a.kind in ("battle_phase", "attack")
                               and (a.kind != "attack" or
                                    a.parameters.get("code") == WARRIOR_LADY)), None)
                attacked |= action is not None and action.kind == "attack"
            if attacked and not targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 4), None)
                targeted |= action is not None
            if targeted and not choice_seen and obs.acting_player == 0:
                option = next((a for a in actions if a.kind == "yes"
                               and a.parameters.get("code") == WARRIOR_LADY), None)
                if option is not None:
                    assert obs.phase == "damage_step"
                    assert obs.life_points == (8000, 8000)
                    assert any(c.code == SPIRIT_REAPER and c.position == "faceup"
                               and c.orientation == "defense" for c in obs.field)
                    choice_seen = True
                    action = option if banish else next(a for a in actions
                                                       if a.kind == "no")
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "main2", "end_phase")),
                    actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if choice_seen and not checked and obs.turn == 3 and obs.phase == "main2":
                assert summoned and reaper_set and attacked and targeted
                assert obs.life_points == (8000, 8000)
                assert (SPIRIT_REAPER in {c.code for c in obs.banished[1]}) == banish
                assert (WARRIOR_LADY in {c.code for c in obs.banished[0]}) == banish
                assert SPIRIT_REAPER not in {c.code for c in obs.graveyards[1]}
                if banish:
                    assert not any(c.code in (SPIRIT_REAPER, WARRIOR_LADY)
                                   for c in obs.field)
                else:
                    assert any(c.code == SPIRIT_REAPER and c.orientation == "defense"
                               for c in obs.field)
                    assert any(c.code == WARRIOR_LADY for c in obs.field)
                assert {f"goat/c{SPIRIT_REAPER}.lua",
                        f"official/c{WARRIOR_LADY}.lua"} <= (
                            env.engine.probe.loaded_script_sha256.keys())
                checked = True
    pytest.fail("Warrior Lady / Reaper duel did not finish")
