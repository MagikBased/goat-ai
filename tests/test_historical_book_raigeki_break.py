"""Book does not save a monster targeted by Raigeki Break from destruction."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

BREAK = 4178474
BOOK = 14087893
SERPENT = 511000818


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("respond", [False, True])
def test_book_chained_to_break_does_not_save_target(tmp_path, respond):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{BREAK}.lua", f"official/c{BOOK}.lua",
               f"pre-errata/c{SERPENT}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card scripts not installed")
    break_deck = tmp_path / "break.ydk"
    break_deck.write_text("#main\n" + "\n".join(map(str, (
        *([BREAK] * 3), SERPENT, *VANILLA_DECK[4:])))
        + "\n#extra\n!side\n")
    book_deck = tmp_path / "book.ydk"
    book_deck.write_text("#main\n" + "\n".join(map(str, (
        *([BOOK] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(break_deck), str(book_deck), seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {BREAK, SERPENT} <= {c.code for c in obs.hand}
        assert BOOK in {c.code for c in env.engine.probe.observation(1).hand}
        break_set = summoned = book_set = activated = discarded = targeted = False
        response_made = book_chained = book_targeted = False
        monster_code = None
        for _ in range(100):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not break_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == BREAK), None)
                break_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        monster_code = action.parameters["code"]
                        summoned = True
                if summoned and not book_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOOK), None)
                    book_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and book_set \
                    and not activated:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == BREAK), None)
                activated |= action is not None
            if activated and not discarded and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == SERPENT
                               and a.parameters.get("location") == 2), None)
                discarded = action is not None
            if discarded and not targeted and action is None \
                    and actions[0].kind == "select_card":
                assert SERPENT in {c.code for c in obs.graveyards[0]}
                action = next((a for a in actions if a.parameters.get("code")
                               == monster_code and a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 4), None)
                targeted = action is not None
            if targeted and obs.acting_player == 1 and not response_made:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK), None)
                if option is not None:
                    assert [link.card_code for link in obs.chain] == [BREAK]
                    action = option if respond else next(a for a in actions
                                                        if a.kind == "pass")
                    response_made = True
                    book_chained = respond
            if book_chained and not book_targeted \
                    and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == monster_code and a.parameters.get("controller") == 1), None)
                book_targeted = action is not None
                if book_targeted:
                    assert [link.card_code for link in obs.chain] == [BREAK, BOOK]
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if targeted and response_made and (not respond or book_targeted) and BREAK in {
                    c.code for c in obs.graveyards[0]} and not obs.chain:
                loaded = env.engine.probe.loaded_script_sha256
                if respond:
                    assert scripts <= loaded.keys()
                else:
                    assert f"official/c{BREAK}.lua" in loaded
                assert SERPENT in {c.code for c in obs.graveyards[0]}
                assert monster_code in {c.code for c in obs.graveyards[1]}
                assert not any(c.controller == 1 and c.zone == "monster" for c in obs.field)
                assert (BOOK in {c.code for c in obs.graveyards[1]}) == respond
                assert obs.life_points == (8000, 8000)
                return
    pytest.fail("Book / Raigeki Break chain did not resolve")
