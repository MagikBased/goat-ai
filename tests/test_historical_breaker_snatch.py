"""Breaker removing an active Snatch Steal returns its target."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

BREAKER = 71413901
SNATCH_STEAL = 45986603


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_breaker_destroys_snatch_steal_and_returns_control(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (BREAKER, SNATCH_STEAL):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    owner_deck = tmp_path / "breaker.ydk"
    owner_deck.write_text("#main\n" + "\n".join(map(str, (
        BREAKER, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    thief_deck = tmp_path / "snatch.ydk"
    thief_deck.write_text("#main\n" + "\n".join(map(str, (
        SNATCH_STEAL, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(owner_deck), str(thief_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert BREAKER in {c.code for c in obs.hand}
        assert SNATCH_STEAL in {c.code for c in env.engine.probe.observation(1).hand}
        summoned = stolen = snatch_targeted = breaker_summoned = False
        breaker_used = breaker_targeted = False
        summoned_code = None
        for _ in range(80):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") != BREAKER), None)
                if action is not None:
                    summoned = True
                    summoned_code = action.parameters["code"]
            if obs.turn == 2 and obs.acting_player == 1 and not stolen:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SNATCH_STEAL), action)
                stolen |= action is not None and action.kind == "activate"
            if stolen and not snatch_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 0
                               and a.parameters.get("code") == summoned_code), None)
                snatch_targeted |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not breaker_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == BREAKER), action)
                if action is not None and action.kind == "normal_summon":
                    assert snatch_targeted
                    assert any(c.controller == 1 and c.code == summoned_code
                               for c in obs.field)
                    breaker_summoned = True
            if breaker_summoned and obs.acting_player == 0 and not breaker_used:
                option = next((a for a in actions if a.kind in ("activate", "chain")
                               and a.parameters.get("code") == BREAKER), None)
                if option is not None:
                    breaker = next(c for c in obs.field if c.code == BREAKER)
                    assert (breaker.attack, breaker.counters) == (1900, ((1, 1),))
                    action = option
                    breaker_used = True
            if breaker_used and not breaker_targeted and actions[0].kind == "select_card":
                breaker = next(c for c in obs.field if c.code == BREAKER)
                assert (breaker.attack, breaker.counters) == (1600, ())
                action = next((a for a in actions if a.parameters.get("code")
                               == SNATCH_STEAL and a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 8), None)
                breaker_targeted |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if breaker_targeted and not obs.chain and SNATCH_STEAL in {
                    c.code for c in obs.graveyards[1]}:
                assert all(c.code != SNATCH_STEAL for c in obs.field)
                restored = next(c for c in obs.field if c.code == summoned_code)
                assert restored.controller == 0 and restored.position == "faceup"
                breaker = next(c for c in obs.field if c.code == BREAKER)
                assert breaker.controller == 0
                assert (breaker.attack, breaker.counters) == (1600, ())
                assert {f"official/c{BREAKER}.lua",
                        f"official/c{SNATCH_STEAL}.lua"}.issubset(
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Breaker did not remove Snatch Steal within 80 decisions")
