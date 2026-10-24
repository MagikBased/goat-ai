"""GOAT Scapegoat token and same-turn Summon restriction regressions."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

SCAPEGOAT = 504700123
CANNON_SOLDIER = 11384280
DMOC = 511001039
TOKEN_CODES = {73915052, 73915053, 73915054, 73915055}
OPPONENT = Path(__file__).resolve().parent.parent / "examples/decks/vanilla_probe.ydk"


@pytest.fixture
def scapegoat_deck(tmp_path):
    deck = tmp_path / "scapegoat.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (SCAPEGOAT, *VANILLA_DECK[1:]))) + "\n")
    return deck


def _native_root():
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/goat/c{SCAPEGOAT}.lua").is_file():
        pytest.skip("GOAT Scapegoat script not installed")
    return root


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_scapegoat_summons_four_tokens_but_still_allows_a_set(scapegoat_deck):
    root = _native_root()
    with GoatEnvironment(str(scapegoat_deck), str(OPPONENT), seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        activated = False
        for _ in range(40):
            choices = env.legal_actions()
            tokens = [card for card in observation.field if card.controller == 0
                      and card.code in TOKEN_CODES]
            if len(tokens) == 4 and observation.acting_player == 0 and any(
                action.kind == "set_monster" for action in choices
            ):
                assert activated
                assert {card.code for card in tokens} == TOKEN_CODES
                assert all(card.position == "faceup" and card.orientation == "defense"
                           for card in tokens)
                assert not any(action.kind in ("normal_summon", "special_summon")
                               for action in choices)
                assert "goat/c504700123.lua" in env.engine.probe.loaded_script_sha256
                return
            action = None
            if observation.acting_player == 0 and observation.phase == "main1" and not activated:
                action = next((item for item in choices if item.kind == "activate"
                               and item.parameters.get("code") == SCAPEGOAT), None)
                activated = action is not None
            if action is None:
                action = next((item for item in choices if item.kind == "pass"), None)
            if action is None:
                action = next((item for item in choices if item.kind == "place"), None)
            if action is None:
                action = next((item for item in choices if item.kind == "end_phase"), choices[0])
            observation = env.step(action)
        pytest.fail("Scapegoat did not produce four tokens and a post-resolution decision")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_scapegoat_cannot_activate_after_normal_summon(scapegoat_deck):
    root = _native_root()
    with GoatEnvironment(str(scapegoat_deck), str(OPPONENT), seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        normal_summoned = False
        checked_after_summon = False
        for _ in range(30):
            choices = env.legal_actions()
            if observation.turn > 1:
                assert normal_summoned and checked_after_summon
                return
            if normal_summoned:
                assert not any(item.kind in ("chain", "activate")
                               and item.parameters.get("code") == SCAPEGOAT
                               for item in choices)
                checked_after_summon = True
            action = None
            if observation.acting_player == 0 and observation.phase == "main1" and not normal_summoned:
                assert any(item.kind == "activate"
                           and item.parameters.get("code") == SCAPEGOAT for item in choices)
                action = next((item for item in choices if item.kind == "normal_summon"), None)
                normal_summoned = action is not None
            if action is None:
                action = next((item for item in choices if item.kind == "pass"), None)
            if action is None:
                action = next((item for item in choices if item.kind == "place"), None)
            if action is None:
                action = next((item for item in choices if item.kind == "end_phase"), choices[0])
            observation = env.step(action)
        pytest.fail("did not reach the turn after the Normal Summon")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_sheep_token_is_cannon_cost_but_not_tribute_summon_material(tmp_path):
    root = _native_root()
    deck = tmp_path / "scapegoat_cannon.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        CANNON_SOLDIER, SCAPEGOAT, DMOC, *VANILLA_DECK[3:]))) + "\n")
    with GoatEnvironment(str(deck), str(OPPONENT), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        goat_activated = cannon_summoned = ignition_activated = token_tributed = False
        checked_tribute_restriction = False
        token_code = None
        for _ in range(60):
            choices = env.legal_actions()
            if token_tributed:
                assert not any(card.code == token_code for zone in
                               (*observation.graveyards, *observation.banished)
                               for card in zone)
                assert not any(card.code == token_code for card in observation.field)
                if observation.life_points[1] == 7500:
                    assert checked_tribute_restriction
                    assert goat_activated and cannon_summoned and ignition_activated
                    return
            action = None
            if observation.acting_player == 0:
                if observation.turn == 1 and observation.phase == "main1" and not goat_activated:
                    action = next((item for item in choices if item.kind == "activate"
                                   and item.parameters.get("code") == SCAPEGOAT), None)
                    goat_activated |= action is not None
                if (action is None and observation.turn == 3
                        and observation.phase == "main1" and not cannon_summoned):
                    assert not any(item.kind == "normal_summon"
                                   and item.parameters.get("code") == DMOC for item in choices)
                    checked_tribute_restriction = True
                    action = next((item for item in choices if item.kind == "normal_summon"
                                   and item.parameters.get("code") == CANNON_SOLDIER), None)
                    cannon_summoned |= action is not None
                if action is None and cannon_summoned and not ignition_activated:
                    action = next((item for item in choices if item.kind == "chain"
                                   and item.parameters.get("code") == CANNON_SOLDIER), None)
                    ignition_activated |= action is not None
                if action is None and ignition_activated and not token_tributed:
                    action = next((item for item in choices if item.kind == "select_card"
                                   and item.parameters.get("code") in TOKEN_CODES), None)
                    if action is not None:
                        token_code = action.parameters["code"]
                        token_tributed = True
            if action is None:
                action = next((item for item in choices if item.kind == "place"), None)
            if action is None:
                action = next((item for item in choices if item.kind == "end_phase"), None)
            if action is None:
                action = next((item for item in choices if item.kind == "pass"), choices[0])
            observation = env.step(action)
        pytest.fail("Scapegoat/Cannon Soldier interaction did not resolve")
