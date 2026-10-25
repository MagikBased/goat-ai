"""Skill Drain negates Breaker's counter trigger or later removal effect."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

BREAKER = 71413901
SKILL_DRAIN = 82732705


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("timing", ["counter_placement", "removal_after_cost"])
def test_skill_drain_breaker_counter_timing(tmp_path, timing):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (BREAKER, SKILL_DRAIN):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    own = tmp_path / "breaker.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        BREAKER, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    other = tmp_path / "skill_drain.ydk"
    other.write_text("#main\n" + "\n".join(map(str, (
        SKILL_DRAIN, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(other), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert BREAKER in {c.code for c in obs.hand}
        assert SKILL_DRAIN in {c.code for c in env.engine.probe.observation(1).hand}
        drain_set = breaker_summoned = counter_placed = breaker_used = False
        target_chosen = drain_chained = False
        for _ in range(85):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1 and not drain_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SKILL_DRAIN), None)
                drain_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not breaker_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == BREAKER), None)
                breaker_summoned |= action is not None
            if breaker_summoned and timing == "counter_placement" \
                    and obs.acting_player == 1 and not drain_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SKILL_DRAIN), None)
                if action is not None:
                    assert [link.card_code for link in obs.chain] == [BREAKER]
                    breaker = next(c for c in obs.field if c.code == BREAKER)
                    assert (breaker.attack, breaker.counters) == (1600, ())
                    drain_chained = True
            if timing == "removal_after_cost" and breaker_summoned \
                    and not counter_placed and obs.acting_player == 0 \
                    and any(c.code == BREAKER and c.counters == ((1, 1),)
                            for c in obs.field):
                counter_placed = True
            if counter_placed and not breaker_used and obs.acting_player == 0:
                action = next((a for a in actions if a.kind in ("activate", "chain")
                               and a.parameters.get("code") == BREAKER), action)
                breaker_used |= action is not None and action.parameters.get("code") == BREAKER
            if breaker_used and not target_chosen and actions[0].kind == "select_card":
                breaker = next(c for c in obs.field if c.code == BREAKER)
                assert (breaker.attack, breaker.counters) == (1600, ())
                assert any(c.zone == "spell_trap" and c.controller == 1
                           and c.position == "facedown" and c.code is None
                           for c in obs.field)
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 8
                               and "code" not in a.parameters), None)
                target_chosen |= action is not None
            if timing == "removal_after_cost" and target_chosen \
                    and obs.acting_player == 1 and not drain_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SKILL_DRAIN), None)
                if action is not None:
                    assert [link.card_code for link in obs.chain] == [BREAKER]
                    drain_chained = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if drain_chained and not obs.chain \
                    and any(c.code == SKILL_DRAIN for c in obs.field):
                breaker = next(c for c in obs.field if c.code == BREAKER)
                assert breaker.position == "faceup"
                assert (breaker.attack, breaker.counters) == (1600, ())
                assert obs.life_points == (8000, 7000)
                assert not any(c.code == SKILL_DRAIN for c in obs.graveyards[1])
                assert not any(a.parameters.get("code") == BREAKER
                               and a.kind in ("activate", "chain")
                               for a in env.legal_actions())
                if timing == "removal_after_cost":
                    assert counter_placed and breaker_used and target_chosen
                else:
                    assert not counter_placed and not breaker_used
                assert {f"official/c{BREAKER}.lua",
                        f"official/c{SKILL_DRAIN}.lua"}.issubset(
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail(f"Skill Drain did not negate Breaker at {timing}")
