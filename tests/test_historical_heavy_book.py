"""A chained Book of Moon resolves before Heavy Storm destroys it."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

HEAVY_STORM = 19613556
BOOK_OF_MOON = 14087893


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_book_chained_to_heavy_storm_still_sets_monster(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (HEAVY_STORM, BOOK_OF_MOON):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    decks = []
    for name, code in (("storm", HEAVY_STORM), ("book", BOOK_OF_MOON)):
        path = tmp_path / f"{name}.ydk"
        path.write_text("#main\n" + "\n".join(map(str, (
            code, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
        decks.append(str(path))

    with GoatEnvironment(*decks, seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        summoned = book_set = storm_used = book_chained = targeted = False
        monster_code = None
        for _ in range(70):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1:
                if not summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        monster_code = action.parameters["code"]
                        summoned = True
                if summoned and not book_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOOK_OF_MOON), None)
                    book_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and book_set \
                    and not storm_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == HEAVY_STORM), action)
                storm_used |= action is not None and action.kind == "activate"
            if storm_used and obs.acting_player == 1 and not book_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK_OF_MOON), action)
                book_chained |= action is not None and action.kind == "chain"
            if book_chained and not targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("controller") == 1
                               and a.parameters.get("code") == monster_code), None)
                targeted |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if targeted and HEAVY_STORM in {c.code for c in obs.graveyards[0]}:
                assert BOOK_OF_MOON in {c.code for c in obs.graveyards[1]}
                assert obs.chain == ()
                assert not any(c.zone == "spell_trap" for c in obs.field)
                hidden = [c for c in obs.field if c.controller == 1
                          and c.zone == "monster"]
                assert len(hidden) == 1
                assert hidden[0].position == "facedown"
                assert hidden[0].code is None
                owner = env.engine.probe.observation(1)
                assert any(c.code == monster_code and c.position == "facedown"
                           for c in owner.field)
                assert obs.life_points == (8000, 8000)
                loaded = env.engine.probe.loaded_script_sha256
                assert {f"official/c{HEAVY_STORM}.lua",
                        f"official/c{BOOK_OF_MOON}.lua"}.issubset(loaded)
                return
    pytest.fail("Heavy Storm / Book of Moon chain did not resolve")
