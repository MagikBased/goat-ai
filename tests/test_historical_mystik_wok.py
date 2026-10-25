"""Mystik Wok pays its Tribute cost and uses Breaker's current ATK or DEF."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

MYSTIK_WOK = 80161395
BREAKER = 71413901


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("mode", ["before_counter", "current_atk", "current_def"])
def test_mystik_wok_uses_tributed_breakers_current_stats(tmp_path, mode):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (MYSTIK_WOK, BREAKER)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("Mystik Wok / Breaker scripts not installed")
    own = tmp_path / "wok_breaker.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        BREAKER, MYSTIK_WOK, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), "examples/decks/vanilla_probe.ydk", seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {BREAKER, MYSTIK_WOK} <= {c.code for c in obs.hand}
        breaker_summoned = wok_used = tribute_paid = option_chosen = False
        expected_gain = {"before_counter": 1600, "current_atk": 1900,
                         "current_def": 1000}[mode]
        for _ in range(60):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not breaker_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == BREAKER), None)
                breaker_summoned |= action is not None
            breaker = next((c for c in obs.field if c.code == BREAKER), None)
            if breaker_summoned and not wok_used and obs.turn == 1 \
                    and obs.acting_player == 0 and breaker is not None:
                timing_matches = ((breaker.attack == 1600 and not breaker.counters)
                                  if mode == "before_counter" else
                                  (breaker.attack == 1900 and breaker.counters == ((1, 1),)))
                if timing_matches:
                    action = next((a for a in actions if a.kind in ("activate", "chain")
                                   and a.parameters.get("code") == MYSTIK_WOK), action)
                    if action is not None and action.parameters.get("code") == MYSTIK_WOK:
                        if mode == "before_counter":
                            assert [link.card_code for link in obs.chain] == [BREAKER]
                        wok_used = True
            if wok_used and not tribute_paid and actions[0].kind == "select_card":
                assert len(actions) == 1
                assert actions[0].parameters.get("code") == BREAKER
                assert breaker is not None
                assert (breaker.attack, breaker.defense) == (
                    (1600 if mode == "before_counter" else 1900), 1000)
                action = actions[0]
                tribute_paid = True
            if tribute_paid and not option_chosen \
                    and actions[0].kind == "select_option":
                assert len(actions) == 2
                assert BREAKER in {c.code for c in obs.graveyards[0]}
                action = actions[1 if mode == "current_def" else 0]
                option_chosen = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if option_chosen and obs.turn == 1 and obs.acting_player == 0 \
                    and obs.chain == () and obs.life_points[0] > 8000:
                assert obs.life_points == (8000 + expected_gain, 8000)
                assert {BREAKER, MYSTIK_WOK} <= {
                    c.code for c in obs.graveyards[0]}
                assert not any(c.code == BREAKER for c in obs.field)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                agents = (RandomAgent(18), RandomAgent(19))
                for _ in range(5000):
                    obs = env.step(agents[obs.acting_player].select_action(
                        obs, env.legal_actions()))
                    if env.is_terminal():
                        path = tmp_path / f"wok_{mode}.json"
                        write_trajectory(path, env.trajectory())
                        assert verify_trajectory(read_trajectory(path),
                                                 ExperimentalOcgcoreEngine(root)) == len(
                                                     env.trajectory().decisions)
                        return
                pytest.fail("Mystik Wok duel did not finish")
    pytest.fail(f"Mystik Wok did not resolve: {mode}")
