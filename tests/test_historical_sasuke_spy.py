"""Sasuke's Damage Step effect requires a face-up Defense Position target."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

SASUKE = 4041838
ENEMY_CONTROLLER = 98045062
SPY = 504700044


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("faceup_defender", [False, True])
def test_sasuke_attack_on_spy_depends_on_faceup_defense(tmp_path, faceup_defender):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"official/c{SASUKE}.lua", f"goat/c{SPY}.lua",
                     f"official/c{ENEMY_CONTROLLER}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    attacker = tmp_path / "sasuke.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        *([SASUKE] * 3), *([ENEMY_CONTROLLER] * 3),
        *VANILLA_DECK[6:]))) + "\n#extra\n!side\n")
    defender = tmp_path / "spy.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        *([SPY] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(attacker), str(defender), seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {SASUKE, ENEMY_CONTROLLER}.issubset(c.code for c in obs.hand)
        assert SPY in {c.code for c in env.engine.probe.observation(1).hand}
        sasuke_summoned = spy_played = controller_used = mode_chosen = False
        spy_targeted = battle = attacked = attack_targeted = False
        saw_damage_step = False
        for _ in range(85):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not sasuke_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == SASUKE), None)
                sasuke_summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not spy_played:
                kind = "normal_summon" if faceup_defender else "set_monster"
                action = next((a for a in actions if a.kind == kind
                               and a.parameters.get("code") == SPY), None)
                spy_played |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and spy_played:
                if faceup_defender and not controller_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == ENEMY_CONTROLLER), None)
                    controller_used |= action is not None
                if controller_used and not mode_chosen \
                        and actions[0].kind == "select_option":
                    assert len(actions) == 2
                    action = actions[0]
                    mode_chosen = True
                if mode_chosen and not spy_targeted \
                        and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == SPY
                                   and a.parameters.get("controller") == 1), None)
                    spy_targeted |= action is not None
                if obs.phase == "main1" and not battle and action is None \
                        and (not faceup_defender or ENEMY_CONTROLLER in {
                            c.code for c in obs.graveyards[0]}):
                    action = next((a for a in actions if a.kind == "battle_phase"), None)
                    battle |= action is not None
                elif obs.phase == "battle_start" and not attacked:
                    spy_view = next(c for c in obs.field if c.controller == 1
                                    and c.zone == "monster")
                    assert spy_view.orientation == "defense"
                    assert spy_view.code == (SPY if faceup_defender else None)
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == SASUKE), None)
                    attacked |= action is not None
            if attacked and not attack_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 4), None)
                attack_targeted |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if attack_targeted and obs.phase == "damage_step":
                saw_damage_step = True
            if saw_damage_step and obs.phase == "battle_step" \
                    and obs.acting_player == 0:
                if faceup_defender:
                    assert SPY in {c.code for c in obs.graveyards[1]}
                    assert not any(c.code == SPY for c in obs.field)
                    assert obs.life_points == (8000, 8000)
                    assert f"official/c{ENEMY_CONTROLLER}.lua" in (
                        env.engine.probe.loaded_script_sha256)
                else:
                    assert SPY not in {c.code for c in obs.graveyards[1]}
                    assert any(c.code == SPY and c.controller == 1 for c in obs.field)
                    assert obs.life_points == (7800, 8000)
                assert f"official/c{SASUKE}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail(f"Sasuke/Spy attack did not finish (faceup={faceup_defender})")
