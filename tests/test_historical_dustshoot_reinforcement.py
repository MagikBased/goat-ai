"""Dustshoot can return a Warrior before Reinforcement searches the Deck."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

REINFORCEMENT = 504700055  # GOAT variant
DUSTSHOOT = 64697231
BLADE_KNIGHT = 39507162


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_dustshoot_returned_warrior_can_be_searched_by_pending_reinforcement(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{REINFORCEMENT}.lua", f"official/c{DUSTSHOOT}.lua",
               f"official/c{BLADE_KNIGHT}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    warrior = tmp_path / "warrior.ydk"
    warrior.write_text("#main\n" + "\n".join(map(str, (
        REINFORCEMENT, BLADE_KNIGHT, BLADE_KNIGHT, *VANILLA_DECK[3:])))
        + "\n#extra\n!side\n")
    trap = tmp_path / "dustshoot.ydk"
    trap.write_text("#main\n" + "\n".join(map(str, (
        DUSTSHOOT, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(warrior), str(trap), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert Counter(c.code for c in obs.hand)[BLADE_KNIGHT] == 1
        assert REINFORCEMENT in {c.code for c in obs.hand}
        assert DUSTSHOOT in {c.code for c in env.engine.probe.observation(1).hand}
        trap_set = spell_used = trap_chained = returned = searched = checked = False
        deck_before = None
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / "dustshoot_reinforcement.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1 and not trap_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                trap_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and trap_set and not spell_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == REINFORCEMENT), None)
                if action is not None:
                    deck_before = obs.deck_counts[0]
                    spell_used = True
            if spell_used and obs.acting_player == 1 and not trap_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                if action is not None:
                    assert [link.card_code for link in obs.chain] == [REINFORCEMENT]
                    trap_chained = True
            if trap_chained and not returned and actions[0].kind == "select_card":
                assert [link.card_code for link in obs.chain] == [
                    REINFORCEMENT, DUSTSHOOT]
                assert obs.acting_player == 1
                assert Counter(obs.known_opponent_hand_cards)[BLADE_KNIGHT] == 1
                action = next((a for a in actions if a.parameters.get("code")
                               == BLADE_KNIGHT and a.parameters.get("location") == 2), None)
                assert action is not None
                assert "sequence" not in action.parameters
                returned = True
            if returned and not searched and actions[0].kind == "select_card" \
                    and obs.acting_player == 0:
                assert obs.deck_counts[0] == deck_before + 1
                assert BLADE_KNIGHT not in {c.code for c in obs.hand}
                assert BLADE_KNIGHT not in env.engine.probe.observation(1) \
                    .known_opponent_hand_cards
                assert all(a.parameters.get("location") == 1
                           and "sequence" not in a.parameters for a in actions)
                action = next((a for a in actions if a.parameters.get("code")
                               == BLADE_KNIGHT), None)
                assert action is not None
                searched = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if searched and not checked and REINFORCEMENT in {
                    c.code for c in obs.graveyards[0]} and not obs.chain:
                owner = env.engine.probe.observation(0)
                opponent = env.engine.probe.observation(1)
                assert owner.deck_counts[0] == deck_before
                assert Counter(c.code for c in owner.hand)[BLADE_KNIGHT] == 1
                assert opponent.known_opponent_hand_cards.count(BLADE_KNIGHT) == 1
                assert opponent.opponent_hand_count == len(owner.hand)
                assert owner.life_points == (8000, 8000)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail("Dustshoot / Reinforcement chain did not finish")
