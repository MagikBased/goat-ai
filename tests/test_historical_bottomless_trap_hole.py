"""GOAT Bottomless Trap Hole and the historical Book of Moon response."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

BOTTOMLESS = 504700052  # GOAT variant
BOOK_OF_MOON = 14087893
GEMINI_ELF = 69140098


def _deck(path, cards):
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("book_response", [False, True])
def test_bottomless_banishes_summoned_monster_unless_book_sets_it(tmp_path,
                                                                   book_response):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/goat/c{BOTTOMLESS}.lua").is_file():
        pytest.skip("GOAT Bottomless script not installed")
    if not (root / f"scripts/official/c{BOOK_OF_MOON}.lua").is_file():
        pytest.skip("Book of Moon script not installed")
    ordinary = [code for code in VANILLA_DECK if code != GEMINI_ELF]
    attacker = _deck(tmp_path / "attacker.ydk", (
        *([GEMINI_ELF] * 3), *([BOOK_OF_MOON] * 3), *ordinary[:34]))
    defender = _deck(tmp_path / "defender.ydk", (
        *([BOTTOMLESS] * 3), *VANILLA_DECK[3:]))
    with GoatEnvironment(attacker, defender, seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        set_book = set_bottomless = summoned = chained_bottomless = False
        chained_book = False
        for _ in range(45):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not set_book:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == BOOK_OF_MOON), None)
                set_book |= action is not None
            if observation.turn == 2 and observation.acting_player == 1 \
                    and not set_bottomless:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == BOTTOMLESS), None)
                set_bottomless |= action is not None
            if observation.turn == 3 and observation.acting_player == 0 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == GEMINI_ELF), None)
                summoned |= action is not None
            if summoned and observation.acting_player == 1 and not chained_bottomless:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOTTOMLESS), None)
                if action is not None:
                    assert observation.phase == "main1"
                    assert any(c.code == GEMINI_ELF and c.position == "faceup"
                               for c in observation.field)
                    chained_bottomless = True
            if chained_bottomless and book_response and observation.acting_player == 0 \
                    and not chained_book:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK_OF_MOON), None)
                chained_book |= action is not None
            if chained_book and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == GEMINI_ELF), None)
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if chained_bottomless and any(c.code == BOTTOMLESS
                                           for c in observation.graveyards[1]):
                assert observation.life_points == (8000, 8000)
                assert f"goat/c{BOTTOMLESS}.lua" in env.engine.probe.loaded_script_sha256
                if book_response:
                    assert chained_book
                    assert not observation.banished[0]
                    assert any(c.code == GEMINI_ELF and c.position == "facedown"
                               for c in observation.field)
                    other = env.engine.probe.observation(1)
                    assert any(c.controller == 0 and c.code is None
                               and c.position == "facedown" for c in other.field)
                    assert any(c.controller == 0 and c.code == GEMINI_ELF
                               for c in other.known_opponent_field_cards)
                    assert BOOK_OF_MOON in {c.code for c in observation.graveyards[0]}
                else:
                    assert not any(c.code == GEMINI_ELF for c in observation.field)
                    assert GEMINI_ELF in {c.code for c in observation.banished[0]}
                    assert GEMINI_ELF not in {c.code for c in observation.graveyards[0]}
                return
    pytest.fail(f"Bottomless summon response did not resolve (book={book_response})")
