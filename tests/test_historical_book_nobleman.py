"""Book of Moon creates a legal Nobleman target from a face-up staple."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

BOOK_OF_MOON = 14087893
NOBLEMAN = 504700116
BREAKER = 71413901


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_book_sets_breaker_then_nobleman_banishes_it(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"official/c{BOOK_OF_MOON}.lua", f"goat/c{NOBLEMAN}.lua",
                     f"official/c{BREAKER}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    attacker = tmp_path / "book_nobleman.ydk"
    defender = tmp_path / "breaker.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        BOOK_OF_MOON, NOBLEMAN, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    defender.write_text("#main\n" + "\n".join(map(str, (
        BREAKER, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert {BOOK_OF_MOON, NOBLEMAN}.issubset(c.code for c in observation.hand)
        breaker_summoned = book_used = book_targeted = nobleman_used = False
        nobleman_targeted = False
        for _ in range(75):
            actions = env.legal_actions()
            action = None
            if observation.turn == 2 and observation.acting_player == 1 \
                    and not breaker_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == BREAKER), None)
                breaker_summoned |= action is not None
            if observation.turn == 3 and observation.acting_player == 0 \
                    and observation.phase == "main1" and breaker_summoned:
                if not book_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == BOOK_OF_MOON), None)
                    book_used |= action is not None
                elif book_targeted and not nobleman_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == NOBLEMAN), None)
                    nobleman_used |= action is not None
            if book_used and not book_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == BREAKER), None)
                book_targeted |= action is not None
            if nobleman_used and not nobleman_targeted and actions[0].kind == "select_card":
                assert any(c.controller == 1 and c.zone == "monster"
                           and c.position == "facedown" and c.code is None
                           for c in observation.field)
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("controller") == 1
                               and "code" not in a.parameters), None)
                nobleman_targeted |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind == "pass"), None)
            if action is None:
                action = next((a for a in actions if a.kind == "end_phase"), actions[0])
            observation = env.step(action)
            if nobleman_targeted and any(c.code == BREAKER
                                         for c in observation.banished[1]):
                assert not any(c.code == BREAKER for c in observation.graveyards[1])
                assert not any(c.code == BREAKER for c in observation.field)
                assert not observation.private_reveals
                loaded = env.engine.probe.loaded_script_sha256
                assert {f"official/c{BOOK_OF_MOON}.lua", f"goat/c{NOBLEMAN}.lua",
                        f"official/c{BREAKER}.lua"}.issubset(loaded)
                return
    pytest.fail("Book of Moon / Nobleman line did not banish Breaker")
