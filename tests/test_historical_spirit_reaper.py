"""GOAT Spirit Reaper battle survival and targeting self-destruction."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

SPIRIT_REAPER = 504700038
BOOK_OF_MOON = 14087893
ENEMY_CONTROLLER = 98045062
MYSTICAL_SPACE_TYPHOON = 5318639
SNATCH_STEAL = 45986603


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("response", [BOOK_OF_MOON, ENEMY_CONTROLLER])
def test_reaper_survives_battle_then_targeted_response(tmp_path, response):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/goat/c{SPIRIT_REAPER}.lua").is_file():
        pytest.skip("GOAT Spirit Reaper script not installed")
    if not (root / f"scripts/official/c{response}.lua").is_file():
        pytest.skip(f"response script for {response} not installed")
    own_deck = tmp_path / "reaper.ydk"
    own_deck.write_text("#main\n" + "\n".join(map(str, (
        SPIRIT_REAPER, SPIRIT_REAPER, SPIRIT_REAPER,
        *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    other_deck = tmp_path / "response.ydk"
    other_deck.write_text("#main\n" + "\n".join(map(str, (
        response, response, response,
        *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own_deck), str(other_deck), seed=11,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        reaper_set = attacker_summoned = attacked = response_used = False
        target_chosen = battle_survived = False
        for _ in range(58):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 \
                    and not reaper_set:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == SPIRIT_REAPER), None)
                reaper_set = action is not None
            if observation.turn == 2 and observation.acting_player == 1:
                if not attacker_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    attacker_summoned = action is not None
                if attacker_summoned and not attacked and action is None:
                    action = next((a for a in actions if a.kind in (
                        "battle_phase", "attack")), None)
                    attacked |= action is not None and action.kind == "attack"
                if attacked and observation.phase == "battle_step" and action is None:
                    action = next((a for a in actions if a.kind == "main2"), None)
                if attacked and observation.phase == "main2" and not response_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == response), None)
                    if action is not None:
                        reaper = next(c for c in observation.field
                                      if c.code == SPIRIT_REAPER)
                        assert reaper.position == "faceup"
                        assert reaper.orientation == "defense"
                        assert SPIRIT_REAPER not in {
                            c.code for c in observation.graveyards[0]}
                        assert observation.life_points == (8000, 8000)
                        battle_survived = True
                        response_used = True
            if response_used and actions[0].kind == "select_option":
                assert response == ENEMY_CONTROLLER and len(actions) == 2
                action = actions[0]  # Battle-position mode; no Tribute cost.
            if response_used and not target_chosen and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == SPIRIT_REAPER and a.parameters.get("controller") == 0),
                              None)
                target_chosen = action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if target_chosen and response in {
                    c.code for c in observation.graveyards[1]}:
                own_view = env.engine.probe.observation(0)
                assert battle_survived
                if response == ENEMY_CONTROLLER:
                    assert SPIRIT_REAPER in {
                        c.code for c in own_view.graveyards[0]}
                    assert not any(c.code == SPIRIT_REAPER for c in own_view.field)
                else:
                    reaper = next(c for c in own_view.field
                                  if c.code == SPIRIT_REAPER)
                    assert reaper.position == "facedown"
                    assert SPIRIT_REAPER not in {
                        c.code for c in own_view.graveyards[0]}
                    opponent_view = env.engine.probe.observation(1)
                    hidden = next(c for c in opponent_view.field
                                  if c.zone == "monster" and c.controller == 0)
                    assert hidden.code is None and hidden.position == "facedown"
                    assert (0, "monster", hidden.sequence, SPIRIT_REAPER) in {
                        (c.controller, c.zone, c.sequence, c.code)
                        for c in opponent_view.known_opponent_field_cards}
                assert "goat/c504700038.lua" in env.engine.probe.loaded_script_sha256
                return
    pytest.fail("Spirit Reaper battle and targeting line did not resolve")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_mst", [False, True])
def test_goat_reaper_snatch_target_survives_only_if_mst_breaks_equip(tmp_path,
                                                                       chain_mst):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/goat/c{SPIRIT_REAPER}.lua").is_file():
        pytest.skip("GOAT Spirit Reaper script not installed")
    for code in (MYSTICAL_SPACE_TYPHOON, SNATCH_STEAL):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    own_deck = tmp_path / "reaper_mst.ydk"
    own_deck.write_text("#main\n" + "\n".join(map(str, (
        *([SPIRIT_REAPER] * 3), MYSTICAL_SPACE_TYPHOON,
        *VANILLA_DECK[4:]))) + "\n#extra\n!side\n")
    other_deck = tmp_path / "snatch.ydk"
    other_deck.write_text("#main\n" + "\n".join(map(str, (
        SNATCH_STEAL, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own_deck), str(other_deck), seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        summoned = mst_set = snatch_used = snatch_targeted = mst_used = False
        mst_targeted = False
        for _ in range(36):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0:
                if not summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == SPIRIT_REAPER), None)
                    summoned = action is not None
                if summoned and not mst_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == MYSTICAL_SPACE_TYPHOON),
                                  None)
                    mst_set = action is not None
            if observation.turn == 2 and observation.acting_player == 1 \
                    and mst_set and not snatch_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SNATCH_STEAL), None)
                snatch_used = action is not None
            if snatch_used and not snatch_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == SPIRIT_REAPER and a.parameters.get("controller") == 0),
                              None)
                snatch_targeted = action is not None
            if chain_mst and snatch_targeted and observation.acting_player == 0 \
                    and not mst_used:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == MYSTICAL_SPACE_TYPHOON),
                              action)
                mst_used = action is not None and action.kind == "chain"
            if mst_used and not mst_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == SNATCH_STEAL and a.parameters.get("controller") == 1),
                              None)
                mst_targeted = action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if snatch_targeted and SNATCH_STEAL in {
                    c.code for c in observation.graveyards[1]}:
                assert mst_used == mst_targeted == chain_mst
                reaper_on_field = any(c.code == SPIRIT_REAPER and c.controller == 0
                                      and c.position == "faceup"
                                      for c in observation.field)
                assert reaper_on_field == chain_mst
                assert (SPIRIT_REAPER in {c.code for c in observation.graveyards[0]}) \
                    != chain_mst
                assert (MYSTICAL_SPACE_TYPHOON in {
                    c.code for c in observation.graveyards[0]}) == chain_mst
                assert "goat/c504700038.lua" in env.engine.probe.loaded_script_sha256
                return
    pytest.fail("GOAT Spirit Reaper / Snatch Steal chain did not resolve")
