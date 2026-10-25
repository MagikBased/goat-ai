"""Dekoichi counts Bokoichi by current control, including after Snatch Steal."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

DEKOICHI = 87621407
BOKOICHI = 8715625
SNATCH = 45986603


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("steal_bokoichi", [False, True])
def test_dekoichi_counts_stolen_bokoichi_at_resolution(tmp_path, steal_bokoichi):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{DEKOICHI}.lua", f"official/c{SNATCH}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    dekoichi_deck = tmp_path / "dekoichi_snatch.ydk"
    dekoichi_deck.write_text("#main\n" + "\n".join(map(str, (
        *([DEKOICHI] * 3), SNATCH, *VANILLA_DECK[4:])))
        + "\n#extra\n!side\n")
    bokoichi_deck = tmp_path / "bokoichi.ydk"
    bokoichi_deck.write_text("#main\n" + "\n".join(map(str, (
        *([BOKOICHI] * 3), *VANILLA_DECK[3:])))
        + "\n#extra\n!side\n")

    with GoatEnvironment(str(dekoichi_deck), str(bokoichi_deck), seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {DEKOICHI, SNATCH} <= {card.code for card in obs.hand}
        assert BOKOICHI in {card.code for card in env.engine.probe.observation(1).hand}
        set_dekoichi = summon_bokoichi = activate_snatch = target_bokoichi = False
        stolen = flipped = checked = False
        before_deck = before_hand = None
        agents = (RandomAgent(15), RandomAgent(16))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"dekoichi_snatch_bokoichi_{steal_bokoichi}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not set_dekoichi:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == DEKOICHI), None)
                set_dekoichi |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not summon_bokoichi:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == BOKOICHI), None)
                summon_bokoichi |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and steal_bokoichi \
                    and not activate_snatch:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SNATCH), None)
                activate_snatch |= action is not None
            if activate_snatch and not target_bokoichi \
                    and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("code") == BOKOICHI), None)
                target_bokoichi |= action is not None
            if target_bokoichi and any(card.code == BOKOICHI and card.controller == 0
                                       for card in obs.field):
                stolen = True
            if obs.turn == 3 and obs.acting_player == 0 and not flipped \
                    and (not steal_bokoichi or stolen):
                action = next((a for a in actions if a.kind == "flip_summon"
                               and a.parameters.get("code") == DEKOICHI), action)
                if action is not None and action.kind == "flip_summon":
                    before_deck = obs.deck_counts[0]
                    before_hand = len(obs.hand)
                    flipped = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            expected_draw = 2 if steal_bokoichi else 1
            if flipped and not checked and not obs.chain \
                    and obs.deck_counts[0] == before_deck - expected_draw:
                assert len(obs.hand) == before_hand + expected_draw
                assert any(card.code == DEKOICHI and card.position == "faceup"
                           for card in obs.field)
                assert any(card.code == BOKOICHI and card.controller == (
                    0 if steal_bokoichi else 1) for card in obs.field)
                assert obs.life_points == (8000, 8000)
                assert f"official/c{DEKOICHI}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                if steal_bokoichi:
                    assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                    assert target_bokoichi and stolen
                checked = True
    pytest.fail("Dekoichi / stolen Bokoichi duel did not finish")
