"""Chaos Turbo's Thunder Dragon and Dekoichi supply Sorcerer's Summon cost."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

THUNDER = 504700054
SORCERER = 9596126
DEKOICHI = 87621407
GRACEFUL = 79571449


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_thunder_and_dekoichi_enable_chaos_sorcerer(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{THUNDER}.lua", f"official/c{SORCERER}.lua",
               f"official/c{DEKOICHI}.lua", f"official/c{GRACEFUL}.lua"}
    for relative in scripts:
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    deck = tmp_path / "chaos_turbo_line.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        *([THUNDER] * 3), *([SORCERER] * 3), *([DEKOICHI] * 3),
        GRACEFUL, *VANILLA_DECK[10:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=90,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {THUNDER, SORCERER, DEKOICHI, GRACEFUL} <= {
            c.code for c in obs.hand}
        dragon_used = searched = graceful_used = discarded = False
        summoned = paid_light = paid_dark = opponent_summoned = False
        effect_used = targeted = checked = False
        target_code = None
        agents = (RandomAgent(90), RandomAgent(91))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / "thunder_chaos_sorcerer.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not dragon_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == THUNDER), None)
                    dragon_used |= action is not None
                elif not searched and any(a.kind == "select_cards" for a in actions):
                    action = next((a for a in actions if a.kind == "select_cards"
                                   and len(a.parameters.get("cards", ())) == 2), None)
                    searched |= action is not None
                elif searched and not graceful_used:
                    assert {c.code for c in obs.graveyards[0]} == {THUNDER}
                    assert not any(a.kind == "special_summon"
                                   and a.parameters.get("code") == SORCERER
                                   for a in actions)
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    graceful_used |= action is not None
                elif graceful_used and not discarded \
                        and any(a.kind == "select_cards" for a in actions):
                    action = next((a for a in actions if a.kind == "select_cards"
                                   and len(a.parameters.get("cards", ())) == 2
                                   and DEKOICHI in {c["code"] for c in a.parameters["cards"]}
                                   and all(c["code"] not in (THUNDER, SORCERER)
                                           for c in a.parameters["cards"])), None)
                    discarded |= action is not None
                elif discarded and not summoned:
                    assert {THUNDER, DEKOICHI} <= {
                        c.code for c in obs.graveyards[0]}
                    action = next((a for a in actions if a.kind == "special_summon"
                                   and a.parameters.get("code") == SORCERER), None)
                    summoned |= action is not None
                elif summoned and not paid_light and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == THUNDER
                                   and a.parameters.get("location") == 16), None)
                    paid_light |= action is not None
                elif paid_light and not paid_dark and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == DEKOICHI
                                   and a.parameters.get("location") == 16), None)
                    paid_dark |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and paid_dark \
                    and not opponent_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    target_code = action.parameters["code"]
                    opponent_summoned = True
            if obs.turn == 3 and obs.acting_player == 0 and opponent_summoned \
                    and not effect_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SORCERER), None)
                effect_used |= action is not None
            if effect_used and not targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == target_code
                               and a.parameters.get("controller") == 1), None)
                targeted |= action is not None
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if targeted and not checked and any(c.code == target_code
                                                  for c in obs.banished[1]):
                assert {THUNDER, DEKOICHI} <= {c.code for c in obs.banished[0]}
                assert any(c.code == SORCERER and c.controller == 0 for c in obs.field)
                assert not any(c.code == target_code for c in obs.field)
                assert obs.life_points == (8000, 8000)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail("Thunder Dragon / Chaos Sorcerer duel did not finish")
