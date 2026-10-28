"""Skill Drain negates BLS's banish effect but not its attack restriction."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

BLS = 504700118
GRACEFUL = 79571449
SKILL_DRAIN = 82732705
LIGHT = 15025844
DARK = 7359741


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("drain_timing", ["passed", "chained", "already_active"])
def test_skill_drain_negates_bls_banish_but_keeps_attack_restriction(tmp_path, drain_timing):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{BLS}.lua", f"official/c{GRACEFUL}.lua",
               f"official/c{SKILL_DRAIN}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    lights = (LIGHT, 62651957)
    darks = (49881766, DARK)
    filler = [code for code in VANILLA_DECK if code not in (*lights, *darks)]
    bls_deck = tmp_path / "bls.ydk"
    bls_deck.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL, BLS, *(code for code in lights for _ in range(3)),
        *(code for code in darks for _ in range(3)), *filler[:26])))
        + "\n#extra\n!side\n")
    drain_deck = tmp_path / "drain.ydk"
    drain_deck.write_text("#main\n" + "\n".join(map(str, (
        SKILL_DRAIN, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(bls_deck), str(drain_deck), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, BLS} <= {c.code for c in obs.hand}
        assert SKILL_DRAIN in {c.code for c in env.engine.probe.observation(1).hand}
        graceful = discarded = summoned = monster_summoned = drain_set = False
        activated = targeted = response_made = resolved = battle_entered = False
        drain_activated = False
        costs = set()
        monster_code = None
        for _ in range(120):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    graceful |= action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"] for c in
                                   a.parameters["cards"]} == {LIGHT, DARK}), None)
                    discarded |= action is not None
                if discarded and not summoned and action is None:
                    action = next((a for a in actions if a.kind == "special_summon"
                                   and a.parameters.get("code") == BLS), None)
                    summoned |= action is not None
            if summoned and len(costs) < 2 and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               in ({LIGHT, DARK} - costs)), action)
                if action is not None and action.kind == "select_card":
                    costs.add(action.parameters["code"])
            if obs.turn == 2 and obs.acting_player == 1:
                if not monster_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        monster_code = action.parameters["code"]
                        monster_summoned = True
                if monster_summoned and not drain_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == SKILL_DRAIN), None)
                    drain_set |= action is not None
            if drain_timing == "already_active" and obs.turn == 3 \
                    and obs.acting_player == 1 and drain_set and not drain_activated:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SKILL_DRAIN), action)
                drain_activated |= action is not None and action.kind == "chain" \
                    and action.parameters.get("code") == SKILL_DRAIN
                response_made |= drain_activated
            if obs.turn == 3 and obs.acting_player == 0 and drain_set:
                if not activated and (drain_timing != "already_active" or drain_activated):
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == BLS), None)
                    if drain_timing == "already_active" and action is not None:
                        assert any(c.code == SKILL_DRAIN and c.position == "faceup"
                                   for c in obs.field)
                    activated |= action is not None
                if activated and not targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == monster_code and a.parameters.get("controller") == 1), None)
                    targeted = action is not None
            if targeted and obs.acting_player == 1 and not response_made:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SKILL_DRAIN), None)
                if option is not None:
                    assert [link.card_code for link in obs.chain] == [BLS]
                    action = option if drain_timing == "chained" else next(
                        a for a in actions if a.kind == "pass")
                    response_made = True
            if targeted and response_made and not resolved \
                    and not obs.chain and obs.turn == 3:
                resolved = True
                assert {LIGHT, DARK} <= {c.code for c in obs.banished[0]}
                assert any(c.code == BLS and c.position == "faceup" for c in obs.field)
                assert (monster_code in {c.code for c in obs.banished[1]}) \
                    == (drain_timing == "passed")
                assert (monster_code in {c.code for c in obs.field}) \
                    == (drain_timing != "passed")
                assert (SKILL_DRAIN in {c.code for c in obs.field}) \
                    == (drain_timing != "passed")
                assert obs.life_points == ((8000, 8000) if drain_timing == "passed"
                                           else (8000, 7000))
                assert not any(a.kind == "activate" and a.parameters.get("code") == BLS
                               for a in actions)
            if resolved and obs.turn == 3 and obs.acting_player == 0 \
                    and obs.phase == "main1":
                action = next((a for a in actions if a.kind == "battle_phase"), action)
                battle_entered |= action is not None and action.kind == "battle_phase"
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "select_position", "pass", "end_phase")),
                              actions[0])
            obs = env.step(action)
            if battle_entered and obs.turn == 3 and obs.phase == "battle_start":
                assert not any(a.kind == "attack" and a.parameters.get("code") == BLS
                               for a in env.legal_actions())
                loaded = env.engine.probe.loaded_script_sha256
                if drain_timing != "passed":
                    assert scripts <= loaded.keys()
                else:
                    assert {f"goat/c{BLS}.lua", f"official/c{GRACEFUL}.lua"} <= loaded.keys()
                return
    pytest.fail("BLS / Skill Drain chain did not reach Battle Phase")
