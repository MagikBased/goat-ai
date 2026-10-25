"""Mirror Force and Book of Moon attack-response regression."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

MIRROR_FORCE = 44095762
BOOK_OF_MOON = 14087893


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_book_saves_attacker_but_mirror_force_destroys_other_attacker(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (MIRROR_FORCE, BOOK_OF_MOON):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    paths = []
    for name, code in (("attacker", BOOK_OF_MOON), ("defender", MIRROR_FORCE)):
        path = tmp_path / f"{name}.ydk"
        path.write_text("#main\n" + "\n".join(map(str, (
            code, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
        paths.append(path)

    with GoatEnvironment(*(str(path) for path in paths), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        summons = 0
        set_mirror = attacked = chained_mirror = chained_book = False
        attacker_code = other_code = None
        for _ in range(65):
            actions = env.legal_actions()
            action = None
            if (observation.acting_player == 0 and observation.turn in (1, 3)
                    and summons < (1 if observation.turn == 1 else 2)):
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    summons += 1
                    if summons == 2:
                        other_code = action.parameters["code"]
            if observation.acting_player == 1 and observation.turn == 2 and not set_mirror:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == MIRROR_FORCE), action)
                set_mirror |= action is not None and action.kind == "set_spell_trap"
            if (action is None and observation.acting_player == 0 and observation.turn == 3
                    and summons == 2 and not attacked):
                action = next((a for a in actions if a.kind in ("battle_phase", "attack")), None)
                if action is not None and action.kind == "attack":
                    attacked = True
                    attacker_code = action.parameters["code"]
            if observation.acting_player == 1 and attacked and not chained_mirror:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == MIRROR_FORCE), action)
                chained_mirror |= action is not None and action.kind == "chain"
                if chained_mirror:
                    assert observation.phase == "battle_step"
            if observation.acting_player == 0 and chained_mirror and not chained_book:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK_OF_MOON), action)
                chained_book |= action is not None and action.kind == "chain"
            if action is None:
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == attacker_code), None)
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if chained_book and any(card.code == MIRROR_FORCE
                                    for card in observation.graveyards[1]):
                assert set_mirror and attacked and chained_mirror
                assert attacker_code != other_code
                monsters = [card for card in observation.field if card.zone == "monster"]
                assert len(monsters) == 1
                assert monsters[0].controller == 0
                assert monsters[0].code == attacker_code
                assert monsters[0].position == "facedown"
                assert any(card.code == other_code for card in observation.graveyards[0])
                assert any(card.code == BOOK_OF_MOON
                           for card in observation.graveyards[0])
                assert observation.life_points == (8000, 8000)
                return
    pytest.fail("Mirror Force / Book of Moon chain did not resolve")
