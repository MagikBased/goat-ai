"""Magician of Faith recovers a Spell even if Book sets it during its Flip Effect."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

POT_OF_GREED = 55144522
MAGICIAN_OF_FAITH = 31560081
BOOK_OF_MOON = 14087893
GEMINI_ELF = 69140098


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("book_response", [False, True])
def test_magician_of_faith_returns_pot_with_or_without_book_response(
        tmp_path, book_response):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    required_scripts = (POT_OF_GREED, MAGICIAN_OF_FAITH)
    if book_response:
        required_scripts += (BOOK_OF_MOON,)
    for code in required_scripts:
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    deck = tmp_path / "mof.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        POT_OF_GREED, MAGICIAN_OF_FAITH, *VANILLA_DECK[2:])))
                    + "\n#extra\n!side\n")
    opponent = "examples/decks/vanilla_probe.ydk"
    if book_response:
        response_deck = tmp_path / "book_response.ydk"
        response_deck.write_text("#main\n" + "\n".join(map(str, (
            BOOK_OF_MOON, BOOK_OF_MOON, BOOK_OF_MOON,
            *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
        opponent = str(response_deck)

    with GoatEnvironment(str(deck), opponent, seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        pot_used = mof_set = mof_flipped = pot_targeted = False
        book_set = book_used = False
        for _ in range(55):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0:
                if not pot_used:
                    option = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == POT_OF_GREED), None)
                    if option is not None:
                        action = option
                        pot_used = True
                if pot_used and not mof_set and action is None:
                    option = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == MAGICIAN_OF_FAITH), None)
                    if option is not None:
                        action = option
                        mof_set = True
            if book_response and observation.turn == 2 and observation.acting_player == 1 \
                    and not book_set:
                option = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == BOOK_OF_MOON), None)
                if option is not None:
                    action = option
                    book_set = True
            if observation.turn == 3 and observation.acting_player == 0:
                if mof_set and not mof_flipped:
                    option = next((a for a in actions if a.kind == "flip_summon"
                                   and a.parameters.get("code") == MAGICIAN_OF_FAITH), None)
                    if option is not None:
                        action = option
                        mof_flipped = True
                if mof_flipped and not pot_targeted and actions[0].kind == "select_card":
                    assert observation.chain[0].card_code == MAGICIAN_OF_FAITH
                    assert POT_OF_GREED in {c.code for c in observation.graveyards[0]}
                    action = next((a for a in actions if a.parameters.get("code")
                                   == POT_OF_GREED and a.parameters.get("location") == 16),
                                  None)
                    pot_targeted = action is not None
            if book_response and pot_targeted and observation.turn == 3 \
                    and observation.acting_player == 1:
                if not book_used:
                    option = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == BOOK_OF_MOON), None)
                    if option is not None:
                        action = option
                        book_used = True
                if book_used and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == MAGICIAN_OF_FAITH
                                   and a.parameters.get("controller") == 0), action)
            if pot_targeted and POT_OF_GREED in {c.code for c in observation.hand} \
                    and any(a.kind == "normal_summon" for a in actions):
                assert POT_OF_GREED not in {c.code for c in observation.graveyards[0]}
                assert any(a.kind == "activate" and a.parameters.get("code")
                           == POT_OF_GREED for a in actions)
                own_mof = next(c for c in observation.field
                               if c.zone == "monster" and c.controller == 0)
                other = env.engine.probe.observation(1)
                assert any(reveal.recipient == 1 and
                           [c.code for c in reveal.cards] == [POT_OF_GREED]
                           for reveal in other.private_reveals)
                if book_response:
                    assert book_used
                    assert own_mof.position == "facedown"
                    hidden = next(c for c in other.field if c.zone == "monster")
                    assert hidden.code is None and hidden.position == "facedown"
                    assert (0, "monster", hidden.sequence, MAGICIAN_OF_FAITH) in {
                        (c.controller, c.zone, c.sequence, c.code)
                        for c in other.known_opponent_field_cards}
                    assert BOOK_OF_MOON in {c.code for c in observation.graveyards[1]}
                else:
                    assert own_mof.position == "faceup"
                loaded = env.engine.probe.loaded_script_sha256
                assert f"official/c{MAGICIAN_OF_FAITH}.lua" in loaded
                if book_response:
                    assert f"official/c{BOOK_OF_MOON}.lua" in loaded
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
    pytest.fail("Magician of Faith did not return Pot of Greed")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_magician_of_faith_recovers_pot_then_book_after_book_resets_it(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (POT_OF_GREED, MAGICIAN_OF_FAITH, BOOK_OF_MOON):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    deck = tmp_path / "mof_book.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        POT_OF_GREED, *([MAGICIAN_OF_FAITH] * 3), *([BOOK_OF_MOON] * 3),
        *VANILLA_DECK[7:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {POT_OF_GREED, MAGICIAN_OF_FAITH, BOOK_OF_MOON}.issubset(
            c.code for c in obs.hand)
        pot_used = mof_set = first_flip = first_targeted = False
        book_used = book_targeted = second_flip = second_targeted = False
        for _ in range(100):
            actions = env.legal_actions()
            action = None
            if obs.acting_player == 0 and obs.turn == 1:
                if not pot_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == POT_OF_GREED), None)
                    pot_used |= action is not None
                if pot_used and not mof_set and action is None:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == MAGICIAN_OF_FAITH), None)
                    mof_set |= action is not None
            if obs.acting_player == 0 and obs.turn == 3 and mof_set:
                if not first_flip:
                    action = next((a for a in actions if a.kind == "flip_summon"
                                   and a.parameters.get("code") == MAGICIAN_OF_FAITH), None)
                    first_flip |= action is not None
                if first_flip and not first_targeted and actions[0].kind == "select_card" \
                        and action is None:
                    action = next((a for a in actions if a.parameters.get("code")
                                   == POT_OF_GREED and a.parameters.get("location") == 16),
                                  None)
                    first_targeted |= action is not None
                if first_targeted and POT_OF_GREED in {c.code for c in obs.hand} \
                        and not book_used and action is None:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == BOOK_OF_MOON), None)
                    book_used |= action is not None
                if book_used and not book_targeted and actions[0].kind == "select_card" \
                        and action is None:
                    action = next((a for a in actions if a.parameters.get("code")
                                   == MAGICIAN_OF_FAITH and a.parameters.get("controller")
                                   == 0), None)
                    book_targeted |= action is not None
            if book_targeted and obs.turn == 3 \
                    and BOOK_OF_MOON in {c.code for c in obs.graveyards[0]}:
                own_view = env.engine.probe.observation(0)
                own_mof = next(c for c in own_view.field if c.controller == 0
                               and c.zone == "monster")
                other = env.engine.probe.observation(1)
                hidden = next(c for c in other.field if c.controller == 0
                              and c.zone == "monster")
                assert own_mof.code == MAGICIAN_OF_FAITH and own_mof.position == "facedown"
                assert hidden.code is None and hidden.position == "facedown"
                if obs.acting_player == 0:
                    assert not any(a.kind == "flip_summon" and a.parameters.get("code")
                                   == MAGICIAN_OF_FAITH for a in actions)
            if obs.acting_player == 0 and obs.turn == 5 and book_targeted:
                if not second_flip:
                    action = next((a for a in actions if a.kind == "flip_summon"
                                   and a.parameters.get("code") == MAGICIAN_OF_FAITH), None)
                    second_flip |= action is not None
                if second_flip and not second_targeted and actions[0].kind == "select_card" \
                        and action is None:
                    assert BOOK_OF_MOON in {c.code for c in obs.graveyards[0]}
                    action = next((a for a in actions if a.parameters.get("code")
                                   == BOOK_OF_MOON and a.parameters.get("location") == 16),
                                  None)
                    second_targeted |= action is not None
            if second_targeted and BOOK_OF_MOON not in {
                    c.code for c in obs.graveyards[0]}:
                own_view = env.engine.probe.observation(0)
                assert BOOK_OF_MOON in {c.code for c in own_view.hand}
                assert POT_OF_GREED in {c.code for c in own_view.hand}
                other = env.engine.probe.observation(1)
                assert [[c.code for c in reveal.cards] for reveal in
                        other.private_reveals] == [[POT_OF_GREED], [BOOK_OF_MOON]]
                assert not own_view.private_reveals
                loaded = env.engine.probe.loaded_script_sha256
                assert all(f"official/c{code}.lua" in loaded for code in (
                    POT_OF_GREED, MAGICIAN_OF_FAITH, BOOK_OF_MOON))
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
    pytest.fail("Magician of Faith did not recover both Spells across two flips")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_magician_of_faith_battle_flip_recovers_pot_before_destruction(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (POT_OF_GREED, MAGICIAN_OF_FAITH):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    deck = tmp_path / "mof_battle.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        POT_OF_GREED, *([MAGICIAN_OF_FAITH] * 3), *VANILLA_DECK[4:])))
                    + "\n#extra\n!side\n")
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=5,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {POT_OF_GREED, MAGICIAN_OF_FAITH}.issubset(c.code for c in obs.hand)
        assert GEMINI_ELF in {c.code for c in env.engine.probe.observation(1).hand}
        pot_used = mof_set = elf_summoned = battle = attacked = targeted = False
        pot_selected = False
        for _ in range(70):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not pot_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == POT_OF_GREED), None)
                    pot_used |= action is not None
                elif not mof_set:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == MAGICIAN_OF_FAITH), None)
                    mof_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not elf_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == GEMINI_ELF), None)
                    elf_summoned |= action is not None
                elif obs.phase == "main1" and not battle:
                    action = next((a for a in actions if a.kind == "battle_phase"), None)
                    battle |= action is not None
                elif obs.phase == "battle_start" and not attacked:
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == GEMINI_ELF), None)
                    attacked |= action is not None
            if attacked and not targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 0
                               and a.parameters.get("location") == 4
                               and "code" not in a.parameters), None)
                targeted |= action is not None
            if targeted and not pot_selected and actions[0].kind == "select_card" \
                    and obs.acting_player == 0:
                assert obs.chain[0].card_code == MAGICIAN_OF_FAITH
                action = next((a for a in actions if a.parameters.get("code")
                               == POT_OF_GREED and a.parameters.get("location") == 16),
                              None)
                pot_selected |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if pot_selected and MAGICIAN_OF_FAITH in {
                    c.code for c in obs.graveyards[0]}:
                owner = env.engine.probe.observation(0)
                assert POT_OF_GREED in {c.code for c in owner.hand}
                assert POT_OF_GREED not in {c.code for c in owner.graveyards[0]}
                assert obs.life_points == (8000, 8000)
                assert any(c.code == GEMINI_ELF and c.controller == 1
                           for c in obs.field)
                assert not any(c.controller == 0 and c.zone == "monster"
                               for c in obs.field)
                assert [[c.code for c in reveal.cards] for reveal in
                        env.engine.probe.observation(1).private_reveals] == [[POT_OF_GREED]]
                assert f"official/c{MAGICIAN_OF_FAITH}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("battle-flipped Magician of Faith did not recover Pot")
