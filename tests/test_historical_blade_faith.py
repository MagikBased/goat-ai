"""Blade Knight's lone-monster condition decides Faith's Spell recovery."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

BLADE_KNIGHT = 39507162
MAGICIAN_OF_FAITH = 31560081
POT_OF_GREED = 55144522


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("friendly_ally", [False, True])
def test_blade_knight_condition_controls_faith_recovery(tmp_path, friendly_ally):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (BLADE_KNIGHT, MAGICIAN_OF_FAITH, POT_OF_GREED):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    attacker = tmp_path / "blade.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        *([BLADE_KNIGHT] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    defender = tmp_path / "faith.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        POT_OF_GREED, *([MAGICIAN_OF_FAITH] * 3), *VANILLA_DECK[4:])))
                        + "\n#extra\n!side\n")
    with GoatEnvironment(str(attacker), str(defender), seed=72,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert BLADE_KNIGHT in {c.code for c in obs.hand}
        assert {MAGICIAN_OF_FAITH, POT_OF_GREED}.issubset(
            c.code for c in env.engine.probe.observation(1).hand)
        blade_summoned = pot_used = faith_set = ally_summoned = False
        battle = attacked = attack_targeted = pot_targeted = False
        for _ in range(80):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not blade_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == BLADE_KNIGHT), None)
                blade_summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not pot_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == POT_OF_GREED), None)
                    pot_used |= action is not None
                elif not faith_set:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == MAGICIAN_OF_FAITH), None)
                    faith_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and faith_set:
                if friendly_ally and not ally_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") != BLADE_KNIGHT), None)
                    ally_summoned |= action is not None
                if obs.phase == "main1" and not battle and action is None:
                    action = next((a for a in actions if a.kind == "battle_phase"), None)
                    battle |= action is not None
                elif obs.phase == "battle_start" and not attacked:
                    assert sum(c.controller == 0 and c.zone == "monster"
                               for c in obs.field) == (2 if friendly_ally else 1)
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == BLADE_KNIGHT), None)
                    attacked |= action is not None
            if attacked and not attack_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 4
                               and "code" not in a.parameters), None)
                attack_targeted |= action is not None
            if attack_targeted and not pot_targeted and obs.acting_player == 1 \
                    and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == POT_OF_GREED and a.parameters.get("location") == 16),
                              None)
                pot_targeted |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if attack_targeted and obs.phase == "battle_step" \
                    and obs.acting_player == 0 and MAGICIAN_OF_FAITH in {
                        c.code for c in obs.graveyards[1]}:
                faith_owner = env.engine.probe.observation(1)
                assert pot_targeted
                assert (POT_OF_GREED in {c.code for c in faith_owner.hand}) \
                    == friendly_ally
                assert (POT_OF_GREED in {c.code for c in obs.graveyards[1]}) \
                    != friendly_ally
                assert obs.life_points == (8000, 8000)
                assert [[c.code for c in reveal.cards] for reveal in
                        env.engine.probe.observation(0).private_reveals] == (
                            [[POT_OF_GREED]] if friendly_ally else [])
                loaded = env.engine.probe.loaded_script_sha256
                assert {f"official/c{BLADE_KNIGHT}.lua",
                        f"official/c{MAGICIAN_OF_FAITH}.lua"}.issubset(loaded)
                return
    pytest.fail(f"Blade Knight / Faith did not resolve (ally={friendly_ally})")
