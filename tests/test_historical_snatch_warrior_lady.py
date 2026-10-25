"""The controller of a stolen D.D. Warrior Lady chooses her battle banish."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

WARRIOR_LADY = 7572887
SNATCH = 45986603
GIANT_SOLDIER = 13039848


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("banish", [False, True])
def test_stolen_warrior_lady_controller_chooses_banish(tmp_path, banish):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (WARRIOR_LADY, SNATCH)}
    if any(not (root / "scripts" / relative).is_file() for relative in scripts):
        pytest.skip("required card script not installed")
    owner_deck = tmp_path / "warrior_lady.ydk"
    owner_deck.write_text("#main\n" + "\n".join(map(str, (
        WARRIOR_LADY, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    snatch_deck = tmp_path / "snatch.ydk"
    snatch_deck.write_text("#main\n" + "\n".join(map(str, (
        SNATCH, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(owner_deck), str(snatch_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {WARRIOR_LADY, GIANT_SOLDIER} <= {c.code for c in obs.hand}
        assert SNATCH in {c.code for c in env.engine.probe.observation(1).hand}
        soldier_set = lady_summoned = snatched = targeted = battle = attacked = False
        attack_targeted = choice_made = checked = False
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"snatch_warrior_lady_{banish}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not soldier_set:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == GIANT_SOLDIER), None)
                soldier_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not lady_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == WARRIOR_LADY), None)
                lady_summoned |= action is not None
            if obs.turn == 4 and obs.acting_player == 1:
                if not snatched:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == SNATCH), None)
                    snatched |= action is not None
                if snatched and not targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == WARRIOR_LADY and a.parameters.get("controller") == 0),
                                  action)
                    targeted |= action is not None and action.kind == "select_card"
                stolen = any(c.code == WARRIOR_LADY and c.controller == 1
                             for c in obs.field)
                if stolen and not battle and obs.phase == "main1":
                    action = next((a for a in actions if a.kind == "battle_phase"), action)
                    battle |= action is not None and action.kind == "battle_phase"
                if battle and obs.phase == "battle_start" and not attacked:
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == WARRIOR_LADY), action)
                    attacked |= action is not None and action.kind == "attack"
                if attacked and not attack_targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("controller") == 0
                                   and a.parameters.get("location") == 4
                                   and "code" not in a.parameters), action)
                    attack_targeted |= action is not None and action.kind == "select_card"
            if attack_targeted and not choice_made and any(
                    a.kind == "yes" for a in actions):
                assert obs.phase == "damage_step"
                assert obs.acting_player == obs.viewer == 1
                assert obs.life_points == (8000, 7500)
                action = next(a for a in actions if a.kind == ("yes" if banish else "no"))
                choice_made = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if choice_made and not checked and obs.turn == 4 \
                    and obs.phase == "battle_step" and not obs.chain:
                if banish:
                    assert {WARRIOR_LADY, GIANT_SOLDIER} <= {
                        c.code for c in obs.banished[0]}
                    assert not any(c.code in (WARRIOR_LADY, GIANT_SOLDIER)
                                   for c in obs.field)
                    assert SNATCH in {c.code for c in obs.graveyards[1]}
                else:
                    assert not obs.banished[0]
                    assert any(c.code == WARRIOR_LADY and c.controller == 1
                               for c in obs.field)
                    assert any(c.code == GIANT_SOLDIER and c.controller == 0
                               for c in obs.field)
                    assert any(c.code == SNATCH for c in obs.field)
                assert obs.life_points == (8000, 7500)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail("Snatch / D.D. Warrior Lady duel did not finish")
