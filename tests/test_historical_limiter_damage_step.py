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
SOLEMN = 41420027
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


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_negated_limiter_gets_no_second_damage_calculation_chain(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / "scripts" / LIMITER_SCRIPT).is_file():
        pytest.skip("GOAT Limiter Removal script not installed")
    machine = list(VANILLA_DECK)
    machine[:3] = DEKOICHI, LIMITER, LIMITER
    defender = ([GEMINI_ELF] * 3 + [SOLEMN] * 3
                + [code for code in VANILLA_DECK if code != GEMINI_ELF][:34])
    paths = []
    for name, cards in (("machine", machine), ("defender", defender)):
        path = tmp_path / f"{name}.ydk"
        path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
        paths.append(str(path))

    with GoatEnvironment(*paths, seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {DEKOICHI, LIMITER} <= {card.code for card in obs.hand}
        assert sum(card.code == LIMITER for card in obs.hand) == 2
        assert {GEMINI_ELF, SOLEMN} <= {
            card.code for card in env.engine.probe.observation(1).hand}
        summoned_machine = summoned_defender = solemn_set = attacked = False
        limiter_set = 0
        target_selected = first_limiter = solemn_used = False
        battle_resolved = checked = False
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
                if action is None and summoned_machine and limiter_set < 2:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == LIMITER), None)
                    limiter_set += action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not summoned_defender:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == GEMINI_ELF), None)
                    summoned_defender |= action is not None
                if action is None and summoned_defender and not solemn_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == SOLEMN), None)
                    solemn_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and solemn_set and not attacked:
                assert limiter_set == 2
                action = next((a for a in actions if a.kind in ("battle_phase", "attack")
                               and (a.kind != "attack" or
                                    a.parameters.get("code") == DEKOICHI)), None)
                attacked |= action is not None and action.kind == "attack"
            if attacked and not target_selected and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 4), None)
                target_selected |= action is not None
            if target_selected and obs.phase == "damage_step":
                offered = [a for a in actions if a.kind == "chain"
                           and a.parameters.get("code") == LIMITER]
                if first_limiter and solemn_used and not battle_resolved:
                    assert not offered, "second Limiter offered after Solemn in one substep"
                if offered and not first_limiter:
                    action = offered[0]
                    first_limiter = True
                if first_limiter and not solemn_used and obs.acting_player == 1:
                    solemn = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == SOLEMN), None)
                    if solemn is not None:
                        action = solemn
                        solemn_used = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "main2", "end_phase")),
                    actions[0])
            if action is None:
                action = RandomAgent(100 + obs.acting_player).select_action(obs, actions)
            obs = env.step(action)
            if target_selected and not battle_resolved and obs.turn == 3 \
                    and obs.phase == "main2":
                battle_resolved = True
                assert first_limiter and solemn_used
                assert obs.life_points == (7500, 4000)
                assert DEKOICHI in {card.code for card in obs.graveyards[0]}
                assert any(card.code == GEMINI_ELF for card in obs.field)
                assert any(card.code == LIMITER and card.zone == "spell_trap"
                           for card in env.engine.probe.observation(0).field)
                checked = True
        assert checked and env.is_terminal(), (
            summoned_machine, limiter_set, summoned_defender, solemn_set,
            attacked, target_selected, first_limiter, solemn_used, obs.turn)
        trajectory = env.trajectory()
        assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) == len(
            trajectory.decisions)
        assert audit_trajectory_visibility(trajectory)["decisions"] == len(
            trajectory.decisions)
