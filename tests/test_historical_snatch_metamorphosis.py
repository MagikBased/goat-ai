"""Snatch Steal permits Metamorphosis to Tribute a stolen Chaos Sorcerer."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

CHAOS_SORCERER = 9596126
GRACEFUL_CHARITY = 79571449
LIGHT = 62651957
DARK = 7359741
SNATCH = 45986603
METAMORPHOSIS = 46411259
RYU_SENSHI = 49868263


def _chaos_deck(path):
    lights = (15025844, LIGHT)
    darks = (49881766, DARK)
    filler = [code for code in VANILLA_DECK if code not in (*lights, *darks)]
    cards = (GRACEFUL_CHARITY, *(CHAOS_SORCERER,) * 3,
             *(code for code in lights for _ in range(3)),
             *(code for code in darks for _ in range(3)), *filler[:24])
    assert len(cards) == 40
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_stolen_sorcerer_is_metamorphosis_cost_for_ryu_senshi(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (
        CHAOS_SORCERER, GRACEFUL_CHARITY, SNATCH, METAMORPHOSIS, RYU_SENSHI)}
    if any(not (root / "scripts" / relative).is_file() for relative in scripts):
        pytest.skip("required card script not installed")
    stolen_deck = tmp_path / "snatch_meta.ydk"
    cards = (SNATCH, *(METAMORPHOSIS if code == 23771716 else code
                       for code in VANILLA_DECK[1:]))
    assert len(cards) == 40
    stolen_deck.write_text("#main\n" + "\n".join(map(str, cards))
                           + f"\n#extra\n{RYU_SENSHI}\n!side\n")

    with GoatEnvironment(_chaos_deck(tmp_path / "chaos.ydk"), str(stolen_deck), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL_CHARITY, CHAOS_SORCERER, LIGHT, DARK} <= {
            c.code for c in obs.hand}
        assert {SNATCH, METAMORPHOSIS} <= {
            c.code for c in env.engine.probe.observation(1).hand}
        graceful = discarded = summoned = snatched = targeted = meta = paid = fused = checked = False
        costs = set()
        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / "snatch_metamorphosis.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not graceful:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == GRACEFUL_CHARITY), None)
                graceful |= action is not None
            if graceful and not discarded and actions[0].kind == "select_cards":
                action = next((a for a in actions if {c["code"] for c in a.parameters["cards"]}
                               == {LIGHT, DARK}), None)
                assert action is not None
                discarded = True
            if discarded and obs.turn == 1 and obs.acting_player == 0 \
                    and not summoned and action is None:
                action = next((a for a in actions if a.kind == "special_summon"
                               and a.parameters.get("code") == CHAOS_SORCERER), None)
                summoned |= action is not None
            if summoned and costs != {LIGHT, DARK} and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               in {LIGHT, DARK} - costs and a.parameters.get("location") == 16),
                              action)
                if action is not None:
                    costs.add(action.parameters["code"])
            if obs.turn == 2 and obs.acting_player == 1 and costs == {LIGHT, DARK}:
                if not snatched:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == SNATCH), action)
                    snatched |= action is not None and action.kind == "activate"
                if snatched and not targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == CHAOS_SORCERER and a.parameters.get("controller") == 0),
                                  action)
                    targeted |= action is not None and action.kind == "select_card"
                stolen = any(c.code == CHAOS_SORCERER and c.controller == 1
                             for c in obs.field)
                if targeted and stolen and not meta:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == METAMORPHOSIS), action)
                    meta |= action is not None and action.kind == "activate"
                if meta and not paid and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == CHAOS_SORCERER and a.parameters.get("controller") == 1
                                   and a.parameters.get("location") == 4), action)
                    paid |= action is not None and action.kind == "select_card"
                if paid and not fused and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == RYU_SENSHI), action)
                    fused |= action is not None and action.kind == "select_card"
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if fused and not checked and any(c.code == RYU_SENSHI and c.controller == 1
                                            for c in obs.field):
                assert CHAOS_SORCERER in {c.code for c in obs.graveyards[0]}
                assert {SNATCH, METAMORPHOSIS} <= {c.code for c in obs.graveyards[1]}
                assert not any(c.code == CHAOS_SORCERER for c in obs.field)
                assert obs.extra_deck_counts[1] == 0
                assert obs.life_points == (8000, 8000)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail("Snatch Steal / Metamorphosis duel did not finish")
