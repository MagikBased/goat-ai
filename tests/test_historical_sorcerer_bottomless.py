"""GOAT Ignition priority changes a Sorcerer/Bottomless exchange."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SORCERER = 9596126
GRACEFUL = 79571449
BOTTOMLESS = 504700052
LIGHT = 15025844
DARK = 7359741


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("use_priority", [False, True])
def test_sorcerer_priority_before_bottomless(tmp_path, use_priority):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"official/c{SORCERER}.lua", f"official/c{GRACEFUL}.lua",
               f"goat/c{BOTTOMLESS}.lua")
    for relative in scripts:
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    lights = (LIGHT, 62651957)
    darks = (49881766, DARK)
    filler = [code for code in VANILLA_DECK if code not in (*lights, *darks)]
    chaos_cards = (GRACEFUL, SORCERER,
                   *(code for code in lights for _ in range(3)),
                   *(code for code in darks for _ in range(3)), *filler[:26])
    chaos_deck = tmp_path / "sorcerer.ydk"
    chaos_deck.write_text("#main\n" + "\n".join(map(str, chaos_cards))
                          + "\n#extra\n!side\n")
    trap_deck = tmp_path / "bottomless.ydk"
    trap_deck.write_text("#main\n" + "\n".join(map(str, (
        BOTTOMLESS, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(chaos_deck), str(trap_deck), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert {SORCERER, GRACEFUL, LIGHT, DARK}.issubset(
            c.code for c in observation.hand)
        assert BOTTOMLESS in {c.code for c in env.engine.probe.observation(1).hand}
        graceful = discarded = trap_set = defender_summoned = summoned = False
        priority_seen = effect_used = target_selected = bottomless_used = False
        costs = set()
        defender_code = None
        for _ in range(100):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    graceful |= action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"] for c in
                                   a.parameters["cards"]} == {LIGHT, DARK}), None)
                    discarded |= action is not None
            if observation.turn == 2 and observation.acting_player == 1:
                if not trap_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOTTOMLESS), None)
                    trap_set |= action is not None
                if trap_set and not defender_summoned and action is None:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        defender_code = action.parameters["code"]
                        defender_summoned = True
            if observation.turn == 3 and observation.acting_player == 0 \
                    and defender_summoned:
                if not summoned:
                    action = next((a for a in actions if a.kind == "special_summon"
                                   and a.parameters.get("code") == SORCERER), None)
                    summoned |= action is not None
                if summoned and len(costs) < 2 and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   in ({LIGHT, DARK} - costs)), action)
                    if action is not None and action.kind == "select_card":
                        costs.add(action.parameters["code"])
                if summoned and len(costs) == 2 and not priority_seen:
                    option = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == SORCERER), None)
                    if option is not None:
                        assert observation.chain == ()
                        assert any(c.controller == 1 and c.zone == "spell_trap"
                                   and c.position == "facedown" and c.code is None
                                   for c in observation.field)
                        assert not observation.known_opponent_field_cards
                        priority_seen = True
                        action = option if use_priority else next(
                            a for a in actions if a.kind == "pass")
                        effect_used = use_priority
                if effect_used and not target_selected and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == defender_code and a.parameters.get("controller") == 1),
                                  None)
                    target_selected |= action is not None
            if priority_seen and observation.acting_player == 1 \
                    and not bottomless_used:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOTTOMLESS), None)
                if action is not None:
                    assert (len(observation.chain) == 1) == use_priority
                    bottomless_used = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if bottomless_used and BOTTOMLESS in {
                    c.code for c in observation.graveyards[1]}:
                assert priority_seen and costs == {LIGHT, DARK}
                assert observation.chain == ()
                assert SORCERER in {c.code for c in observation.banished[0]}
                assert (defender_code in {
                    c.code for c in observation.banished[1]}) == use_priority
                assert (defender_code in {
                    c.code for c in observation.field}) != use_priority
                assert target_selected == use_priority
                assert observation.life_points == (8000, 8000)
                assert set(scripts).issubset(env.engine.probe.loaded_script_sha256)
                agents = (RandomAgent(100), RandomAgent(101))
                for _ in range(5000):
                    action = agents[observation.acting_player].select_action(
                        observation, env.legal_actions())
                    observation = env.step(action)
                    if env.is_terminal():
                        trajectory = env.trajectory()
                        path = tmp_path / f"sorcerer_bottomless_{use_priority}.json"
                        write_trajectory(path, trajectory)
                        assert verify_trajectory(read_trajectory(path),
                                                 ExperimentalOcgcoreEngine(root)) == len(
                                                     trajectory.decisions)
                        return
                pytest.fail("Sorcerer/Bottomless duel did not finish in 5000 decisions")
    pytest.fail(f"Sorcerer/Bottomless line stalled: summon={summoned} "
                f"priority={priority_seen} effect={effect_used}/{target_selected} "
                f"Bottomless={bottomless_used} turn={observation.turn}")
