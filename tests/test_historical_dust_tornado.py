"""Dust Tornado's optional Set and Quick-Play activation timing."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

DUST_TORNADO = 60082869
BOOK_OF_MOON = 14087893
SAKURETSU_ARMOR = 56120475
MYSTICAL_SPACE_TYPHOON = 5318639


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("set_book", [False, True])
def test_dust_tornado_optional_set_and_book_activation_timing(tmp_path, set_book):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (DUST_TORNADO, BOOK_OF_MOON, SAKURETSU_ARMOR):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    own_deck = tmp_path / "dust.ydk"
    own_deck.write_text("#main\n" + "\n".join(map(str, (
        *([DUST_TORNADO] * 3), *([BOOK_OF_MOON] * 3),
        *VANILLA_DECK[6:]))) + "\n#extra\n!side\n")
    other_deck = tmp_path / "sakuretsu.ydk"
    other_deck.write_text("#main\n" + "\n".join(map(str, (
        *([SAKURETSU_ARMOR] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own_deck), str(other_deck), seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        dust_set = armor_set = opponent_summoned = dust_used = False
        choice_made = book_chosen = checked_after_resolution = checked_same_turn = False
        for _ in range(55):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 \
                    and not dust_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == DUST_TORNADO), None)
                dust_set = action is not None
            if observation.turn == 2 and observation.acting_player == 1:
                if not armor_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == SAKURETSU_ARMOR), None)
                    armor_set = action is not None
                if armor_set and not opponent_summoned and action is None:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    opponent_summoned = action is not None
            if observation.turn == 3 and observation.acting_player == 0 \
                    and not dust_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == DUST_TORNADO), None)
                if action is not None:
                    assert armor_set and opponent_summoned
                    assert any(c.code is None and c.controller == 1
                               and c.zone == "spell_trap" for c in observation.field)
                    dust_used = True
            if dust_used and actions[0].kind == "select_card" and not choice_made:
                assert [a.parameters for a in actions] == [
                    {"controller": 1, "location": 8, "sequence": 0}]
                action = actions[0]
            if dust_used and actions[0].kind == "no" and not choice_made:
                assert [a.kind for a in actions] == ["no", "yes"]
                assert SAKURETSU_ARMOR in {c.code for c in observation.graveyards[1]}
                action = next(a for a in actions if a.kind == ("yes" if set_book else "no"))
                choice_made = True
            if set_book and choice_made and not book_chosen \
                    and actions[0].kind == "select_card":
                assert [a.parameters["code"] for a in actions] == [BOOK_OF_MOON]
                action = actions[0]
                book_chosen = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if choice_made and DUST_TORNADO in {
                    c.code for c in observation.graveyards[0]} and not checked_after_resolution:
                assert set_book == book_chosen
                own_book = [c for c in observation.field if c.zone == "spell_trap"
                            and c.controller == 0 and c.code == BOOK_OF_MOON]
                assert len(own_book) == int(set_book)
                assert (BOOK_OF_MOON in {c.code for c in observation.hand}) != set_book
                opponent_view = env.engine.probe.observation(1)
                if set_book:
                    hidden = next(c for c in opponent_view.field
                                  if c.zone == "spell_trap" and c.controller == 0)
                    assert hidden.code is None and hidden.position == "facedown"
                checked_after_resolution = True
                if not set_book:
                    assert "official/c60082869.lua" in env.engine.probe.loaded_script_sha256
                    return
            if checked_after_resolution and set_book and observation.turn == 3 \
                    and observation.acting_player == 0 \
                    and any(a.kind == "end_phase" for a in env.legal_actions()):
                assert not any(a.parameters.get("code") == BOOK_OF_MOON
                               and a.kind in ("activate", "chain")
                               for a in env.legal_actions())
                checked_same_turn = True
            if checked_after_resolution and set_book and observation.turn == 4 \
                    and observation.acting_player == 0:
                assert checked_same_turn
                assert any(a.kind == "chain" and a.parameters.get("code") == BOOK_OF_MOON
                           for a in env.legal_actions())
                assert "official/c60082869.lua" in env.engine.probe.loaded_script_sha256
                return
    pytest.fail("Dust Tornado did not reach its optional Set outcome")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_dust_tornado_cannot_set_when_mst_removes_its_target(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (DUST_TORNADO, BOOK_OF_MOON, MYSTICAL_SPACE_TYPHOON):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    own_deck = tmp_path / "dust.ydk"
    own_deck.write_text("#main\n" + "\n".join(map(str, (
        *([DUST_TORNADO] * 3), *([BOOK_OF_MOON] * 3),
        *VANILLA_DECK[6:]))) + "\n#extra\n!side\n")
    other_deck = tmp_path / "book_mst.ydk"
    other_deck.write_text("#main\n" + "\n".join(map(str, (
        *([BOOK_OF_MOON] * 3), MYSTICAL_SPACE_TYPHOON,
        *VANILLA_DECK[4:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own_deck), str(other_deck), seed=556,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        dust_set = book_set = mst_set = dust_used = mst_chained = False
        target_chosen = mst_target_chosen = False
        for _ in range(60):
            actions = env.legal_actions()
            assert not (mst_target_chosen and any(a.kind in ("yes", "no")
                                               for a in actions))
            action = None
            if observation.turn == 1 and observation.acting_player == 0 \
                    and not dust_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == DUST_TORNADO), None)
                dust_set = action is not None
            if observation.turn == 2 and observation.acting_player == 1:
                if not book_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOOK_OF_MOON), None)
                    book_set = action is not None
                if book_set and not mst_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == MYSTICAL_SPACE_TYPHOON),
                                  None)
                    mst_set = action is not None
            if observation.turn == 3 and observation.acting_player == 0 \
                    and mst_set and not dust_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == DUST_TORNADO), None)
                dust_used = action is not None
            if dust_used and not target_chosen and actions[0].kind == "select_card":
                assert [a.parameters for a in actions] == [
                    {"controller": 1, "location": 8, "sequence": 0},
                    {"controller": 1, "location": 8, "sequence": 1}]
                action = actions[0]  # Book of Moon, known only by its field slot.
                target_chosen = True
            if target_chosen and observation.acting_player == 1 and not mst_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == MYSTICAL_SPACE_TYPHOON),
                              action)
                mst_chained = action is not None and action.kind == "chain"
            if mst_chained and not mst_target_chosen \
                    and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == BOOK_OF_MOON and a.parameters.get("controller") == 1),
                              None)
                mst_target_chosen = action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if mst_target_chosen and DUST_TORNADO in {
                    c.code for c in observation.graveyards[0]}:
                assert {BOOK_OF_MOON, MYSTICAL_SPACE_TYPHOON}.issubset(
                    {c.code for c in observation.graveyards[1]})
                assert BOOK_OF_MOON in {c.code for c in observation.hand}
                assert not any(c.zone == "spell_trap" and c.controller == 0
                               for c in observation.field)
                assert "official/c60082869.lua" in env.engine.probe.loaded_script_sha256
                return
    pytest.fail("MST did not remove Dust Tornado's target before resolution")
