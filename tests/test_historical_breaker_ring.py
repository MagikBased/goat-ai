"""Ring chained to Breaker's destruction resolves before the pending effect."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

BREAKER = 71413901
RING = 511000824
BOOK = 14087893


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_ring_destroys_breaker_after_counter_cost_but_book_is_still_destroyed(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"official/c{BREAKER}.lua", f"pre-errata/c{RING}.lua",
               f"official/c{BOOK}.lua")
    for script in scripts:
        if not (root / "scripts" / script).is_file():
            pytest.skip(f"script {script} not installed")
    breaker_deck = tmp_path / "breaker.ydk"
    breaker_deck.write_text("#main\n" + "\n".join(map(str, (
        BREAKER, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    defender_deck = tmp_path / "defender.ydk"
    defender_deck.write_text("#main\n" + "\n".join(map(str, (
        RING, BOOK, BOOK, BOOK, *VANILLA_DECK[4:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(breaker_deck), str(defender_deck), seed=316,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert BREAKER in {c.code for c in obs.hand}
        assert {RING, BOOK} <= {c.code for c in env.engine.probe.observation(1).hand}
        book_set = ring_set = breaker_summoned = breaker_used = False
        book_targeted = ring_chained = breaker_targeted = False
        for _ in range(90):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1:
                if not book_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOOK), None)
                    book_set |= action is not None
                if book_set and not ring_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == RING), None)
                    ring_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and ring_set:
                if not breaker_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == BREAKER), None)
                    breaker_summoned |= action is not None
                if breaker_summoned and not breaker_used:
                    option = next((a for a in actions if a.kind in ("activate", "chain")
                                   and a.parameters.get("code") == BREAKER), None)
                    if option is not None:
                        breaker = next(c for c in obs.field if c.code == BREAKER)
                        assert (breaker.attack, breaker.counters) == (1900, ((1, 1),))
                        action = option
                        breaker_used = True
            if breaker_used and not book_targeted and actions[0].kind == "select_card":
                breaker = next(c for c in obs.field if c.code == BREAKER)
                assert (breaker.attack, breaker.counters) == (1600, ())
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 8), None)
                book_targeted |= action is not None
                if action is not None:
                    assert action.parameters.get("code") is None
            if book_targeted and obs.acting_player == 1 and not ring_chained:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == RING), None)
                if option is not None:
                    assert obs.chain[0].card_code == BREAKER
                    action = option
                    ring_chained = True
            if ring_chained and not breaker_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 0
                               and a.parameters.get("code") == BREAKER), None)
                breaker_targeted |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if breaker_targeted and not obs.chain and RING in {
                    c.code for c in obs.graveyards[1]}:
                assert obs.life_points == (6400, 6400)
                assert BREAKER in {c.code for c in obs.graveyards[0]}
                assert BOOK in {c.code for c in obs.graveyards[1]}
                assert not any(c.code == BREAKER for c in obs.field)
                assert set(scripts).issubset(env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Breaker/Ring response did not resolve within 90 decisions")
