"""A stolen BLS can reset its banish effect through Tsukuyomi."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

BLS = 504700118
GRACEFUL = 79571449
SNATCH = 45986603
TSUKUYOMI = 34853266
LIGHT = 15025844
DARK = 7359741


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_snatch_tsukuyomi_resets_stolen_bls_banish(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{BLS}.lua", f"official/c{GRACEFUL}.lua",
               f"official/c{SNATCH}.lua", f"official/c{TSUKUYOMI}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required GOAT card scripts not installed")
    lights = (LIGHT, 62651957)
    darks = (49881766, DARK)
    filler = [code for code in VANILLA_DECK if code not in (*lights, *darks)]
    owner = tmp_path / "bls.ydk"
    owner.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL, BLS, *(code for code in lights for _ in range(3)),
        *(code for code in darks for _ in range(3)), *filler[:26])))
        + "\n#extra\n!side\n")
    stealer = tmp_path / "snatch_tsukuyomi.ydk"
    stealer.write_text("#main\n" + "\n".join(map(str, (
        SNATCH, *(TSUKUYOMI if code == 23771716 else code
                  for code in VANILLA_DECK[1:])))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(owner), str(stealer), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, BLS, LIGHT, DARK} <= {c.code for c in obs.hand}
        assert {SNATCH, TSUKUYOMI} <= {
            c.code for c in env.engine.probe.observation(1).hand}
        graceful = discarded = first_summoned = second_summoned = bls_summoned = False
        snatch_used = snatch_targeted = first_effect = first_target = False
        tsuk_summoned = tsuk_target = set_bls = flipped = False
        second_effect = second_target = False
        first_code = second_code = None
        costs = set()
        for _ in range(175):
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
                if discarded and not first_summoned and action is None:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") in filler), None)
                    if action is not None:
                        first_code = action.parameters["code"]
                        first_summoned = True
            if obs.turn == 3 and obs.acting_player == 0:
                if first_summoned and not second_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") in filler
                                   and a.parameters.get("code") != first_code), None)
                    if action is not None:
                        second_code = action.parameters["code"]
                        second_summoned = True
                if second_summoned and not bls_summoned and action is None:
                    action = next((a for a in actions if a.kind == "special_summon"
                                   and a.parameters.get("code") == BLS), None)
                    bls_summoned |= action is not None
                if bls_summoned and len(costs) < 2 and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   in ({LIGHT, DARK} - costs)), action)
                    if action is not None and action.kind == "select_card":
                        costs.add(action.parameters["code"])
            if obs.turn == 4 and obs.acting_player == 1 and bls_summoned:
                if not snatch_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == SNATCH), None)
                    snatch_used |= action is not None
                if snatch_used and not snatch_targeted \
                        and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == BLS
                                   and a.parameters.get("controller") == 0), None)
                    snatch_targeted |= action is not None
                if snatch_targeted and not obs.chain and not first_effect \
                        and any(c.code == BLS and c.controller == 1 for c in obs.field):
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == BLS), None)
                    first_effect |= action is not None
                if first_effect and not first_target \
                        and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == first_code and a.parameters.get("controller") == 0),
                                  None)
                    first_target |= action is not None
                first_resolved = first_code in {c.code for c in obs.banished[0]}
                if first_resolved and not tsuk_summoned and action is None:
                    assert not any(a.kind == "activate"
                                   and a.parameters.get("code") == BLS for a in actions)
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == TSUKUYOMI), None)
                    tsuk_summoned |= action is not None
                if tsuk_summoned and not tsuk_target \
                        and actions[0].kind == "select_card":
                    assert [link.card_code for link in obs.chain] == [TSUKUYOMI]
                    action = next((a for a in actions if a.parameters.get("code") == BLS
                                   and a.parameters.get("controller") == 1), None)
                    tsuk_target |= action is not None
                if tsuk_target and not obs.chain and not set_bls:
                    hidden_bls = next((c for c in obs.field if c.code == BLS
                                       and c.controller == 1
                                       and c.position == "facedown"), None)
                    if hidden_bls is not None:
                        set_bls = True
                        assert SNATCH in {c.code for c in obs.graveyards[1]}
                        original_owner = env.engine.probe.observation(0)
                        hidden = next(c for c in original_owner.field
                                      if c.zone == "monster" and c.controller == 1
                                      and c.sequence == hidden_bls.sequence)
                        assert hidden.code is None and hidden.position == "facedown"
                        assert (1, "monster", hidden.sequence, BLS) in {
                            (c.controller, c.zone, c.sequence, c.code)
                            for c in original_owner.known_opponent_field_cards}
                if set_bls and not flipped and action is None:
                    action = next((a for a in actions if a.kind == "flip_summon"
                                   and a.parameters.get("code") == BLS), None)
                    flipped |= action is not None
                if flipped and not second_effect and action is None:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == BLS), None)
                    second_effect |= action is not None
                if second_effect and not second_target \
                        and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == second_code and a.parameters.get("controller") == 0),
                                  None)
                    second_target |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if second_target and not obs.chain \
                    and second_code in {c.code for c in obs.banished[0]}:
                assert first_code != second_code
                assert {first_code, second_code} <= {
                    c.code for c in obs.banished[0]}
                assert snatch_used and snatch_targeted and first_effect and first_target
                assert tsuk_summoned and tsuk_target and set_bls and flipped
                assert second_effect and second_target and costs == {LIGHT, DARK}
                assert any(c.code == BLS and c.controller == 1
                           and c.position == "faceup" for c in obs.field)
                assert SNATCH in {c.code for c in obs.graveyards[1]}
                assert obs.life_points == (8000, 8000)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                agents = (RandomAgent(100), RandomAgent(101))
                for _ in range(5000):
                    if env.is_terminal():
                        break
                    obs = env.step(agents[obs.acting_player].select_action(
                        obs, env.legal_actions()))
                else:
                    pytest.fail("Stolen BLS / Tsukuyomi continuation exceeded 5000 decisions")
                path = tmp_path / "bls_snatch_tsukuyomi.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                                             env.trajectory().decisions)
                return
    pytest.fail(f"Stolen BLS reset stalled: turn={obs.turn} phase={obs.phase} "
                f"normal={first_summoned}/{second_summoned} BLS={bls_summoned} "
                f"Snatch={snatch_used}/{snatch_targeted} "
                f"first={first_effect}/{first_target} "
                f"Tsuk={tsuk_summoned}/{tsuk_target} Set={set_bls} Flip={flipped} "
                f"second={second_effect}/{second_target}")
