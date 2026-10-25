"""Solemn negates Book's activation before the target can turn face-down."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.observations import TargetSlotView

BOOK = 14087893
SOLEMN = 41420027


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("negate", [False, True])
def test_solemn_response_to_book_activation(tmp_path, negate):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (BOOK, SOLEMN)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required official card script not installed")
    book_deck = tmp_path / "book.ydk"
    book_deck.write_text("#main\n" + "\n".join(map(str, (
        BOOK, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    solemn_deck = tmp_path / "solemn.ydk"
    solemn_deck.write_text("#main\n" + "\n".join(map(str, (
        SOLEMN, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(book_deck), str(solemn_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert BOOK in {c.code for c in obs.hand}
        assert SOLEMN in {c.code for c in env.engine.probe.observation(1).hand}
        summoned = solemn_set = booked = targeted = solemn_chained = False
        monster_code = None
        for _ in range(75):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    summoned = True
                    monster_code = action.parameters["code"]
            if obs.turn == 2 and obs.acting_player == 1 and not solemn_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SOLEMN), None)
                solemn_set = action is not None
            if obs.turn == 3 and obs.acting_player == 0:
                if not booked:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == BOOK), None)
                    booked = action is not None
                if booked and not targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == monster_code and a.parameters.get("controller") == 0),
                                  None)
                    targeted = action is not None
            if targeted and obs.acting_player == 1 and obs.chain \
                    and obs.chain[-1].card_code == BOOK:
                monster = next(c for c in obs.field if c.code == monster_code
                               and c.zone == "monster")
                assert obs.chain[0].targets == (TargetSlotView(
                    0, "monster", monster.sequence),)
            if negate and targeted and obs.acting_player == 1 \
                    and not solemn_chained:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SOLEMN), None)
                if option is not None:
                    assert [link.card_code for link in obs.chain] == [BOOK]
                    action = option
                    solemn_chained = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if targeted and BOOK in {c.code for c in obs.graveyards[0]} \
                    and obs.chain == () and obs.turn == 3:
                own = env.engine.probe.observation(0)
                monster = next(c for c in own.field if c.controller == 0
                               and c.zone == "monster")
                assert monster.code == monster_code
                other = env.engine.probe.observation(1)
                opposing_monster = next(c for c in other.field if c.controller == 0
                                        and c.zone == "monster")
                if negate:
                    assert solemn_chained
                    assert own.life_points == (8000, 4000)
                    assert monster.position == opposing_monster.position == "faceup"
                    assert opposing_monster.code == monster_code
                    assert not other.known_opponent_field_cards
                    assert SOLEMN in {c.code for c in own.graveyards[1]}
                    assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                else:
                    assert not solemn_chained
                    assert own.life_points == (8000, 8000)
                    assert monster.position == opposing_monster.position == "facedown"
                    assert opposing_monster.code is None
                    assert (0, "monster", opposing_monster.sequence, monster_code) in {
                        (c.controller, c.zone, c.sequence, c.code)
                        for c in other.known_opponent_field_cards}
                    assert SOLEMN not in {c.code for c in own.graveyards[1]}
                return
    pytest.fail("Book / Solemn chain did not resolve")
