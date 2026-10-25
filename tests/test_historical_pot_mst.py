"""Destroying an activated Pot of Greed does not negate its draw."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

POT_OF_GREED = 55144522
MYSTICAL_SPACE_TYPHOON = 5318639
SOLEMN_JUDGMENT = 41420027


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_mst_chained_to_pot_destroys_card_without_negating_draw(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (POT_OF_GREED, MYSTICAL_SPACE_TYPHOON):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    pot_deck = tmp_path / "pot.ydk"
    pot_deck.write_text("#main\n" + "\n".join(map(str, (
        POT_OF_GREED, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    mst_deck = tmp_path / "mst.ydk"
    mst_deck.write_text("#main\n" + "\n".join(map(str, (
        MYSTICAL_SPACE_TYPHOON, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(pot_deck), str(mst_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        mst_set = pot_activated = mst_chained = pot_targeted = False
        before_hand = before_deck = None
        for _ in range(55):
            actions = env.legal_actions()
            action = None
            if observation.turn == 2 and observation.acting_player == 1 and not mst_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == MYSTICAL_SPACE_TYPHOON), None)
                mst_set |= action is not None
            if observation.turn == 3 and observation.acting_player == 0 and not pot_activated:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == POT_OF_GREED), action)
                if action is not None and action.kind == "activate":
                    before_hand = len(observation.hand)
                    before_deck = observation.deck_counts[0]
                    pot_activated = True
            if pot_activated and observation.acting_player == 1 and not mst_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == MYSTICAL_SPACE_TYPHOON),
                              action)
                mst_chained |= action is not None and action.kind == "chain"
            if mst_chained and not pot_targeted:
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("controller") == 0
                               and a.parameters.get("code") == POT_OF_GREED), action)
                pot_targeted |= action is not None and action.kind == "select_card"
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if pot_targeted and {POT_OF_GREED, MYSTICAL_SPACE_TYPHOON}.issubset(
                    {card.code for pile in observation.graveyards for card in pile}):
                assert mst_set and pot_activated and mst_chained
                assert observation.chain == ()
                own = env.engine.probe.observation(0)
                assert len(own.hand) == before_hand + 1
                assert own.deck_counts[0] == before_deck - 2
                assert not any(card.code == POT_OF_GREED for card in own.field)
                loaded = env.engine.probe.loaded_script_sha256
                assert f"official/c{POT_OF_GREED}.lua" in loaded
                assert f"official/c{MYSTICAL_SPACE_TYPHOON}.lua" in loaded
                return
    pytest.fail("MST/Pot chain did not resolve")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_solemn_negates_pot_activation_and_prevents_draw(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (POT_OF_GREED, SOLEMN_JUDGMENT):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    pot_deck = tmp_path / "pot.ydk"
    pot_deck.write_text("#main\n" + "\n".join(map(str, (
        POT_OF_GREED, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    solemn_deck = tmp_path / "solemn.ydk"
    solemn_deck.write_text("#main\n" + "\n".join(map(str, (
        SOLEMN_JUDGMENT, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(pot_deck), str(solemn_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        solemn_set = pot_activated = solemn_chained = False
        hand_before = deck_before = None
        for _ in range(55):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1 and not solemn_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SOLEMN_JUDGMENT), None)
                solemn_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not pot_activated:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == POT_OF_GREED), action)
                if action is not None and action.kind == "activate":
                    hand_before = len(obs.hand)
                    deck_before = obs.deck_counts[0]
                    pot_activated = True
            if pot_activated and obs.acting_player == 1 and not solemn_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SOLEMN_JUDGMENT), action)
                solemn_chained |= action is not None and action.kind == "chain"
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if solemn_chained and {POT_OF_GREED, SOLEMN_JUDGMENT}.issubset(
                    {card.code for pile in obs.graveyards for card in pile}):
                own = env.engine.probe.observation(0)
                assert own.life_points == (8000, 4000)
                assert len(own.hand) == hand_before - 1
                assert own.deck_counts[0] == deck_before
                assert own.chain == ()
                assert not any(c.code == POT_OF_GREED for c in own.field)
                loaded = env.engine.probe.loaded_script_sha256
                assert f"official/c{POT_OF_GREED}.lua" in loaded
                assert f"official/c{SOLEMN_JUDGMENT}.lua" in loaded
                return
    pytest.fail("Solemn Judgment did not negate Pot of Greed")
