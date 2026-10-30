"""Reaper equipped during Skill Drain dies if Drain leaves the field."""

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
SNATCH_STEAL = 45986603
MYSTICAL_SPACE_TYPHOON = 5318639


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("remove_drain", [False, True])
def test_reaper_equip_survives_drain_then_dies_when_drain_removed(tmp_path,
                                                                   remove_drain):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"goat/c{SPIRIT_REAPER}.lua",
               *(f"official/c{code}.lua" for code in (
                   SKILL_DRAIN, SNATCH_STEAL, MYSTICAL_SPACE_TYPHOON)))
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("Reaper / Skill Drain / Snatch / Typhoon scripts not installed")
    own = tmp_path / "reaper_drain.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        *([SPIRIT_REAPER] * 3), *([SKILL_DRAIN] * 3),
        *VANILLA_DECK[6:]))) + "\n#extra\n!side\n")
    other = tmp_path / "snatch_mst.ydk"
    other.write_text("#main\n" + "\n".join(map(str, (
        SNATCH_STEAL, MYSTICAL_SPACE_TYPHOON, *VANILLA_DECK[2:])))
        + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(other), seed=72,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {SPIRIT_REAPER, SKILL_DRAIN} <= {c.code for c in obs.hand}
        assert {SNATCH_STEAL, MYSTICAL_SPACE_TYPHOON} <= {
            c.code for c in env.engine.probe.observation(1).hand}
        summoned = drain_set = snatch_used = snatch_targeted = False
        drain_used = snatch_resolved = mst_used = mst_targeted = checked = False
        agents = (RandomAgent(72), RandomAgent(73))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"reaper_drain_equip_{remove_drain}.json"
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
                if not summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == SPIRIT_REAPER), None)
                    summoned |= action is not None
                if summoned and not drain_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == SKILL_DRAIN), None)
                    drain_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not snatch_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SNATCH_STEAL), None)
                snatch_used |= action is not None
            if snatch_used and not snatch_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == SPIRIT_REAPER and a.parameters.get("controller") == 0), None)
                snatch_targeted |= action is not None
            if snatch_targeted and obs.acting_player == 0 and not drain_used:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SKILL_DRAIN), action)
                drain_used |= action is not None and action.kind == "chain"
            if drain_used and not snatch_resolved and obs.turn == 2 \
                    and obs.acting_player == 1 and obs.phase == "main1" \
                    and not obs.chain and any(c.code == SNATCH_STEAL
                                              for c in obs.field):
                assert any(c.code == SPIRIT_REAPER and c.controller == 1
                           for c in obs.field)
                assert SPIRIT_REAPER not in {c.code for c in obs.graveyards[0]}
                assert obs.life_points == (7000, 8000)
                snatch_resolved = True
            if snatch_resolved and remove_drain and not mst_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == MYSTICAL_SPACE_TYPHOON),
                              action)
                mst_used |= action is not None and action.kind == "activate" \
                    and action.parameters.get("code") == MYSTICAL_SPACE_TYPHOON
            if mst_used and not mst_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == SKILL_DRAIN and a.parameters.get("controller") == 0), None)
                mst_targeted |= action is not None
            if snatch_resolved and not checked and obs.turn == 2 \
                    and obs.acting_player == 1 and obs.phase == "main1" \
                    and not obs.chain and (not remove_drain or
                                           MYSTICAL_SPACE_TYPHOON in {
                                               c.code for c in obs.graveyards[1]}):
                assert mst_used == mst_targeted == remove_drain
                assert (SPIRIT_REAPER in {c.code for c in obs.graveyards[0]}) \
                    == remove_drain
                assert any(c.code == SPIRIT_REAPER and c.controller == 1
                           for c in obs.field) != remove_drain
                assert set(scripts if remove_drain else scripts[:3]) <= \
                    env.engine.probe.loaded_script_sha256.keys()
                checked = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
    pytest.fail(f"Reaper / Drain Equip branch unfinished: checked={checked} "
                f"turn={obs.turn} phase={obs.phase} snatch={snatch_resolved} "
                f"mst={mst_used}/{mst_targeted}")
