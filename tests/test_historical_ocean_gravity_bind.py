"""Ocean's Level reduction permits a Level 4 WATER attack through Gravity Bind."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

OCEAN = 295517
GAGAGIGO = 49003308
GRAVITY_BIND = 85742772
MST = 5318639


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("activate_ocean", (False, True), ids=("without_ocean", "ocean"))
def test_ocean_allows_gagagigo_attack_under_gravity_bind(tmp_path, activate_ocean):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{OCEAN}.lua", f"official/c{GRAVITY_BIND}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required pinned card scripts not installed")
    remaining = list(VANILLA_DECK)
    remaining.remove(GAGAGIGO)
    attacker = tmp_path / "water.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        OCEAN, GAGAGIGO, *remaining[:38]))) + "\n#extra\n!side\n")
    defender = tmp_path / "gravity.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        GRAVITY_BIND, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {OCEAN, GAGAGIGO} <= {c.code for c in obs.hand}
        assert GRAVITY_BIND in {c.code for c in env.engine.probe.observation(1).hand}
        ocean_used = summoned = bind_set = bind_used = checked = False
        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(3000):
            if env.is_terminal():
                break
            actions = env.legal_actions()
            action = None
            if not checked:
                if obs.turn == 1 and obs.acting_player == 0:
                    if activate_ocean and not ocean_used:
                        action = next((a for a in actions if a.kind == "activate"
                                       and a.parameters.get("code") == OCEAN), None)
                        ocean_used |= action is not None
                    if not summoned and action is None:
                        action = next((a for a in actions if a.kind == "normal_summon"
                                       and a.parameters.get("code") == GAGAGIGO), None)
                        summoned |= action is not None
                if obs.turn == 2 and obs.acting_player == 1 and not bind_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == GRAVITY_BIND), None)
                    bind_set |= action is not None
                if obs.turn == 3 and obs.acting_player == 0 and obs.phase == "main1":
                    action = next((a for a in actions if a.kind == "battle_phase"), action)
                if obs.turn >= 3 and bind_set and not bind_used \
                        and obs.acting_player == 1:
                    option = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == GRAVITY_BIND), None)
                    if option is not None:
                        action = option
                        bind_used = True
                if obs.turn == 3 and obs.phase == "battle_start" and bind_used \
                        and not obs.chain and obs.acting_player == 0:
                    assert any(c.code == GRAVITY_BIND and c.position == "faceup"
                               for c in obs.field)
                    monster = next(c for c in obs.field if c.code == GAGAGIGO)
                    assert monster.level == (3 if activate_ocean else 4)
                    attacks = [a for a in actions if a.kind == "attack"
                               and a.parameters.get("code") == GAGAGIGO]
                    assert bool(attacks) == activate_ocean
                    checked = True
            if action is None:
                action = (next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0]) if not checked else
                    agents[obs.acting_player].select_action(obs, actions))
            obs = env.step(action)
        assert checked and env.is_terminal(), "Ocean/Gravity Bind duel did not finish"
        path = tmp_path / f"gravity_{activate_ocean}.json"
        write_trajectory(path, env.trajectory())
    replay = read_trajectory(path)
    assert audit_trajectory_visibility(replay)["decisions"] == len(replay.decisions)
    assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(replay.decisions)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_destroying_ocean_after_attack_declaration_blocks_level_four_attacker(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (OCEAN, GRAVITY_BIND, MST)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required pinned card scripts not installed")
    remaining = list(VANILLA_DECK)
    remaining.remove(GAGAGIGO)
    attacker = tmp_path / "water.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        OCEAN, GAGAGIGO, *remaining[:38]))) + "\n#extra\n!side\n")
    defender = tmp_path / "gravity_mst.ydk"
    defender_cards = [GRAVITY_BIND, MST, *VANILLA_DECK[2:]]
    defender_cards[1], defender_cards[4] = defender_cards[4], defender_cards[1]
    defender.write_text("#main\n" + "\n".join(map(str, defender_cards))
                        + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {OCEAN, GAGAGIGO} <= {c.code for c in obs.hand}
        assert {GRAVITY_BIND, MST} <= {
            c.code for c in env.engine.probe.observation(1).hand}
        ocean_used = summoned = bind_set = mst_set = bind_used = False
        attack_declared = mst_used = mst_targeted = checked = False
        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(3000):
            if env.is_terminal():
                break
            actions = env.legal_actions()
            action = None
            if not checked:
                if obs.turn == 1 and obs.acting_player == 0:
                    if not ocean_used:
                        action = next((a for a in actions if a.kind == "activate"
                                       and a.parameters.get("code") == OCEAN), None)
                        ocean_used |= action is not None
                    if ocean_used and not summoned and action is None:
                        action = next((a for a in actions if a.kind == "normal_summon"
                                       and a.parameters.get("code") == GAGAGIGO), None)
                        summoned |= action is not None
                if obs.turn == 2 and obs.acting_player == 1:
                    for code, done in ((GRAVITY_BIND, bind_set), (MST, mst_set)):
                        if not done and action is None:
                            action = next((a for a in actions if a.kind == "set_spell_trap"
                                           and a.parameters.get("code") == code), None)
                            if action is not None:
                                if code == GRAVITY_BIND:
                                    bind_set = True
                                else:
                                    mst_set = True
                if obs.turn == 3 and obs.acting_player == 0 and obs.phase == "main1":
                    action = next((a for a in actions if a.kind == "battle_phase"), action)
                if obs.turn == 3 and obs.acting_player == 1 and not bind_used:
                    option = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == GRAVITY_BIND), None)
                    if option is not None:
                        action = option
                        bind_used = True
                if obs.turn == 3 and obs.acting_player == 0 and bind_used \
                        and obs.phase == "battle_start" and not obs.chain \
                        and not attack_declared:
                    assert any(c.code == GRAVITY_BIND and c.position == "faceup"
                               for c in obs.field)
                    assert next(c for c in obs.field if c.code == GAGAGIGO).level == 3
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == GAGAGIGO), None)
                    attack_declared = action is not None
                if attack_declared and obs.acting_player == 1 and not mst_used:
                    option = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == MST), None)
                    if option is not None:
                        action = option
                        mst_used = True
                if mst_used and not mst_targeted and action is None \
                        and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == OCEAN
                                   and a.parameters.get("controller") == 0), None)
                    mst_targeted = action is not None
                if mst_targeted and action is None and not checked and not obs.chain \
                        and obs.phase == "battle_step" and obs.acting_player == 0 \
                        and any(a.kind == "main2" for a in actions):
                    assert OCEAN in {c.code for c in obs.graveyards[0]}
                    assert next(c for c in obs.field if c.code == GAGAGIGO).level == 4
                    assert any(c.code == GRAVITY_BIND for c in obs.field)
                    assert not any(a.kind == "attack" and a.parameters.get("code")
                                   == GAGAGIGO for a in actions)
                    assert obs.life_points == (8000, 8000)
                    assert len(obs.recent_attacks) == 1
                    checked = True
            if action is None:
                action = (next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0]) if not checked else
                    agents[obs.acting_player].select_action(obs, actions))
            obs = env.step(action)
        assert checked and env.is_terminal(), (
            f"Ocean removal replay duel did not finish: {ocean_used=} {summoned=} "
            f"{bind_set=} {mst_set=} {bind_used=} {attack_declared=} {mst_used=} "
            f"{mst_targeted=} {obs.turn=} {obs.phase=} {obs.life_points=}")
        assert scripts <= env.engine.probe.loaded_script_sha256.keys()
        path = tmp_path / "ocean_removed_attack.json"
        write_trajectory(path, env.trajectory())
    replay = read_trajectory(path)
    assert audit_trajectory_visibility(replay)["decisions"] == len(replay.decisions)
    assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(replay.decisions)
