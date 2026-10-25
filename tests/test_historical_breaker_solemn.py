"""Solemn negates Breaker's Summon before its counter-placement trigger."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

BREAKER = 71413901
SOLEMN = 41420027


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("solemn_response", [False, True])
def test_solemn_before_breaker_counter_trigger(tmp_path, solemn_response):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (BREAKER, SOLEMN)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    breaker_deck = tmp_path / "breaker.ydk"
    breaker_deck.write_text("#main\n" + "\n".join(map(str, (
        BREAKER, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    solemn_deck = tmp_path / "solemn.ydk"
    solemn_deck.write_text("#main\n" + "\n".join(map(str, (
        *([SOLEMN] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(breaker_deck), str(solemn_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert BREAKER in {c.code for c in obs.hand}
        assert SOLEMN in {c.code for c in env.engine.probe.observation(1).hand}
        trap_set = attempted = responded = counter_window = checked = False
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"breaker_solemn_{solemn_response}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1 and not trap_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SOLEMN), None)
                trap_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not attempted:
                assert trap_set
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == BREAKER), None)
                attempted |= action is not None
            if attempted and obs.acting_player == 1 and not responded:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SOLEMN), None)
                if option is not None:
                    assert not obs.chain
                    assert not any(c.code == BREAKER and c.counters for c in obs.field)
                    action = option if solemn_response else next(
                        a for a in actions if a.kind == "pass")
                    responded = True
            if responded and not solemn_response and obs.acting_player == 1 \
                    and [link.card_code for link in obs.chain] == [BREAKER]:
                assert not any(a.kind == "chain" and a.parameters.get("code") == SOLEMN
                               for a in actions)
                breaker = next(c for c in obs.field if c.code == BREAKER)
                assert breaker.attack == 1600 and breaker.counters == ()
                counter_window = True
            if responded and solemn_response and not checked:
                assert not any(link.card_code == BREAKER for link in obs.chain)
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if responded and not checked and obs.turn == 3 and obs.acting_player == 0 \
                    and obs.phase == "main1" and not obs.chain:
                if solemn_response and SOLEMN in {c.code for c in obs.graveyards[1]}:
                    assert BREAKER in {c.code for c in obs.graveyards[0]}
                    assert not any(c.code == BREAKER for c in obs.field)
                    assert not any(a.kind == "normal_summon" for a in env.legal_actions())
                    assert obs.life_points == (8000, 4000)
                    assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                    checked = True
                if not solemn_response and counter_window and any(
                        c.code == BREAKER and c.counters == ((1, 1),)
                        for c in obs.field):
                    assert SOLEMN not in {c.code for c in obs.graveyards[1]}
                    assert obs.life_points == (8000, 8000)
                    assert f"official/c{BREAKER}.lua" in (
                        env.engine.probe.loaded_script_sha256)
                    checked = True
    pytest.fail("Breaker / Solemn duel did not finish")
