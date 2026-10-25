"""Dust Tornado's optional Set and Quick-Play activation timing."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.observations import TargetSlotView

DUST_TORNADO = 60082869
BOOK_OF_MOON = 14087893
SAKURETSU_ARMOR = 56120475
MYSTICAL_SPACE_TYPHOON = 5318639
HEAVY_STORM = 19613556


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


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_book", [False, True])
def test_dust_targeted_book_still_allows_set_after_book_chains(tmp_path, chain_book):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (DUST_TORNADO, BOOK_OF_MOON):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    dust = tmp_path / "dust_book.ydk"
    dust.write_text("#main\n" + "\n".join(map(str, (
        *([DUST_TORNADO] * 3), *([BOOK_OF_MOON] * 3),
        *VANILLA_DECK[6:]))) + "\n#extra\n!side\n")
    book = tmp_path / "book.ydk"
    book.write_text("#main\n" + "\n".join(map(str, (
        *([BOOK_OF_MOON] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(dust), str(book), seed=556,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        dust_set = book_set = monster_summoned = dust_used = dust_targeted = False
        book_chained = book_targeted = set_offered = targets_seen = False
        dust_target_sequence = None
        for _ in range(85):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not dust_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == DUST_TORNADO), None)
                dust_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not monster_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    monster_summoned |= action is not None
                if action is None and not book_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOOK_OF_MOON), None)
                    book_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and book_set \
                    and not dust_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == DUST_TORNADO), None)
                dust_used |= action is not None
            if dust_used and not dust_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 8), None)
                if action is not None:
                    assert "code" not in action.parameters
                    dust_target_sequence = action.parameters["sequence"]
                    dust_targeted = True
            if dust_targeted and obs.acting_player == 1 and not book_chained \
                    and chain_book:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK_OF_MOON), None)
                book_chained |= action is not None
            if book_chained and not book_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 4), None)
                book_targeted |= action is not None
            if book_targeted and obs.acting_player == 0 and len(obs.chain) == 2:
                other_view = env.engine.probe.observation(1)
                assert other_view.chain == obs.chain
                opponent_monster = next(c for c in obs.field if c.controller == 1
                                        and c.zone == "monster")
                assert obs.chain[0].targets == (TargetSlotView(
                    1, "spell_trap", dust_target_sequence),)
                assert obs.chain[1].targets == (TargetSlotView(
                    1, "monster", opponent_monster.sequence),)
                targets_seen = True
            if dust_targeted and actions[0].kind == "no":
                assert [a.kind for a in actions] == ["no", "yes"]
                set_offered = True
                action = next(a for a in actions if a.kind == "no")
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if set_offered and DUST_TORNADO in {c.code for c in obs.graveyards[0]}:
                assert book_chained == chain_book
                assert targets_seen == chain_book
                assert BOOK_OF_MOON in {c.code for c in obs.graveyards[1]}
                assert obs.chain == ()
                monster = next(c for c in obs.field if c.controller == 1
                               and c.zone == "monster")
                assert (monster.position == "facedown") == chain_book
                assert {f"official/c{code}.lua" for code in (
                    DUST_TORNADO, BOOK_OF_MOON)}.issubset(
                        env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Dust Tornado / Book chain did not reach the optional Set")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_dust_sets_book_in_heavy_storm_chain_then_storm_destroys_book(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (DUST_TORNADO, BOOK_OF_MOON, HEAVY_STORM):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    storm = tmp_path / "storm.ydk"
    storm.write_text("#main\n" + "\n".join(map(str, (
        HEAVY_STORM, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    dust = tmp_path / "dust.ydk"
    dust.write_text("#main\n" + "\n".join(map(str, (
        *([DUST_TORNADO] * 3), *([BOOK_OF_MOON] * 3),
        *VANILLA_DECK[6:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(storm), str(dust), seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        dust_set = storm_used = dust_chained = target_selected = False
        accepted_set = book_selected = False
        for _ in range(55):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1 and not dust_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == DUST_TORNADO), None)
                dust_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and dust_set \
                    and not storm_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == HEAVY_STORM), None)
                storm_used |= action is not None
            if storm_used and obs.acting_player == 1 and not dust_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == DUST_TORNADO), None)
                if action is not None:
                    assert [link.card_code for link in obs.chain] == [HEAVY_STORM]
                    dust_chained = True
            if dust_chained and not target_selected and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == HEAVY_STORM and a.parameters.get("controller") == 0), None)
                target_selected |= action is not None
            if target_selected and not accepted_set and actions[0].kind == "no":
                assert [a.kind for a in actions] == ["no", "yes"]
                action = next(a for a in actions if a.kind == "yes")
                accepted_set = True
            if accepted_set and not book_selected and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == BOOK_OF_MOON and a.parameters.get("controller") == 1),
                              None)
                book_selected |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if book_selected and {DUST_TORNADO, BOOK_OF_MOON}.issubset(
                    {c.code for c in obs.graveyards[1]}):
                assert target_selected and accepted_set
                assert HEAVY_STORM in {c.code for c in obs.graveyards[0]}
                assert obs.chain == ()
                assert not any(c.zone == "spell_trap" for c in obs.field)
                assert BOOK_OF_MOON not in {
                    c.code for c in env.engine.probe.observation(1).hand}
                assert obs.life_points == (8000, 8000)
                assert {f"official/c{code}.lua" for code in (
                    DUST_TORNADO, BOOK_OF_MOON, HEAVY_STORM)}.issubset(
                        env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Dust did not Set Book before Heavy Storm resolved")
