"""A public attack announcement cannot disclose a Set defender's identity."""

import os
from pathlib import Path

import pytest

from goat_ai.actions import Action
from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

DES_KOALA = 69579761
GEMINI_ELF = 69140098


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
def test_attacker_view_and_actions_ignore_set_defender_identity(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{DES_KOALA}.lua").is_file():
        pytest.skip("Des Koala script not installed")
    attacker = tmp_path / "attacker.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, VANILLA_DECK))
                        + "\n#extra\n!side\n")

    def run(hidden_code: int):
        defender = tmp_path / f"defender_{hidden_code}.ydk"
        defender.write_text("#main\n" + "\n".join(map(str, (
            hidden_code, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
        with GoatEnvironment(str(attacker), str(defender), seed=98,
                             engine=ExperimentalOcgcoreEngine(root)) as env:
            obs = env.reset()
            assert hidden_code in {card.code for card in
                                   env.engine.probe.observation(1).hand}
            summoned = set_defender = attacked = False
            snapshots = None
            agents = (RandomAgent(52), RandomAgent(53))
            for _ in range(5000):
                if env.is_terminal():
                    break
                actions = env.legal_actions()
                action: Action | None = None
                if obs.turn == 1 and obs.acting_player == 0 and not summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == GEMINI_ELF), None)
                    summoned |= action is not None
                if obs.turn == 2 and obs.acting_player == 1 and not set_defender:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == hidden_code), None)
                    set_defender |= action is not None
                if obs.turn == 3 and obs.acting_player == 0 \
                        and set_defender and not attacked:
                    action = next((a for a in actions if a.kind in (
                        "battle_phase", "attack") and (a.kind != "attack"
                        or a.parameters.get("code") == GEMINI_ELF)), None)
                    attacked |= action is not None and action.kind == "attack"
                if attacked and snapshots is None and actions[0].kind == "select_card":
                    target = next((a for a in actions
                                   if a.parameters.get("controller") == 1
                                   and a.parameters.get("location") == 4), None)
                    assert target is not None
                    before = (obs, actions)
                    after = env.step(target)
                    hidden = next(c for c in after.field
                                  if c.controller == 1 and c.zone == "monster")
                    assert hidden.position == "facedown" and hidden.code is None
                    assert len(after.recent_attacks) == 1
                    snapshots = before, after
                    obs = after
                    continue
                if action is None and snapshots is None:
                    action = next((a for a in actions if a.kind in (
                        "place", "select_position", "pass", "main2", "end_phase")),
                        actions[0])
                if action is None:
                    action = agents[obs.acting_player].select_action(obs, actions)
                obs = env.step(action)
            assert env.is_terminal() and summoned and set_defender and attacked
            assert snapshots is not None
            path = tmp_path / f"attack_hidden_{hidden_code}.json"
            write_trajectory(path, env.trajectory())
            loaded = read_trajectory(path)
            assert verify_trajectory(loaded, ExperimentalOcgcoreEngine(root)) == len(
                loaded.decisions)
            assert audit_trajectory_visibility(loaded)["decisions"] == len(
                loaded.decisions)
            return snapshots

    koala, vanilla = run(DES_KOALA), run(VANILLA_DECK[0])
    assert koala == vanilla
