"""Book of Moon chained to Breaker's counter placement."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

BREAKER = 71413901
BOOK_OF_MOON = 14087893
BOTTOMLESS = 504700052


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
        book_resolved = breaker_flipped = False
        for _ in range(90):
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
            if book_resolved and observation.turn == 5 \
                    and observation.acting_player == 0 and not breaker_flipped:
                action = next((a for a in actions if a.kind == "flip_summon"
                               and a.parameters.get("code") == BREAKER), None)
                breaker_flipped |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind == "pass"), None)
            if action is None:
                action = next((a for a in actions if a.kind == "end_phase"), actions[0])
            observation = env.step(action)
            if not book_resolved and book_targeted and not observation.chain and any(
                    c.controller == 0 and c.zone == "monster" and c.position == "facedown"
                    for c in observation.field):
                assert observation.acting_player == 0
                own = env.engine.probe.observation(0)
                breaker = next(c for c in own.field if c.code == BREAKER)
                assert breaker.counters == ()
                assert not any(a.parameters.get("code") == BREAKER
                               and a.kind in ("activate", "chain") for a in env.legal_actions())
                book_resolved = True
            if breaker_flipped and not observation.chain and any(
                    c.code == BREAKER and c.position != "facedown"
                    for c in observation.field):
                breaker = next(c for c in observation.field if c.code == BREAKER)
                assert (breaker.attack, breaker.counters) == (1600, ())
                assert not any(a.parameters.get("code") == BREAKER
                               and a.kind in ("activate", "chain") for a in env.legal_actions())
                assert f"official/c{BREAKER}.lua" in env.engine.probe.loaded_script_sha256
                assert f"official/c{BOOK_OF_MOON}.lua" in env.engine.probe.loaded_script_sha256
                return
    pytest.fail("Book / Breaker line did not reach the counter-free Flip Summon")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_targeted_book_chains_to_breaker_removal_but_is_still_destroyed(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (BREAKER, BOOK_OF_MOON):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    attacker = tmp_path / "breaker.ydk"
    defender = tmp_path / "book.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        BREAKER, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    defender.write_text("#main\n" + "\n".join(map(str, (
        *([BOOK_OF_MOON] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=316,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        book_set = breaker_summoned = counter_placed = breaker_used = False
        breaker_targeted = book_chained = book_targeted = False
        for _ in range(80):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1 and not book_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == BOOK_OF_MOON), None)
                book_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not breaker_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == BREAKER), None)
                breaker_summoned |= action is not None
            if breaker_summoned and not counter_placed and obs.acting_player == 0 \
                    and any(c.code == BREAKER and c.counters == ((1, 1),)
                            for c in obs.field):
                counter_placed = True
            if counter_placed and obs.acting_player == 0 and not breaker_used:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BREAKER), None)
                if action is not None:
                    assert any(c.code == BREAKER and c.attack == 1900
                               for c in obs.field)
                    breaker_used = True
            if breaker_used and not breaker_targeted and actions[0].kind == "select_card":
                assert any(c.code == BREAKER and c.attack == 1600
                           and c.counters == () for c in obs.field)
                assert any(c.controller == 1 and c.zone == "spell_trap"
                           and c.position == "facedown" and c.code is None
                           for c in obs.field)
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 8
                               and "code" not in a.parameters), None)
                breaker_targeted |= action is not None
            if breaker_targeted and obs.acting_player == 1 and not book_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK_OF_MOON), None)
                book_chained |= action is not None
            if book_chained and not book_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == BREAKER
                               and a.parameters.get("controller") == 0), None)
                book_targeted |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if book_targeted and BOOK_OF_MOON in {
                    c.code for c in obs.graveyards[1]} and obs.chain == ():
                own = env.engine.probe.observation(0)
                opponent = env.engine.probe.observation(1)
                breaker = next(c for c in own.field if c.code == BREAKER)
                assert breaker.controller == 0 and breaker.position == "facedown"
                assert breaker.counters == ()
                assert not any(c.zone == "spell_trap" for c in own.field)
                assert any(c.controller == 0 and c.zone == "monster"
                           and c.code is None for c in opponent.field)
                assert any(c.controller == 0 and c.zone == "monster"
                           and c.code == BREAKER for c in opponent.known_opponent_field_cards)
                assert own.life_points == (8000, 8000)
                assert {f"official/c{code}.lua" for code in (
                    BREAKER, BOOK_OF_MOON)}.issubset(
                        env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Book did not chain to Breaker's already paid removal effect")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_bottomless_chains_to_breaker_counter_placement_before_counter_exists(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"official/c{BREAKER}.lua", f"goat/c{BOTTOMLESS}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    attacker = tmp_path / "breaker.ydk"
    defender = tmp_path / "bottomless.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        BREAKER, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    defender.write_text("#main\n" + "\n".join(map(str, (
        *([BOTTOMLESS] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=316,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert BREAKER in {c.code for c in obs.hand}
        bottomless_set = breaker_summoned = bottomless_chained = False
        for _ in range(70):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1 and not bottomless_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == BOTTOMLESS), None)
                bottomless_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not breaker_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == BREAKER), None)
                breaker_summoned |= action is not None
            if breaker_summoned and obs.acting_player == 1 and not bottomless_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOTTOMLESS), None)
                if action is not None:
                    assert obs.chain[0].card_code == BREAKER
                    breaker = next(c for c in obs.field if c.code == BREAKER)
                    assert (breaker.attack, breaker.counters) == (1600, ())
                    bottomless_chained = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if bottomless_chained and BREAKER in {c.code for c in obs.banished[0]}:
                assert obs.chain == ()
                assert not any(c.code == BREAKER for c in obs.field)
                assert not any(a.kind in ("activate", "chain")
                               and a.parameters.get("code") == BREAKER
                               for a in env.legal_actions())
                assert BOTTOMLESS in {c.code for c in obs.graveyards[1]}
                assert {f"official/c{BREAKER}.lua", f"goat/c{BOTTOMLESS}.lua"}.issubset(
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Bottomless did not banish Breaker before its counter was placed")
