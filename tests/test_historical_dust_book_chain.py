"""Dust destroys a chained Book without negating its monster flip."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

DUST = 60082869
BOOK = 14087893


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("set_from_hand", [False, True])
def test_dust_chained_to_book_destroys_it_without_negating_flip(tmp_path,
                                                                 set_from_hand):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (DUST, BOOK)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required official card script not installed")
    dust_cards = list(VANILLA_DECK)
    dust_cards[0] = DUST
    dust_cards[1] = BOOK
    dust = tmp_path / "dust.ydk"
    dust.write_text("#main\n" + "\n".join(map(str, dust_cards))
                    + "\n#extra\n!side\n")
    book = tmp_path / "book.ydk"
    book.write_text("#main\n" + "\n".join(map(str, (
        BOOK, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(dust), str(book), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {DUST, BOOK} <= {c.code for c in obs.hand}
        assert BOOK in {c.code for c in env.engine.probe.observation(1).hand}
        dust_set = summoned = book_used = book_targeted = dust_chained = False
        dust_targeted = set_chosen = set_placed = False
        monster_code = None
        for _ in range(90):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not dust_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == DUST), None)
                dust_set = action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        monster_code = action.parameters["code"]
                        summoned = True
                if summoned and not book_used and action is None:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == BOOK), None)
                    book_used = action is not None
                if book_used and not book_targeted \
                        and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == monster_code and a.parameters.get("controller") == 1),
                                  None)
                    book_targeted = action is not None
            if book_targeted and obs.acting_player == 0 and not dust_chained:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == DUST), None)
                if option is not None:
                    assert [link.card_code for link in obs.chain] == [BOOK]
                    action = option
                    dust_chained = True
            if dust_chained and not dust_targeted \
                    and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == BOOK
                               and a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 8), None)
                dust_targeted = action is not None
            if dust_targeted and not set_chosen \
                    and any(a.kind == "yes" for a in actions):
                assert BOOK in {c.code for c in obs.graveyards[1]}
                action = next(a for a in actions if a.kind == (
                    "yes" if set_from_hand else "no"))
                set_chosen = True
            if set_chosen and set_from_hand and not set_placed \
                    and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == BOOK
                               and a.parameters.get("controller") == 0), None)
                set_placed = action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if dust_targeted and set_chosen and DUST in {
                    c.code for c in obs.graveyards[0]} and not obs.chain:
                owner = env.engine.probe.observation(1)
                target = next(c for c in owner.field if c.zone == "monster"
                              and c.controller == 1)
                assert target.code == monster_code and target.position == "facedown"
                opponent = env.engine.probe.observation(0)
                hidden = next(c for c in opponent.field if c.controller == 1
                              and c.zone == "monster")
                assert hidden.code is None and hidden.position == "facedown"
                assert (1, "monster", hidden.sequence, monster_code) in {
                    (c.controller, c.zone, c.sequence, c.code)
                    for c in opponent.known_opponent_field_cards}
                assert BOOK in {c.code for c in obs.graveyards[1]}
                assert obs.life_points == (8000, 8000)
                assert set_placed == set_from_hand
                assert any(c.code == BOOK for c in opponent.field
                           if c.controller == 0 and c.zone == "spell_trap") == set_from_hand
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                return
    pytest.fail("Dust / Book response did not resolve")
