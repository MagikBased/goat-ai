"""D.D. Survivor returns only after being banished face-up from the field.

Archived individual FAQ: https://www.goatformat.com/rulings2.html
"""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SURVIVOR = 48092532
BOTTOMLESS = 504700052  # GOAT variant
NOBLEMAN = 504700116  # GOAT variant, Semi-Limited
SKILL_DRAIN = 82732705


def _deck(path: Path, card: int, copies: int) -> str:
    cards = [card] * copies + list(VANILLA_DECK[:40 - copies])
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("faceup_banish", [True, False])
def test_survivor_end_phase_return_depends_on_faceup_field_banish(
        tmp_path, faceup_banish):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    own = (_deck(tmp_path / "trap.ydk", BOTTOMLESS, 3) if faceup_banish else
           _deck(tmp_path / "survivor.ydk", SURVIVOR, 3))
    other = (_deck(tmp_path / "survivor.ydk", SURVIVOR, 3) if faceup_banish else
             _deck(tmp_path / "nobleman.ydk", NOBLEMAN, 2))
    owner = 1 if faceup_banish else 0
    with GoatEnvironment(own, other, seed=11,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        initiated = banished = end_phase_trigger = checked = False
        agents = (RandomAgent(11), RandomAgent(12))
        for _ in range(5000):
            if env.is_terminal():
                assert initiated and banished and checked
                if faceup_banish:
                    assert end_phase_trigger
                else:
                    assert not end_phase_trigger
                trajectory = env.trajectory()
                path = tmp_path / f"survivor_faceup_{faceup_banish}.json"
                write_trajectory(path, trajectory)
                saved = read_trajectory(path)
                assert verify_trajectory(saved, ExperimentalOcgcoreEngine(root)) == len(
                    trajectory.decisions)
                audit_trajectory_visibility(saved)
                required = {f"official/c{SURVIVOR}.lua",
                            f"goat/c{BOTTOMLESS if faceup_banish else NOBLEMAN}.lua"}
                assert required <= env.engine.probe.loaded_script_sha256.keys()
                return

            actions = env.legal_actions()
            action = None
            if not checked:
                if obs.turn == 1 and obs.acting_player == 0 and not initiated:
                    kind = "set_spell_trap" if faceup_banish else "set_monster"
                    code = BOTTOMLESS if faceup_banish else SURVIVOR
                    action = next((a for a in actions if a.kind == kind
                                   and a.parameters.get("code") == code), None)
                    initiated |= action is not None
                if obs.turn == 2 and obs.acting_player == 1:
                    kind = "normal_summon" if faceup_banish else "activate"
                    code = SURVIVOR if faceup_banish else NOBLEMAN
                    action = next((a for a in actions if a.kind == kind
                                   and a.parameters.get("code") == code), action)
                if faceup_banish and obs.turn == 2 and obs.acting_player == 0:
                    action = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == BOTTOMLESS), action)
                if (faceup_banish and obs.turn == 2 and obs.phase == "end"
                        and obs.acting_player == owner):
                    trigger = next((a for a in actions if a.kind == "chain"
                                    and a.parameters.get("code") == SURVIVOR), None)
                    if trigger is not None:
                        action = trigger
                        end_phase_trigger = True
                if not faceup_banish and obs.turn == 2 and actions[0].kind == "select_card":
                    assert all(a.parameters.get("code") is None for a in actions)
                if obs.turn >= 3 and obs.phase == "main1":
                    if faceup_banish:
                        assert any(
                            c.code == SURVIVOR and c.controller == owner
                            and c.position == "faceup" for c in obs.field)
                        assert SURVIVOR not in {c.code for c in obs.banished[owner]}
                    else:
                        assert SURVIVOR in {c.code for c in obs.banished[owner]}
                        assert not any(c.code == SURVIVOR for c in obs.field)
                    checked = True
                if not checked and action is None:
                    action = next((a for a in actions if a.kind in (
                        "select_card", "place", "select_position", "pass", "end_phase")),
                        actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if obs.turn == 2 and SURVIVOR in {c.code for c in obs.banished[owner]}:
                banished = True
                if not faceup_banish:
                    opponent_view = env.engine.probe.observation(1)
                    assert SURVIVOR in {c.code for c in opponent_view.banished[owner]}
        pytest.fail(f"D.D. Survivor duel did not terminate; faceup={faceup_banish}")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_skill_drain_on_field_does_not_negate_banished_survivor(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    own = tmp_path / "bottomless_drain.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        *([BOTTOMLESS] * 3), *([SKILL_DRAIN] * 3), *VANILLA_DECK[:34])))
                   + "\n#extra\n!side\n")
    other = _deck(tmp_path / "survivor.ydk", SURVIVOR, 3)
    with GoatEnvironment(str(own), other, seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        set_cards = set()
        drain_active = summoned = bottomless_used = survivor_triggered = checked = False
        agents = (RandomAgent(15), RandomAgent(16))
        for _ in range(5000):
            if env.is_terminal():
                assert set_cards == {BOTTOMLESS, SKILL_DRAIN}
                assert drain_active and summoned and bottomless_used
                assert survivor_triggered and checked
                trajectory = env.trajectory()
                path = tmp_path / "survivor_skill_drain.json"
                write_trajectory(path, trajectory)
                saved = read_trajectory(path)
                assert verify_trajectory(saved, ExperimentalOcgcoreEngine(root)) == len(
                    trajectory.decisions)
                audit_trajectory_visibility(saved)
                assert {f"official/c{SURVIVOR}.lua", f"official/c{SKILL_DRAIN}.lua",
                        f"goat/c{BOTTOMLESS}.lua"} <= (
                            env.engine.probe.loaded_script_sha256.keys())
                return

            actions = env.legal_actions()
            action = None
            if not checked:
                if obs.turn == 1 and obs.acting_player == 0:
                    for code in (BOTTOMLESS, SKILL_DRAIN):
                        if code not in set_cards:
                            action = next((a for a in actions
                                           if a.kind == "set_spell_trap"
                                           and a.parameters.get("code") == code), None)
                            if action is not None:
                                set_cards.add(code)
                                break
                if obs.turn == 2 and obs.phase == "draw" and obs.acting_player == 0 \
                        and not drain_active:
                    action = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == SKILL_DRAIN), action)
                    drain_active |= action is not None and action.kind == "chain"
                if obs.turn == 2 and obs.phase == "main1":
                    if obs.acting_player == 1 and not summoned:
                        action = next((a for a in actions if a.kind == "normal_summon"
                                       and a.parameters.get("code") == SURVIVOR), action)
                        summoned |= action is not None and action.kind == "normal_summon"
                    if obs.acting_player == 0 and not bottomless_used:
                        action = next((a for a in actions if a.kind == "chain"
                                       and a.parameters.get("code") == BOTTOMLESS), action)
                        bottomless_used |= action is not None and action.kind == "chain"
                if obs.turn == 2 and obs.phase == "end" and obs.acting_player == 1:
                    trigger = next((a for a in actions if a.kind == "chain"
                                    and a.parameters.get("code") == SURVIVOR), None)
                    if trigger is not None:
                        assert trigger.parameters.get("location") == 32  # Banished zone
                        action = trigger
                        survivor_triggered = True
                if obs.turn >= 3 and obs.phase == "main1":
                    assert obs.life_points == (7000, 8000)  # Skill Drain cost
                    assert any(c.code == SKILL_DRAIN and c.position == "faceup"
                               for c in obs.field)
                    assert any(c.code == SURVIVOR and c.controller == 1
                               and c.position == "faceup" for c in obs.field)
                    assert SURVIVOR not in {c.code for c in obs.banished[1]}
                    checked = True
                if not checked and action is None:
                    action = next((a for a in actions if a.kind in (
                        "select_card", "place", "select_position", "pass", "end_phase")),
                        actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if (obs.turn == 2 and bottomless_used and not survivor_triggered
                    and SURVIVOR in {c.code for c in obs.banished[1]}):
                assert any(c.code == SKILL_DRAIN and c.position == "faceup"
                           for c in obs.field)
        pytest.fail("D.D. Survivor/Skill Drain duel did not terminate")
