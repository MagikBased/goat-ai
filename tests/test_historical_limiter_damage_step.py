"""Limiter Removal can change a Machine's ATK during the Damage Step."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import verify_trajectory

LIMITER = 504700037
DEKOICHI = 87621407
GEMINI_ELF = 69140098
LIMITER_SCRIPT = f"goat/c{LIMITER}.lua"
LIMITER_SHA256 = "68a9919c8deabee329804c46081958e9c144c8161dadbaf39cd4ed975e733c88"


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("use_limiter", [False, True])
def test_limiter_during_damage_step_changes_battle_result(tmp_path, use_limiter):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / "scripts" / LIMITER_SCRIPT).is_file():
        pytest.skip("GOAT Limiter Removal script not installed")
    decks = []
    for name, opening in (("machine", (DEKOICHI, LIMITER)),
                          ("attacker", (GEMINI_ELF,))):
        cards = list(VANILLA_DECK)
        if name == "machine":
            cards[:2] = opening
        else:
            cards = [GEMINI_ELF] * 3 + [code for code in cards
                                       if code != GEMINI_ELF]
        path = tmp_path / f"{name}.ydk"
        path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
        decks.append(str(path))

    with GoatEnvironment(*decks, seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        summoned_machine = set_limiter = summoned_attacker = attacked = False
        selected_target = damage_step_seen = limiter_activated = checked = False
        for _ in range(5000):
            if env.is_terminal():
                break
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not summoned_machine:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == DEKOICHI), None)
                    summoned_machine |= action is not None
                if action is None and summoned_machine and not set_limiter:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == LIMITER), None)
                    set_limiter |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not summoned_attacker:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == GEMINI_ELF), None)
                    summoned_attacker |= action is not None
                if action is None and summoned_attacker and not attacked:
                    action = next((a for a in actions if a.kind in ("battle_phase", "attack")
                                   and (a.kind != "attack" or
                                        a.parameters.get("code") == GEMINI_ELF)), None)
                    attacked |= action is not None and action.kind == "attack"
            if attacked and not selected_target and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 0
                               and a.parameters.get("location") == 4), None)
                selected_target |= action is not None
            if selected_target and obs.phase == "damage_step":
                damage_step_seen = True
                candidate = next((a for a in actions if a.kind == "chain"
                                  and a.parameters.get("code") == LIMITER), None)
                if candidate is not None and not limiter_activated:
                    action = candidate if use_limiter else next(
                        a for a in actions if a.kind == "pass")
                    limiter_activated = use_limiter
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "main2", "end_phase")),
                    actions[0])
            if action is None:
                action = RandomAgent(100 + obs.acting_player).select_action(obs, actions)
            obs = env.step(action)
            if selected_target and not checked and obs.turn == 2 and obs.phase == "main2":
                assert summoned_machine and set_limiter and summoned_attacker
                assert damage_step_seen
                assert limiter_activated == use_limiter
                if use_limiter:
                    assert obs.life_points == (8000, 7100)
                    assert GEMINI_ELF in {c.code for c in obs.graveyards[1]}
                    assert any(c.code == DEKOICHI for c in obs.field)
                else:
                    assert obs.life_points == (7500, 8000)
                    assert DEKOICHI in {c.code for c in obs.graveyards[0]}
                    assert any(c.code == GEMINI_ELF for c in obs.field)
                checked = True
        assert checked and env.is_terminal(), (
            summoned_machine, set_limiter, summoned_attacker, attacked,
            selected_target, damage_step_seen, limiter_activated,
            obs.turn, obs.phase, obs.life_points)
        assert env.engine.probe.loaded_script_sha256[LIMITER_SCRIPT] == LIMITER_SHA256
        trajectory = env.trajectory()
        assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) == len(
            trajectory.decisions)
        assert audit_trajectory_visibility(trajectory)["decisions"] == len(
            trajectory.decisions)
