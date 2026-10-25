"""Call of the Haunted remains after Book of Moon severs its monster link."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

GRACEFUL_CHARITY = 79571449
CALL_OF_THE_HAUNTED = 97077563
BOOK_OF_MOON = 14087893
MYSTICAL_ELF = 15025844
SECOND_DISCARD = 79182538


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_book_on_call_revived_monster_leaves_call_faceup_and_monster_facedown(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (GRACEFUL_CHARITY, CALL_OF_THE_HAUNTED, BOOK_OF_MOON):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    deck = tmp_path / "call_book.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL_CHARITY, CALL_OF_THE_HAUNTED, BOOK_OF_MOON,
        *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        graceful = discarded = call_set = call_used = book_used = False
        for _ in range(55):
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
                if discarded and not call_set:
                    option = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == CALL_OF_THE_HAUNTED), None)
                    if option is not None:
                        action = option
                        call_set = True
            if observation.turn == 3 and observation.acting_player == 0:
                if call_set and not call_used:
                    option = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == CALL_OF_THE_HAUNTED), None)
                    if option is not None:
                        assert MYSTICAL_ELF in {c.code for c in observation.graveyards[0]}
                        action = option
                        call_used = True
                revived = any(c.code == MYSTICAL_ELF and c.zone == "monster"
                              and c.position == "faceup" for c in observation.field)
                if call_used and revived and not book_used:
                    assert any(c.code == CALL_OF_THE_HAUNTED and c.position == "faceup"
                               for c in observation.field)
                    option = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == BOOK_OF_MOON), None)
                    if option is not None:
                        action = option
                        book_used = True
                if actions[0].kind == "select_card" and call_used:
                    action = next((a for a in actions if a.parameters.get("code")
                                   == MYSTICAL_ELF and a.parameters.get("controller") == 0),
                                  action)
            if book_used and BOOK_OF_MOON in {c.code for c in observation.graveyards[0]} \
                    and any(a.kind == "normal_summon" for a in actions):
                own_monsters = [c for c in observation.field if c.zone == "monster"]
                assert len(own_monsters) == 1
                assert own_monsters[0].code == MYSTICAL_ELF
                assert own_monsters[0].position == "facedown"
                assert any(c.code == CALL_OF_THE_HAUNTED and c.zone == "spell_trap"
                           and c.position == "faceup" for c in observation.field)
                assert MYSTICAL_ELF not in {c.code for c in observation.graveyards[0]}
                other = env.engine.probe.observation(1)
                hidden = next(c for c in other.field if c.zone == "monster")
                assert hidden.code is None and hidden.position == "facedown"
                assert (0, "monster", hidden.sequence, MYSTICAL_ELF) in {
                    (c.controller, c.zone, c.sequence, c.code)
                    for c in other.known_opponent_field_cards}
                loaded = env.engine.probe.loaded_script_sha256
                assert f"official/c{CALL_OF_THE_HAUNTED}.lua" in loaded
                assert f"official/c{BOOK_OF_MOON}.lua" in loaded
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
    pytest.fail("Call of the Haunted / Book of Moon line did not complete")
