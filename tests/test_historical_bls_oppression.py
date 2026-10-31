"""Royal Oppression can negate an inherent BLS Summon after its banish cost.

Archived FAQ: https://www.goatformat.com/rulings6.html (Royal Oppression).
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

BLS = 504700118
GRACEFUL = 79571449
OPPRESSION = 93016201
LIGHT = 15025844
DARK = 7359741


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
@pytest.mark.parametrize("negate_summon", [False, True])
def test_faceup_oppression_answers_bls_inherent_summon(tmp_path, negate_summon):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{BLS}.lua", f"official/c{GRACEFUL}.lua",
               f"official/c{OPPRESSION}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    lights = (LIGHT, 62651957)
    darks = (49881766, DARK)
    filler = [code for code in VANILLA_DECK if code not in (*lights, *darks)]
    bls_cards = [GRACEFUL, BLS,
                 *(code for code in lights for _ in range(3)),
                 *(code for code in darks for _ in range(3)), *filler[:26]]
    caller = tmp_path / "bls.ydk"
    responder = tmp_path / "oppression.ydk"
    caller.write_text("#main\n" + "\n".join(map(str, bls_cards)) + "\n#extra\n!side\n")
    responder.write_text("#main\n" + "\n".join(map(str, (
        OPPRESSION, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(caller), str(responder), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {BLS, GRACEFUL, LIGHT, DARK} <= {c.code for c in obs.hand}
        graceful = discarded = oppression_set = oppression_up = False
        summon_started = responded = checked = False
        costs = []
        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"bls_oppression_{negate_summon}.json"
                write_trajectory(path, env.trajectory())
                replay = read_trajectory(path)
                assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(
                    replay.decisions)
                audit_trajectory_visibility(replay)
                assert scripts <= set(env.engine.probe.loaded_script_sha256)
                return
            actions = env.legal_actions()
            action = None

            def choose(kind, code=None):
                return next((a for a in actions if a.kind == kind and
                             (code is None or a.parameters.get("code") == code)), None)

            if not checked and obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = choose("activate", GRACEFUL)
                    graceful |= action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if
                                   {c["code"] for c in a.parameters["cards"]} ==
                                   {LIGHT, DARK}), None)
                    discarded |= action is not None
            if not checked and obs.turn == 2 and obs.acting_player == 1 \
                    and not oppression_set:
                action = choose("set_spell_trap", OPPRESSION)
                oppression_set |= action is not None
            if not checked and obs.turn == 3 and obs.acting_player == 1 \
                    and oppression_set and not oppression_up:
                action = choose("chain", OPPRESSION)
                oppression_up |= action is not None
            if not checked and obs.turn == 3 and obs.acting_player == 0 \
                    and oppression_up and discarded and not summon_started \
                    and not obs.chain:
                action = choose("special_summon", BLS)
                summon_started |= action is not None
            if summon_started and len(costs) < 2 and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") in
                               ({LIGHT, DARK} - set(costs)) and
                               a.parameters.get("location") == 16), None)
                assert action is not None
                costs.append(action.parameters["code"])
            if summon_started and len(costs) == 2 and not responded \
                    and obs.acting_player == 1:
                oppression_action = choose("chain", OPPRESSION)
                if oppression_action is not None:
                    assert {c.code for c in obs.banished[0]} == {LIGHT, DARK}
                    if negate_summon:
                        action = oppression_action
                    responded = True
            if action is None:
                action = (agents[obs.acting_player].select_action(obs, actions)
                          if checked else next((a for a in actions if a.kind in
                                                ("place", "pass", "end_phase")),
                                               actions[0]))
            obs = env.step(action)
            if responded and not checked and obs.acting_player == 0 \
                    and obs.phase == "main1" and not obs.chain:
                assert set(costs) == {LIGHT, DARK}
                assert {c.code for c in obs.banished[0]} == {LIGHT, DARK}
                assert obs.life_points[1] == (7200 if negate_summon else 8000)
                assert any(c.code == BLS for c in obs.field) == (not negate_summon)
                if negate_summon:
                    assert BLS in {c.code for c in obs.graveyards[0]}
                    assert not any(a.kind == "special_summon" and
                                   a.parameters.get("code") == BLS
                                   for a in env.legal_actions())
                checked = True
    pytest.fail("BLS/Oppression fixture did not reach a verified terminal duel")
