"""Historical optional-trigger timing, exercised in the pinned native core."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.decks import read_ydk
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.ocgcore_probe import LOCATION_DECK
from goat_ai.environments import GoatEnvironment

CANNON_SOLDIER = 11384280
PETEN = 504700084  # GOAT variant of Peten the Dark Clown


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_peten_tributed_for_cannon_soldier_misses_timing(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/goat/c{PETEN}.lua").is_file():
        pytest.skip("full card script checkout not installed")
    decks = Path(__file__).resolve().parent.parent / "examples/decks"
    cards = list(read_ydk(decks / "cannon_probe.ydk").main)
    cards[1:4] = [PETEN] * 3
    deck = tmp_path / "peten.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, cards)) + "\n")

    with GoatEnvironment(str(deck), str(decks / "vanilla_probe.ydk"), seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        cannon_summoned = peten_summoned = cannon_activated = peten_tributed = False
        for _ in range(45):
            choices = env.legal_actions()

            def choice(kind, code=None, actions=choices):
                return next((action for action in actions if action.kind == kind
                             and (code is None or action.parameters.get("code") == code)), None)

            if peten_tributed and observation.life_points[1] == 7500:
                assert cannon_summoned and peten_summoned and cannon_activated
                assert any(card.code == PETEN for card in observation.graveyards[0])
                assert not any(card.code == PETEN for card in observation.banished[0])
                assert not any(action.kind in ("yes", "chain")
                               and action.parameters.get("code") == PETEN
                               for action in choices)
                assert sum(card.code == PETEN for card in env.engine.probe._query_location(
                    0, LOCATION_DECK) if card is not None) == 2  # test-only private deck check
                assert "goat/c504700084.lua" in env.engine.probe.loaded_script_sha256
                return

            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not cannon_summoned:
                action = choice("normal_summon", CANNON_SOLDIER)
                cannon_summoned |= action is not None
            if observation.turn == 3 and observation.acting_player == 0 and cannon_summoned:
                if not peten_summoned:
                    action = choice("normal_summon", PETEN)
                    peten_summoned |= action is not None
                if peten_summoned and not cannon_activated and action is None:
                    action = choice("chain", CANNON_SOLDIER)
                    cannon_activated |= action is not None
                if cannon_activated and not peten_tributed and action is None:
                    action = choice("select_card", PETEN)
                    peten_tributed |= action is not None
            if action is None:
                action = choice("end_phase") or choice("pass") or choices[0]
            observation = env.step(action)
        pytest.fail("Peten missed-timing branch did not resolve within 45 decisions")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_peten_destroyed_by_battle_can_trigger_and_summon_copy(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/goat/c{PETEN}.lua").is_file():
        pytest.skip("full card script checkout not installed")
    decks = Path(__file__).resolve().parent.parent / "examples/decks"
    cards = list(read_ydk(decks / "vanilla_probe.ydk").main)
    cards[:3] = [PETEN] * 3
    deck = tmp_path / "peten.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, cards)) + "\n")

    with GoatEnvironment(str(deck), str(decks / "vanilla_probe.ydk"), seed=0,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        peten_set = attacker_summoned = attacked = trigger_accepted = False
        for _ in range(60):
            choices = env.legal_actions()

            def choice(kind, code=None, actions=choices):
                return next((action for action in actions if action.kind == kind
                             and (code is None or action.parameters.get("code") == code)), None)

            if trigger_accepted and any(card.code == PETEN for card in observation.field):
                assert peten_set and attacker_summoned and attacked
                assert any(card.code == PETEN for card in observation.banished[0])
                return

            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not peten_set:
                action = choice("set_monster", PETEN)
                peten_set |= action is not None
            if observation.turn == 2 and observation.acting_player == 1:
                if not attacker_summoned:
                    action = choice("normal_summon")
                    attacker_summoned |= action is not None
                if attacker_summoned and not attacked and action is None:
                    action = choice("battle_phase") or choice("attack")
                    attacked |= action is not None and action.kind == "attack"
                if attacked and action is None:
                    action = choice("select_card") or choice("pass")
            trigger = choice("yes", PETEN)
            if trigger is not None:
                assert observation.phase == "damage_step"
                assert any(card.code == PETEN for card in observation.graveyards[0])
                action = trigger
                trigger_accepted = True
            if trigger_accepted and action is None:
                action = choice("select_card", PETEN) or choice("place") or choice(
                    "select_position")
            if action is None:
                action = choice("end_phase") or choice("pass") or choices[0]
            observation = env.step(action)
        pytest.fail("Peten battle-trigger branch did not resolve within 60 decisions")
