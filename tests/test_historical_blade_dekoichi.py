"""Blade Knight negates Dekoichi's draw only while attacking alone."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

BLADE = 39507162
DEKOICHI = 87621407


def _deck(path, cards):
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("ally", [False, True])
def test_blade_knight_lone_monster_condition_against_dekoichi(tmp_path, ally):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (BLADE, DEKOICHI)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card scripts not installed")
    attacker = _deck(tmp_path / "blade.ydk", (
        *([BLADE] * 3), *VANILLA_DECK[3:]))
    defender = _deck(tmp_path / "dekoichi.ydk", (
        *([DEKOICHI] * 3), *VANILLA_DECK[3:]))

    with GoatEnvironment(attacker, defender, seed=72,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert BLADE in {card.code for card in obs.hand}
        assert DEKOICHI in {card.code for card in
                            env.engine.probe.observation(1).hand}
        blade_summoned = dekoichi_set = ally_summoned = False
        battle = attacked = target_chosen = checked = False
        deck_before = hand_before = None
        agents = (RandomAgent(72), RandomAgent(73))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"blade_dekoichi_{ally}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not blade_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == BLADE), None)
                blade_summoned = action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not dekoichi_set:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == DEKOICHI), None)
                dekoichi_set = action is not None
            if obs.turn == 3 and obs.acting_player == 0 and dekoichi_set:
                if ally and not ally_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") != BLADE), None)
                    ally_summoned = action is not None
                if obs.phase == "main1" and not battle and action is None:
                    action = next((a for a in actions if a.kind == "battle_phase"), None)
                    battle = action is not None
                elif obs.phase == "battle_start" and not attacked:
                    assert sum(c.controller == 0 and c.zone == "monster"
                               for c in obs.field) == (2 if ally else 1)
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == BLADE), None)
                    attacked = action is not None
            if attacked and not target_chosen and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 4
                               and "code" not in a.parameters), None)
                if action is not None:
                    deck_before = obs.deck_counts[1]
                    hand_before = len(env.engine.probe.observation(1).hand)
                    target_chosen = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if target_chosen and not checked and DEKOICHI in {
                    c.code for c in obs.graveyards[1]} and obs.phase == "battle_step":
                owner = env.engine.probe.observation(1)
                assert owner.deck_counts[1] == deck_before - int(ally)
                assert len(owner.hand) == hand_before + int(ally)
                assert obs.life_points == (8000, 8000)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail("Blade Knight / Dekoichi duel did not finish")
