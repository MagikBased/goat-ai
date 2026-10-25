"""Raigeki Break removes Book of Moon's target after paying its discard cost."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

RAIGEKI_BREAK = 4178474
BOOK = 14087893
SERPENT = 511000818


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("respond", [False, True])
def test_raigeki_break_chained_to_book_removes_target(tmp_path, respond):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{RAIGEKI_BREAK}.lua", f"official/c{BOOK}.lua",
               f"pre-errata/c{SERPENT}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card scripts not installed")
    break_deck = tmp_path / "break.ydk"
    break_deck.write_text("#main\n" + "\n".join(map(str, (
        *([RAIGEKI_BREAK] * 3), SERPENT, *VANILLA_DECK[4:])))
        + "\n#extra\n!side\n")
    book_deck = tmp_path / "book.ydk"
    book_deck.write_text("#main\n" + "\n".join(map(str, (
        *([BOOK] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(break_deck), str(book_deck), seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {RAIGEKI_BREAK, SERPENT} <= {card.code for card in obs.hand}
        assert BOOK in {card.code for card in env.engine.probe.observation(1).hand}
        break_set = summoned = book_used = book_targeted = False
        break_chained = serpent_discarded = break_targeted = False
        monster_code = None
        for _ in range(80):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not break_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == RAIGEKI_BREAK), None)
                break_set = action is not None
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
                if book_used and not book_targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.kind == "select_card"
                                   and a.parameters.get("code") == monster_code
                                   and a.parameters.get("controller") == 1), None)
                    book_targeted = action is not None
            if book_targeted and obs.acting_player == 0 and not break_chained:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == RAIGEKI_BREAK), None)
                assert option is not None
                assert [link.card_code for link in obs.chain] == [BOOK]
                if respond:
                    action = option
                    break_chained = True
            if break_chained and not serpent_discarded \
                    and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == SERPENT
                               and a.parameters.get("location") == 2), None)
                serpent_discarded = action is not None
            if serpent_discarded and not break_targeted and action is None \
                    and actions[0].kind == "select_card":
                assert SERPENT in {card.code for card in obs.graveyards[0]}
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == monster_code
                               and a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 4), None)
                break_targeted = action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if book_targeted and BOOK in {c.code for c in obs.graveyards[1]} \
                    and obs.chain == ():
                owner = env.engine.probe.observation(1)
                opponent = env.engine.probe.observation(0)
                assert obs.life_points == (8000, 8000)
                assert f"official/c{BOOK}.lua" in env.engine.probe.loaded_script_sha256
                if respond:
                    assert break_chained and serpent_discarded and break_targeted
                    assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                    assert RAIGEKI_BREAK in {c.code for c in obs.graveyards[0]}
                    assert SERPENT in {c.code for c in obs.graveyards[0]}
                    assert monster_code in {c.code for c in obs.graveyards[1]}
                    assert not any(c.controller == 1 and c.zone == "monster"
                                   for c in owner.field)
                    assert opponent.known_opponent_field_cards == ()
                else:
                    assert not break_chained
                    assert RAIGEKI_BREAK not in {c.code for c in obs.graveyards[0]}
                    assert SERPENT in {c.code for c in opponent.hand}
                    assert any(c.code == monster_code and c.position == "facedown"
                               for c in owner.field)
                    hidden = next(c for c in opponent.field if c.controller == 1
                                  and c.zone == "monster")
                    assert hidden.code is None and hidden.position == "facedown"
                    assert (1, "monster", hidden.sequence, monster_code) in {
                        (c.controller, c.zone, c.sequence, c.code)
                        for c in opponent.known_opponent_field_cards}
                return
    pytest.fail("Raigeki Break / Book response did not resolve")
