"""Historical Snatch Steal / Book of Moon control and field memory."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

SNATCH_STEAL = 45986603
BOOK_OF_MOON = 14087893


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_book_on_snatch_stolen_monster_keeps_control_and_known_identity(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (SNATCH_STEAL, BOOK_OF_MOON):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    deck = tmp_path / "snatch_book.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        SNATCH_STEAL, BOOK_OF_MOON, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        summoned = snatched = booked = False
        summoned_code = None
        for _ in range(50):
            actions = env.legal_actions()
            action = None
            if observation.turn == 2 and observation.acting_player == 1 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    summoned = True
                    summoned_code = action.parameters["code"]
            if observation.turn == 3 and observation.acting_player == 0 and not snatched:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SNATCH_STEAL), action)
                snatched |= action is not None and action.kind == "activate"
            stolen = next((card for card in observation.field
                           if card.zone == "monster" and card.controller == 0
                           and card.code == summoned_code), None)
            if (observation.turn == 3 and observation.acting_player == 0
                    and snatched and not booked and stolen is not None):
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == BOOK_OF_MOON), action)
                booked |= action is not None and action.kind == "activate"
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "select_position", "pass", "end_phase")), actions[0])
            if action.kind == "select_card" and booked:
                assert action.parameters["code"] == summoned_code
                assert action.parameters["controller"] == 0
            observation = env.step(action)
            own = env.engine.probe.observation(0)
            if booked and {SNATCH_STEAL, BOOK_OF_MOON}.issubset(
                    {card.code for card in own.graveyards[0]}):
                facedown = next(card for card in own.field
                                if card.zone == "monster" and card.controller == 0)
                assert facedown.code == summoned_code
                assert facedown.position == "facedown"
                assert not any(card.code == SNATCH_STEAL for card in own.field)
                opponent = env.engine.probe.observation(1)
                hidden = next(card for card in opponent.field
                              if card.zone == "monster" and card.controller == 0)
                assert hidden.code is None and hidden.position == "facedown"
                assert (0, "monster", hidden.sequence, summoned_code) in {
                    (card.controller, card.zone, card.sequence, card.code)
                    for card in opponent.known_opponent_field_cards}
                return
    pytest.fail("Snatch Steal / Book of Moon did not reach the face-down outcome")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_book", [False, True])
def test_book_chain_timing_on_snatch_activation(tmp_path, chain_book):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (SNATCH_STEAL, BOOK_OF_MOON):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    attacker = tmp_path / "snatch.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        SNATCH_STEAL, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    defender = tmp_path / "book.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        BOOK_OF_MOON, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert SNATCH_STEAL in {c.code for c in obs.hand}
        assert BOOK_OF_MOON in {c.code for c in env.engine.probe.observation(1).hand}
        summoned = book_set = snatch_used = target_chosen = book_chained = False
        book_target_chosen = False
        summoned_code = None
        for _ in range(70):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1:
                if not summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        summoned = True
                        summoned_code = action.parameters["code"]
                if summoned and not book_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOOK_OF_MOON), None)
                    book_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not snatch_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SNATCH_STEAL), action)
                snatch_used |= action is not None and action.kind == "activate"
            if snatch_used and not target_chosen and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("code") == summoned_code), None)
                target_chosen |= action is not None
            if (chain_book and target_chosen and obs.acting_player == 1
                    and not book_chained):
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK_OF_MOON), None)
                if option is not None:
                    assert obs.chain[0].card_code == SNATCH_STEAL
                    action = option
                    book_chained = True
            if book_chained and not book_target_chosen \
                    and obs.acting_player == 1 and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("code") == summoned_code), None)
                book_target_chosen |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            own = env.engine.probe.observation(0)
            if snatch_used and target_chosen and own.turn == 3 \
                    and own.phase == "main1" and not own.chain:
                if chain_book:
                    if SNATCH_STEAL not in {c.code for c in own.graveyards[0]}:
                        continue
                    assert book_set and book_chained and book_target_chosen
                    defender_view = env.engine.probe.observation(1)
                    monster = next(c for c in defender_view.field
                                   if c.zone == "monster" and c.code == summoned_code)
                    assert monster.controller == 1 and monster.position == "facedown"
                    assert BOOK_OF_MOON in {c.code for c in own.graveyards[1]}
                    hidden = next(c for c in own.field if c.zone == "monster"
                                  and c.controller == 1)
                    assert hidden.code is None and hidden.position == "facedown"
                    assert (1, "monster", hidden.sequence, summoned_code) in {
                        (c.controller, c.zone, c.sequence, c.code)
                        for c in own.known_opponent_field_cards}
                    assert not any(c.code == SNATCH_STEAL for c in own.field)
                else:
                    if not any(c.code == SNATCH_STEAL for c in own.field):
                        continue
                    monster = next(c for c in own.field
                                   if c.zone == "monster" and c.code == summoned_code)
                    assert book_set and not book_chained
                    assert monster.controller == 0 and monster.position == "faceup"
                    assert BOOK_OF_MOON not in {c.code for c in own.graveyards[1]}
                assert {f"official/c{SNATCH_STEAL}.lua",
                        f"official/c{BOOK_OF_MOON}.lua"}.issubset(
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Snatch Steal / chained Book did not resolve within 70 decisions")
