"""GOAT Ignition priority after BLS Special Summon versus Torrential."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

BLS = 504700118
GRACEFUL = 79571449
TORRENTIAL = 53582587
LIGHT = 15025844
DARK = 7359741


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("use_priority", [False, True])
def test_bls_priority_before_opposing_torrential(tmp_path, use_priority):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{BLS}.lua", f"official/c{GRACEFUL}.lua",
                     f"official/c{TORRENTIAL}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    lights = (LIGHT, 62651957)
    darks = (49881766, DARK)
    filler = [code for code in VANILLA_DECK if code not in (*lights, *darks)]
    bls_cards = (GRACEFUL, BLS, *(code for code in lights for _ in range(3)),
                 *(code for code in darks for _ in range(3)), *filler[:26])
    bls_deck = tmp_path / "bls.ydk"
    bls_deck.write_text("#main\n" + "\n".join(map(str, bls_cards))
                        + "\n#extra\n!side\n")
    trap_deck = tmp_path / "torrential.ydk"
    trap_deck.write_text("#main\n" + "\n".join(map(str, (
        TORRENTIAL, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(bls_deck), str(trap_deck), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {BLS, GRACEFUL, LIGHT, DARK}.issubset(c.code for c in obs.hand)
        assert TORRENTIAL in {c.code for c in env.engine.probe.observation(1).hand}
        graceful = discarded = trap_set = defender_summoned = summoned = False
        priority_seen = effect_used = target_selected = torrential_used = False
        costs = []
        defender_code = None
        for _ in range(95):
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
            if obs.turn == 2 and obs.acting_player == 1:
                if not trap_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == TORRENTIAL), None)
                    trap_set |= action is not None
                if trap_set and not defender_summoned and action is None:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        defender_code = action.parameters["code"]
                        defender_summoned = True
            if obs.turn == 3 and obs.acting_player == 0 and defender_summoned:
                if not summoned:
                    action = next((a for a in actions if a.kind == "special_summon"
                                   and a.parameters.get("code") == BLS), None)
                    summoned |= action is not None
                if summoned and len(costs) < 2 and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   in ({LIGHT, DARK} - set(costs))), action)
                    if action is not None and action.kind == "select_card":
                        costs.append(action.parameters["code"])
                if summoned and len(costs) == 2 and not priority_seen:
                    option = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == BLS), None)
                    if option is not None:
                        assert obs.chain == ()
                        assert {c.code for c in obs.banished[0]} == {LIGHT, DARK}
                        assert any(c.controller == 1 and c.zone == "spell_trap"
                                   and c.position == "facedown" and c.code is None
                                   for c in obs.field)
                        priority_seen = True
                        action = option if use_priority else next(
                            a for a in actions if a.kind == "pass")
                        effect_used = use_priority
                if effect_used and not target_selected and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == defender_code and a.parameters.get("controller") == 1),
                                  None)
                    target_selected |= action is not None
            if priority_seen and obs.acting_player == 1 and not torrential_used:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == TORRENTIAL), None)
                if action is not None:
                    assert (len(obs.chain) == 1) == use_priority
                    if use_priority:
                        assert obs.chain[0].card_code == BLS
                    torrential_used = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if torrential_used and TORRENTIAL in {c.code for c in obs.graveyards[1]}:
                assert priority_seen and set(costs) == {LIGHT, DARK}
                assert obs.chain == ()
                assert not any(c.zone == "monster" for c in obs.field)
                assert {BLS, defender_code}.issubset(
                    {c.code for pile in obs.graveyards for c in pile})
                assert defender_code not in {c.code for c in obs.banished[1]}
                assert obs.life_points == (8000, 8000)
                assert target_selected == use_priority
                assert {f"goat/c{BLS}.lua", f"official/c{TORRENTIAL}.lua"}.issubset(
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("BLS priority / Torrential chain did not resolve")
