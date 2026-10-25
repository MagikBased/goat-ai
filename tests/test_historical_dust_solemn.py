"""Solemn negates Dust Tornado before destruction and optional Set."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

DUST = 60082869
SOLEMN = 41420027
BOOK = 14087893
SAKURETSU = 56120475


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("negate", [False, True])
def test_solemn_stops_dust_destruction_and_optional_set(tmp_path, negate):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (DUST, SOLEMN, BOOK, SAKURETSU)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required official card script not installed")
    decks = []
    for name, first, seventh in (("dust", DUST, BOOK),
                                 ("solemn", SOLEMN, SAKURETSU)):
        cards = list(VANILLA_DECK)
        cards[0] = first
        for index in (1, 2, 6):
            cards[index] = seventh
        deck = tmp_path / f"{name}.ydk"
        deck.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
        decks.append(deck)

    with GoatEnvironment(*(str(deck) for deck in decks), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {DUST, BOOK} <= {card.code for card in obs.hand}
        assert {SOLEMN, SAKURETSU} <= {
            card.code for card in env.engine.probe.observation(1).hand}
        dust_set = solemn_set = armor_set = dust_used = target_chosen = False
        solemn_chained = set_offered = set_chosen = book_chosen = False
        for _ in range(85):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not dust_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == DUST), None)
                dust_set = action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not solemn_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == SOLEMN), None)
                    solemn_set = action is not None
                if solemn_set and not armor_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == SAKURETSU), None)
                    armor_set = action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not dust_used:
                assert dust_set and solemn_set and armor_set
                hidden = [card for card in obs.field if card.controller == 1
                          and card.zone == "spell_trap"]
                assert len(hidden) == 2 and all(card.code is None for card in hidden)
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == DUST), None)
                dust_used = action is not None
            if dust_used and not target_chosen and actions[0].kind == "select_card":
                targets = [a for a in actions if a.kind == "select_card"
                           and a.parameters.get("controller") == 1
                           and a.parameters.get("location") == 8]
                assert len(targets) == 2
                assert all("code" not in a.parameters for a in targets)
                owner = env.engine.probe.observation(1)
                armor = next(c for c in owner.field if c.code == SAKURETSU)
                action = next(a for a in targets if a.parameters["sequence"]
                              == armor.sequence)
                target_chosen = True
            if target_chosen and obs.acting_player == 1 and not solemn_chained:
                solemn = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SOLEMN), None)
                assert solemn is not None
                assert [link.card_code for link in obs.chain] == [DUST]
                if negate:
                    action = solemn
                    solemn_chained = True
            if dust_used and not negate and not set_chosen \
                    and any(a.kind == "yes" for a in actions):
                assert [a.kind for a in actions] == ["no", "yes"]
                assert SAKURETSU in {c.code for c in obs.graveyards[1]}
                action = next(a for a in actions if a.kind == "yes")
                set_offered = set_chosen = True
            if set_chosen and not book_chosen and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == BOOK), None)
                book_chosen = action is not None
            if negate and solemn_chained:
                assert not any(a.kind in ("yes", "no") for a in actions)
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if target_chosen and DUST in {c.code for c in obs.graveyards[0]} \
                    and not obs.chain and (negate or book_chosen):
                own = env.engine.probe.observation(0)
                owner = env.engine.probe.observation(1)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                if negate:
                    assert solemn_chained and not set_offered
                    assert own.life_points == (8000, 4000)
                    assert BOOK in {c.code for c in own.hand}
                    assert SAKURETSU not in {c.code for c in owner.graveyards[1]}
                    assert any(c.code == SAKURETSU and c.position == "facedown"
                               for c in owner.field)
                    assert any(c.controller == 1 and c.zone == "spell_trap"
                               and c.code is None for c in own.field)
                else:
                    assert not solemn_chained and set_offered and book_chosen
                    assert own.life_points == (8000, 8000)
                    assert SAKURETSU in {c.code for c in owner.graveyards[1]}
                    assert BOOK not in {c.code for c in own.hand}
                    assert any(c.code == BOOK and c.position == "facedown"
                               for c in own.field)
                    assert any(c.code == SOLEMN and c.position == "facedown"
                               for c in owner.field)
                return
    pytest.fail("Dust/Solemn response did not resolve")
