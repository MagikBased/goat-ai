"""Scapegoat can fill Monster Zones while Snatch Steal is on a chain."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SNATCH = 45986603
SCAPEGOAT = 504700123
MST = 5318639
SHEEP_CODES = {73915052, 73915053, 73915054, 73915055}


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_goat", [False, True])
def test_snatch_steal_when_scapegoat_fills_its_controllers_zones(tmp_path, chain_goat):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"official/c{SNATCH}.lua", f"goat/c{SCAPEGOAT}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    attacker = tmp_path / "snatch_goat.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        SNATCH, SCAPEGOAT, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(attacker), "examples/decks/vanilla_probe.ydk", seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {SNATCH, SCAPEGOAT}.issubset({c.code for c in obs.hand})
        own_summoned = other_summoned = snatch_used = target_chosen = False
        goat_chained = False
        target_code = None
        for _ in range(90):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not own_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                own_summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not other_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    target_code = action.parameters["code"]
                    other_summoned = True
            if obs.turn == 3 and obs.acting_player == 0 and not snatch_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SNATCH), action)
                snatch_used |= action is not None and action.kind == "activate"
            if snatch_used and not target_chosen and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == target_code and a.parameters.get("controller") == 1), None)
                target_chosen |= action is not None
            if chain_goat and target_chosen and not goat_chained \
                    and obs.acting_player == 0 and obs.chain:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SCAPEGOAT), action)
                if action is not None and action.kind == "chain":
                    assert len([c for c in obs.field if c.zone == "monster"
                                and c.controller == 0]) == 1
                    assert obs.chain[0].card_code == SNATCH
                    goat_chained = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if target_chosen and not obs.chain and obs.turn == 3 \
                    and obs.acting_player == 0 and obs.phase == "main1":
                own = env.engine.probe.observation(0)
                own_monsters = [c for c in own.field if c.zone == "monster"
                                and c.controller == 0]
                if chain_goat:
                    assert goat_chained
                    assert len(own_monsters) == 5
                    assert sum(c.code in SHEEP_CODES for c in own_monsters) == 4
                    assert target_code in {c.code for c in own.graveyards[1]}
                    assert target_code not in {c.code for c in own.field}
                    assert SNATCH in {c.code for c in own.graveyards[0]}
                    assert SCAPEGOAT in {c.code for c in own.graveyards[0]}
                else:
                    assert len(own_monsters) == 2
                    assert target_code in {c.code for c in own_monsters}
                    assert target_code not in {c.code for c in own.graveyards[1]}
                    assert SNATCH in {c.code for c in own.field}
                assert own.life_points == (8000, 8000)
                loaded = env.engine.probe.loaded_script_sha256
                assert f"official/c{SNATCH}.lua" in loaded
                if chain_goat:
                    assert f"goat/c{SCAPEGOAT}.lua" in loaded
                return
    pytest.fail("Snatch/Scapegoat chain did not resolve within 90 decisions")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_snatch_steal_cannot_start_with_five_occupied_monster_zones(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck = tmp_path / "full_zones.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        SNATCH, SCAPEGOAT, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        goat_used = other_summoned = own_summoned = False
        for _ in range(75):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not goat_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                goat_used |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not other_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                other_summoned |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not own_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                own_summoned |= action is not None
            if goat_used and other_summoned and own_summoned \
                    and obs.turn == 3 and obs.acting_player == 0 \
                    and action is None \
                    and obs.phase == "main1" and any(a.kind == "end_phase"
                                                      for a in actions):
                assert len([c for c in obs.field if c.zone == "monster"
                            and c.controller == 0]) == 5
                assert len([c for c in obs.field if c.zone == "monster"
                            and c.controller == 1]) == 1
                assert SNATCH in {c.code for c in obs.hand}
                assert not any(a.kind == "activate" and a.parameters.get("code")
                               == SNATCH for a in actions)
                assert f"goat/c{SCAPEGOAT}.lua" in \
                    env.engine.probe.loaded_script_sha256
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
    pytest.fail("Scapegoat did not leave five occupied zones on turn 3")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_snatch_target_is_destroyed_when_original_controller_has_no_return_zone(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{SNATCH}.lua", f"goat/c{SCAPEGOAT}.lua",
               f"official/c{MST}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    owner = tmp_path / "owner.ydk"
    owner.write_text("#main\n" + "\n".join(map(str, (
        SCAPEGOAT, MST, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    stealer = tmp_path / "stealer.ydk"
    stealer.write_text("#main\n" + "\n".join(map(str, (
        SNATCH, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(owner), str(stealer), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {SCAPEGOAT, MST} <= {c.code for c in obs.hand}
        assert SNATCH in {c.code for c in env.engine.probe.observation(1).hand}
        first_summon = snatch = snatch_target = second_summon = goat_set = False
        goat_used = mst_used = mst_targeted = False
        stolen_code = second_code = None
        for _ in range(160):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not first_summon:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    stolen_code = action.parameters["code"]
                    first_summon = True
            if obs.turn == 2 and obs.acting_player == 1:
                if not snatch:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == SNATCH), None)
                    snatch |= action is not None
                if snatch and not snatch_target and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == stolen_code and a.parameters.get("controller") == 0),
                                  action)
                    snatch_target |= action is not None and action.kind == "select_card"
            if obs.turn == 3 and obs.acting_player == 0 and snatch_target:
                if not second_summon:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        second_code = action.parameters["code"]
                        second_summon = True
                if second_summon and not goat_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == SCAPEGOAT), None)
                    goat_set |= action is not None
            if obs.turn == 5 and obs.acting_player == 0 and goat_set:
                if not goat_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == SCAPEGOAT), None)
                    goat_used |= action is not None
                if goat_used and not mst_used and action is None:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == MST), None)
                    if action is not None:
                        assert len([c for c in obs.field if c.zone == "monster"
                                    and c.controller == 0]) == 5
                        assert any(c.code == stolen_code and c.controller == 1
                                   for c in obs.field)
                        mst_used = True
                if mst_used and not mst_targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == SNATCH
                                   and a.parameters.get("controller") == 1), action)
                    mst_targeted |= action is not None and action.kind == "select_card"
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if mst_targeted and not obs.chain and obs.turn == 5 \
                    and SNATCH in {c.code for c in obs.graveyards[1]}:
                assert all((first_summon, snatch, snatch_target, second_summon,
                            goat_set, goat_used, mst_used, mst_targeted))
                assert stolen_code in {c.code for c in obs.graveyards[0]}
                assert stolen_code not in {c.code for c in obs.field}
                assert any(c.code == second_code and c.controller == 0
                           and c.zone == "monster" for c in obs.field)
                assert sum(c.code in SHEEP_CODES and c.controller == 0
                           and c.zone == "monster" for c in obs.field) == 4
                assert obs.life_points == (10000, 8000)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                agents = (RandomAgent(52), RandomAgent(53))
                for _ in range(3000):
                    if env.is_terminal():
                        break
                    obs = env.step(agents[obs.acting_player].select_action(
                        obs, env.legal_actions()))
                else:
                    pytest.fail("full-zone Snatch continuation exceeded 3000 decisions")
                trajectory = env.trajectory()
                path = tmp_path / "snatch_full_return.json"
                write_trajectory(path, trajectory)
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                                             trajectory.decisions)
                return
        pytest.fail(f"full-zone Snatch line stalled: first={first_summon} "
                    f"snatch={snatch}/{snatch_target} second={second_summon}/{goat_set} "
                    f"goat={goat_used} mst={mst_used}/{mst_targeted} "
                    f"turn={obs.turn} phase={obs.phase}")
