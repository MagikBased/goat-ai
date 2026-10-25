"""Bazoo's Graveyard banish cost feeds Return in Chaos Return."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

BAZOO = 40133511
GRACEFUL = 79571449
RETURN = 27174286
FIRST = 62651957
SECOND = 97590747


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_bazoo_banish_cost_boost_and_return_revival(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (BAZOO, GRACEFUL, RETURN):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    deck = tmp_path / "bazoo_return.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL, *([BAZOO] * 3), *([RETURN] * 3), *VANILLA_DECK[7:])))
                    + "\n#extra\n!side\n")
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, BAZOO, RETURN, FIRST, SECOND}.issubset(
            c.code for c in obs.hand)
        graceful = discarded = summoned = bazoo_used = cost_paid = False
        trap_set = boosted = expired = return_used = return_resolved = False
        for _ in range(100):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    graceful |= action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"] for c in
                                   a.parameters["cards"]} == {FIRST, SECOND}), None)
                    discarded |= action is not None
                if discarded and not summoned and action is None:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == BAZOO), None)
                    summoned |= action is not None
                if summoned and not bazoo_used and action is None:
                    action = next((a for a in actions if a.kind in ("activate", "chain")
                                   and a.parameters.get("code") == BAZOO), None)
                    bazoo_used |= action is not None
                if bazoo_used and not cost_paid:
                    action = next((a for a in actions if a.kind == "select_cards"
                                   and {c["code"] for c in
                                   a.parameters["cards"]} == {FIRST, SECOND}), action)
                    if action is not None and action.kind == "select_cards":
                        assert len(actions) == 3
                        assert {a.parameters["code"] for a in actions
                                if a.kind == "select_card"} == {FIRST, SECOND}
                    cost_paid |= action is not None and action.kind == "select_cards"
                if boosted and not trap_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == RETURN), None)
                    trap_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not return_used:
                if not expired:
                    assert any(c.code == BAZOO and c.attack == 1600 for c in obs.field)
                    expired = True
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == RETURN), action)
                return_used |= action is not None and action.kind == "activate"
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_cards", "select_card", "place", "select_position",
                    "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if cost_paid and not boosted and any(
                    c.code == BAZOO and c.attack == 2200 for c in obs.field):
                assert {c.code for c in obs.banished[0]} == {FIRST, SECOND}
                boosted = True
            if return_used and not return_resolved \
                    and RETURN in {c.code for c in obs.graveyards[0]}:
                assert obs.life_points == (4000, 8000)
                assert {FIRST, SECOND}.issubset({c.code for c in obs.field})
                assert any(c.code == BAZOO and c.attack == 1600 for c in obs.field)
                return_resolved = True
            if return_resolved and obs.turn >= 4:
                assert graceful and discarded and summoned and bazoo_used
                assert cost_paid and boosted and trap_set and expired
                assert {c.code for c in obs.banished[0]} == {FIRST, SECOND}
                assert any(c.code == BAZOO for c in obs.field)
                assert not any(c.code in (FIRST, SECOND) for c in obs.field)
                assert {f"official/c{code}.lua" for code in (BAZOO, RETURN)}.issubset(
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail(f"Bazoo/Return line did not resolve: turn={obs.turn} "
                f"phase={obs.phase} flags={graceful, discarded, summoned, bazoo_used, cost_paid, trap_set, boosted, expired, return_used, return_resolved} "
                f"field={[(c.code, c.attack) for c in obs.field]} "
                f"banished={[c.code for c in obs.banished[0]]}")
