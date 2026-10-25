"""Torrential Tribute summon response and Book of Moon chain."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

TORRENTIAL_TRIBUTE = 53582587
BOOK_OF_MOON = 14087893


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_torrential_after_summon_destroys_faceup_and_book_facedown_monsters(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (TORRENTIAL_TRIBUTE, BOOK_OF_MOON):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    paths = []
    for name, code in (("attacker", BOOK_OF_MOON),
                       ("defender", TORRENTIAL_TRIBUTE)):
        path = tmp_path / f"{name}.ydk"
        path.write_text("#main\n" + "\n".join(map(str, (
            code, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
        paths.append(path)

    with GoatEnvironment(*(str(path) for path in paths), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        summons = 0
        set_trap = chained_torrential = chained_book = False
        summoned_codes = []
        for _ in range(55):
            actions = env.legal_actions()
            action = None
            if (observation.acting_player == 0 and observation.turn in (1, 3)
                    and summons < (1 if observation.turn == 1 else 2)):
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    summons += 1
                    summoned_codes.append(action.parameters["code"])
            if observation.acting_player == 1 and observation.turn == 2 and not set_trap:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == TORRENTIAL_TRIBUTE), action)
                set_trap |= action is not None and action.kind == "set_spell_trap"
            if observation.acting_player == 1 and observation.turn == 3 and not chained_torrential:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == TORRENTIAL_TRIBUTE), action)
                if action is not None and action.kind == "chain":
                    assert summons == 2
                    assert observation.phase == "main1"
                    chained_torrential = True
            if observation.acting_player == 0 and chained_torrential and not chained_book:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK_OF_MOON), action)
                chained_book |= action is not None and action.kind == "chain"
            if action is None and summoned_codes:
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == summoned_codes[0]), None)
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if set_trap and not chained_torrential and observation.acting_player == 0:
                assert any(card.controller == 1 and card.zone == "spell_trap"
                           and card.position == "facedown" and card.code is None
                           for card in observation.field)
            if chained_book and any(card.code == TORRENTIAL_TRIBUTE
                                    for card in observation.graveyards[1]):
                assert set_trap and chained_torrential
                assert len(summoned_codes) == 2
                assert not any(card.zone == "monster" for card in observation.field)
                assert ({card.code for card in observation.graveyards[0]}
                        >= {*summoned_codes, BOOK_OF_MOON})
                assert observation.life_points == (8000, 8000)
                return
    pytest.fail("Torrential Tribute / Book of Moon chain did not resolve")
