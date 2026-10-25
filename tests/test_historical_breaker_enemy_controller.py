"""Enemy Controller takes Breaker before its summon-trigger counter resolves."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

BREAKER = 71413901
ENEMY_CONTROLLER = 98045062


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_enemy_controller_steals_breaker_before_counter_placement(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (BREAKER, ENEMY_CONTROLLER):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    own = tmp_path / "breaker.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        BREAKER, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    other = tmp_path / "controller.ydk"
    other.write_text("#main\n" + "\n".join(map(str, (
        *([ENEMY_CONTROLLER] * 3), *VANILLA_DECK[3:])))
        + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(other), seed=316,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert BREAKER in {c.code for c in obs.hand}
        assert ENEMY_CONTROLLER in {c.code for c in env.engine.probe.observation(1).hand}
        defender_summoned = controller_set = breaker_summoned = chained = False
        control_mode = tribute_paid = target_chosen = control_checked = False
        tribute_code = None
        for _ in range(95):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1:
                if not defender_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        tribute_code = action.parameters["code"]
                        defender_summoned = True
                if defender_summoned and not controller_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == ENEMY_CONTROLLER), None)
                    controller_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not breaker_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == BREAKER), action)
                breaker_summoned |= action is not None and action.kind == "normal_summon"
            if breaker_summoned and obs.acting_player == 1 and not chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == ENEMY_CONTROLLER), action)
                if action is not None and action.kind == "chain":
                    assert [link.card_code for link in obs.chain] == [BREAKER]
                    breaker = next(c for c in obs.field if c.code == BREAKER)
                    assert (breaker.controller, breaker.attack, breaker.counters) \
                        == (0, 1600, ())
                    chained = True
            if chained and not control_mode and actions[0].kind == "select_option":
                assert len(actions) == 2
                action = actions[1]
                control_mode = True
            if control_mode and not tribute_paid and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("code") == tribute_code), None)
                tribute_paid |= action is not None
            if tribute_paid and not target_chosen and action is None \
                    and actions[0].kind == "select_card":
                assert tribute_code in {c.code for c in obs.graveyards[1]}
                action = next((a for a in actions if a.parameters.get("controller") == 0
                               and a.parameters.get("code") == BREAKER), None)
                target_chosen |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_card", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if target_chosen and not control_checked and not obs.chain \
                    and ENEMY_CONTROLLER in {c.code for c in obs.graveyards[1]}:
                assert defender_summoned and controller_set and breaker_summoned
                assert chained and control_mode and tribute_paid
                breaker = next(c for c in obs.field if c.code == BREAKER)
                assert (breaker.controller, breaker.attack, breaker.counters) \
                    == (1, 1900, ((1, 1),))
                assert tribute_code in {c.code for c in obs.graveyards[1]}
                assert obs.life_points == (8000, 8000)
                assert not any(a.parameters.get("code") == BREAKER
                               and a.kind in ("activate", "chain")
                               for a in env.legal_actions())
                assert {f"official/c{BREAKER}.lua",
                        f"official/c{ENEMY_CONTROLLER}.lua"}.issubset(
                    env.engine.probe.loaded_script_sha256)
                control_checked = True
            if control_checked and obs.turn == 4 and obs.phase == "main1":
                breaker = next(c for c in obs.field if c.code == BREAKER)
                assert (breaker.controller, breaker.attack, breaker.counters) \
                    == (0, 1900, ((1, 1),))
                assert obs.life_points == (8000, 8000)
                return
    pytest.fail("Enemy Controller / Breaker line did not reach the next turn")
