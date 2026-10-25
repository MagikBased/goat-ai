"""Book of Moon chained to Breaker's counter placement."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

BREAKER = 71413901
BOOK_OF_MOON = 14087893


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_book_chained_to_breaker_summon_keeps_counter_off(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (BREAKER, BOOK_OF_MOON):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    attacker = tmp_path / "breaker.ydk"
    defender = tmp_path / "book.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        BREAKER, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    defender.write_text("#main\n" + "\n".join(map(str, (
        BOOK_OF_MOON, BOOK_OF_MOON, BOOK_OF_MOON, *VANILLA_DECK[3:])))
        + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=316,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        book_set = breaker_summoned = book_chained = book_targeted = False
        for _ in range(65):
            actions = env.legal_actions()
            action = None
            if observation.turn == 2 and observation.acting_player == 1 \
                    and not book_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == BOOK_OF_MOON), None)
                book_set |= action is not None
            if observation.turn == 3 and observation.acting_player == 0 \
                    and not breaker_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == BREAKER), None)
                breaker_summoned |= action is not None
            if breaker_summoned and observation.acting_player == 1 and not book_chained:
                chain = next((a for a in actions if a.kind == "chain"
                              and a.parameters.get("code") == BOOK_OF_MOON), None)
                if chain is not None:
                    assert observation.chain[0].card_code == BREAKER
                    breaker = next(c for c in observation.field if c.code == BREAKER)
                    assert (breaker.attack, breaker.counters) == (1600, ())
                    action = chain
                    book_chained = True
            if book_chained and not book_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == BREAKER), None)
                book_targeted |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind == "pass"), None)
            if action is None:
                action = next((a for a in actions if a.kind == "end_phase"), actions[0])
            observation = env.step(action)
            if book_targeted and not observation.chain and any(
                    c.controller == 0 and c.zone == "monster" and c.position == "facedown"
                    for c in observation.field):
                assert observation.acting_player == 0
                own = env.engine.probe.observation(0)
                breaker = next(c for c in own.field if c.code == BREAKER)
                assert breaker.counters == ()
                assert not any(a.parameters.get("code") == BREAKER
                               and a.kind in ("activate", "chain") for a in env.legal_actions())
                assert f"official/c{BREAKER}.lua" in env.engine.probe.loaded_script_sha256
                assert f"official/c{BOOK_OF_MOON}.lua" in env.engine.probe.loaded_script_sha256
                return
    pytest.fail("Book did not turn Breaker facedown before its counter resolved")
