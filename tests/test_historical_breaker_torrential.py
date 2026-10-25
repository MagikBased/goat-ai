"""Torrential answers Breaker's summon-trigger counter placement."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

BREAKER = 71413901
TORRENTIAL = 53582587


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_torrential_chained_to_breaker_counter_clears_both_fields(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (BREAKER, TORRENTIAL):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    own = tmp_path / "breaker.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        BREAKER, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    other = tmp_path / "torrential.ydk"
    other.write_text("#main\n" + "\n".join(map(str, (
        TORRENTIAL, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(other), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert BREAKER in {c.code for c in obs.hand}
        assert TORRENTIAL in {c.code for c in env.engine.probe.observation(1).hand}
        first_summoned = trap_set = other_summoned = breaker_summoned = chained = False
        own_code = other_code = None
        for _ in range(90):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not first_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") != BREAKER), None)
                if action is not None:
                    own_code = action.parameters["code"]
                    first_summoned = True
            if obs.turn == 2 and obs.acting_player == 1:
                if not trap_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == TORRENTIAL), None)
                    trap_set |= action is not None
                if trap_set and not other_summoned and action is None:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        other_code = action.parameters["code"]
                        other_summoned = True
            if obs.turn == 3 and obs.acting_player == 0 and not breaker_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == BREAKER), action)
                breaker_summoned |= action is not None and action.kind == "normal_summon"
            if breaker_summoned and obs.acting_player == 1 and not chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == TORRENTIAL), None)
                if action is not None:
                    assert [link.card_code for link in obs.chain] == [BREAKER]
                    breaker = next(c for c in obs.field if c.code == BREAKER)
                    assert (breaker.attack, breaker.counters) == (1600, ())
                    chained = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if chained and TORRENTIAL in {c.code for c in obs.graveyards[1]}:
                assert first_summoned and trap_set and other_summoned and breaker_summoned
                assert obs.chain == ()
                assert not any(c.zone == "monster" for c in obs.field)
                assert {own_code, BREAKER} <= {c.code for c in obs.graveyards[0]}
                assert other_code in {c.code for c in obs.graveyards[1]}
                assert obs.life_points == (8000, 8000)
                assert not any(a.parameters.get("code") == BREAKER
                               and a.kind in ("activate", "chain")
                               for a in env.legal_actions())
                assert {f"official/c{BREAKER}.lua", f"official/c{TORRENTIAL}.lua"} \
                    <= env.engine.probe.loaded_script_sha256.keys()
                return
    pytest.fail("Torrential did not resolve before Breaker's counter placement")
