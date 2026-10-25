"""Premature Burial leaves different outcomes when its equip link is broken."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

GRACEFUL_CHARITY = 79571449
PREMATURE_BURIAL = 70828912
BOOK_OF_MOON = 14087893
MYSTICAL_SPACE_TYPHOON = 5318639
MYSTICAL_ELF = 15025844
SECOND_DISCARD = 79182538


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("response", [BOOK_OF_MOON, MYSTICAL_SPACE_TYPHOON])
def test_premature_equip_break_by_flip_or_destruction(tmp_path, response):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (GRACEFUL_CHARITY, PREMATURE_BURIAL, response):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    deck = tmp_path / "premature.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL_CHARITY, PREMATURE_BURIAL, response, *VANILLA_DECK[3:])))
                    + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        graceful = discarded = premature = response_used = False
        for _ in range(45):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0:
                if not graceful:
                    option = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL_CHARITY), None)
                    if option is not None:
                        action = option
                        graceful = True
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"]
                                   for c in a.parameters["cards"]} == {
                                       MYSTICAL_ELF, SECOND_DISCARD}), None)
                    discarded = action is not None
                if discarded and not premature:
                    option = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == PREMATURE_BURIAL), None)
                    if option is not None:
                        assert MYSTICAL_ELF in {c.code for c in observation.graveyards[0]}
                        action = option
                        premature = True
                revived = any(c.code == MYSTICAL_ELF and c.zone == "monster"
                              and c.position == "faceup" for c in observation.field)
                if premature and revived and not response_used:
                    assert observation.life_points == (7200, 8000)
                    assert any(c.code == PREMATURE_BURIAL and c.zone == "spell_trap"
                               for c in observation.field)
                    option = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == response), None)
                    if option is not None:
                        action = option
                        response_used = True
                if actions[0].kind == "select_card" and premature:
                    target = (PREMATURE_BURIAL if response_used
                              and response == MYSTICAL_SPACE_TYPHOON else MYSTICAL_ELF)
                    action = next((a for a in actions if a.parameters.get("code") == target
                                   and a.parameters.get("controller") == 0), action)
            grave = {c.code for c in observation.graveyards[0]}
            if response_used and {PREMATURE_BURIAL, response}.issubset(grave) \
                    and any(a.kind == "normal_summon" for a in actions):
                assert observation.life_points == (7200, 8000)
                own_monsters = [c for c in observation.field if c.zone == "monster"]
                if response == BOOK_OF_MOON:
                    assert len(own_monsters) == 1
                    assert own_monsters[0].code == MYSTICAL_ELF
                    assert own_monsters[0].position == "facedown"
                    assert MYSTICAL_ELF not in grave
                    other = env.engine.probe.observation(1)
                    hidden = next(c for c in other.field if c.zone == "monster")
                    assert hidden.code is None and hidden.position == "facedown"
                    assert (0, "monster", hidden.sequence, MYSTICAL_ELF) in {
                        (c.controller, c.zone, c.sequence, c.code)
                        for c in other.known_opponent_field_cards}
                else:
                    assert not own_monsters
                    assert MYSTICAL_ELF in grave
                loaded = env.engine.probe.loaded_script_sha256
                assert f"official/c{PREMATURE_BURIAL}.lua" in loaded
                assert f"official/c{response}.lua" in loaded
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
    pytest.fail("Premature Burial response did not reach its final state")
