"""Airknight pierces a battle-immune Spirit Reaper and draws for damage."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

GRACEFUL_CHARITY = 79571449
PREMATURE_BURIAL = 70828912
AIRKNIGHT = 18036057
SPIRIT_REAPER = 504700038
WABOKU = 12607053
SECOND_DISCARD = 79182538


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("waboku", [False, True])
def test_airknight_pierces_reaper_without_destroying_it(tmp_path, waboku):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"official/c{GRACEFUL_CHARITY}.lua",
               f"official/c{PREMATURE_BURIAL}.lua",
               f"official/c{AIRKNIGHT}.lua", f"goat/c{SPIRIT_REAPER}.lua")
    if waboku:
        scripts += (f"official/c{WABOKU}.lua",)
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("Airknight / Reaper scripts not installed")
    own = tmp_path / "airknight.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL_CHARITY, PREMATURE_BURIAL, AIRKNIGHT,
        *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    other = tmp_path / "reaper.ydk"
    other.write_text("#main\n" + "\n".join(map(str, (
        SPIRIT_REAPER, SPIRIT_REAPER, SPIRIT_REAPER,
        *([WABOKU] * 3 if waboku else VANILLA_DECK[3:6]),
        *VANILLA_DECK[6:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(own), str(other), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        graceful = discarded = premature = reaper_set = waboku_set = False
        attacked = target_chosen = waboku_used = damage_step = checked = False
        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"airknight_reaper_{waboku}.json"
                write_trajectory(path, env.trajectory())
                trajectory = read_trajectory(path)
                assert verify_trajectory(trajectory,
                                         ExperimentalOcgcoreEngine(root)) == len(
                    trajectory.decisions)
                audit_trajectory_visibility(trajectory)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL_CHARITY), None)
                    graceful |= action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"]
                                   for c in a.parameters["cards"]} == {
                                       AIRKNIGHT, SECOND_DISCARD}), None)
                    discarded |= action is not None
                if discarded and not premature and action is None:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == PREMATURE_BURIAL), None)
                    premature |= action is not None
                if premature and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == AIRKNIGHT
                                   and a.parameters.get("location") == 16), action)
            if obs.turn == 2 and obs.acting_player == 1:
                if not reaper_set:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == SPIRIT_REAPER), None)
                    reaper_set |= action is not None
                if waboku and reaper_set and not waboku_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == WABOKU), None)
                    waboku_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and reaper_set:
                if obs.phase == "main1":
                    action = next((a for a in actions if a.kind == "battle_phase"), action)
                if obs.phase == "battle_start" and not attacked:
                    assert any(c.controller == 1 and c.zone == "monster"
                               and c.position == "facedown" and c.code is None
                               for c in obs.field)
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == AIRKNIGHT), action)
                    attacked |= action is not None and action.kind == "attack"
                if attacked and not target_chosen and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("controller") == 1
                                   and a.parameters.get("location") == 4), None)
                    target_chosen |= action is not None
            if waboku and attacked and obs.turn == 3 and obs.phase == "battle_step" \
                    and obs.acting_player == 1 and not waboku_used:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == WABOKU), action)
                waboku_used |= action is not None and action.kind == "chain"
            if target_chosen and obs.turn == 3 and obs.phase == "damage_step":
                damage_step = True
            if damage_step and not checked and obs.turn == 3 \
                    and obs.phase == "battle_step" and obs.acting_player == 0:
                assert obs.life_points == ((7200, 8000) if waboku else (7200, 6300))
                assert obs.deck_counts[0] == (30 if waboku else 29)
                assert any(c.code == SPIRIT_REAPER and c.controller == 1
                           and c.position == "faceup" and c.orientation == "defense"
                           for c in obs.field)
                assert SPIRIT_REAPER not in {c.code for c in obs.graveyards[1]}
                assert all(script in env.engine.probe.loaded_script_sha256
                           for script in scripts)
                checked = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "select_card", "select_position", "place", "pass", "main2",
                    "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
    pytest.fail("Airknight / Reaper duel did not finish")
