"""A set Scapegoat may chain to Breaker and leave its four Tokens behind."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

BREAKER = 71413901
SCAPEGOAT = 504700123
SHEEP = {73915052, 73915053, 73915054, 73915055}


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_scapegoat", [False, True])
def test_breaker_targets_set_scapegoat_with_optional_chain(tmp_path, chain_scapegoat):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"official/c{BREAKER}.lua", f"goat/c{SCAPEGOAT}.lua")
    for relative in scripts:
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    breaker_deck = tmp_path / "breaker.ydk"
    breaker_deck.write_text("#main\n" + "\n".join(map(str, (
        BREAKER, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    goat_deck = tmp_path / "scapegoat.ydk"
    goat_deck.write_text("#main\n" + "\n".join(map(str, (
        SCAPEGOAT, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(breaker_deck), str(goat_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert BREAKER in {c.code for c in obs.hand}
        assert SCAPEGOAT in {c.code for c in env.engine.probe.observation(1).hand}
        goat_set = breaker_summoned = counter_placed = breaker_used = False
        goat_targeted = response_made = False
        for _ in range(85):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1 and not goat_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                goat_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and goat_set:
                if not breaker_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == BREAKER), None)
                    breaker_summoned |= action is not None
                if breaker_summoned and not counter_placed and any(
                        c.code == BREAKER and c.counters == ((1, 1),)
                        for c in obs.field):
                    counter_placed = True
                if counter_placed and not breaker_used:
                    action = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == BREAKER), action)
                    breaker_used |= action is not None and action.kind == "chain"
                if breaker_used and not goat_targeted \
                        and actions[0].kind == "select_card":
                    assert any(c.controller == 1 and c.zone == "spell_trap"
                               and c.position == "facedown" and c.code is None
                               for c in obs.field)
                    action = next((a for a in actions if a.kind == "select_card"
                                   and a.parameters.get("controller") == 1
                                   and a.parameters.get("location") == 8
                                   and "code" not in a.parameters), None)
                    goat_targeted |= action is not None
            if goat_targeted and obs.acting_player == 1 and not response_made:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                if option is not None:
                    assert tuple(link.card_code for link in obs.chain) == (BREAKER,)
                    action = option if chain_scapegoat else next(
                        a for a in actions if a.kind == "pass")
                    response_made = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if response_made and SCAPEGOAT in {c.code for c in obs.graveyards[1]}:
                assert obs.chain == ()
                assert BREAKER in {c.code for c in obs.field}
                assert next(c for c in obs.field if c.code == BREAKER).counters == ()
                assert not any(c.zone == "spell_trap" for c in obs.field)
                tokens = [c for c in obs.field if c.controller == 1
                          and c.code in SHEEP]
                assert len(tokens) == (4 if chain_scapegoat else 0)
                assert {c.code for c in tokens} == (SHEEP if chain_scapegoat else set())
                assert not any(c.code in SHEEP for pile in obs.graveyards
                               for c in pile)
                assert obs.life_points == (8000, 8000)
                assert set(scripts) <= env.engine.probe.loaded_script_sha256.keys()
                return
    pytest.fail("Breaker / Scapegoat response did not resolve")
