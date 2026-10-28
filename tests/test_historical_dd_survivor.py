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
