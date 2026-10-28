"""Two resolving Spell activations in one chain give Skilled two counters."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SKILLED = 504700122
POT = 55144522
MST = 5318639


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_skilled_counts_mst_chained_to_pot_without_losing_pot_draw(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    required = (f"goat/c{SKILLED}.lua", f"official/c{POT}.lua",
                f"official/c{MST}.lua")
    if any(not (root / "scripts" / script).is_file() for script in required):
        pytest.skip("required GOAT or official card script not installed")
    own = tmp_path / "skilled.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        SKILLED, POT, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    other = tmp_path / "mst.ydk"
    other.write_text("#main\n" + "\n".join(map(str, (
        MST, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(other), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {SKILLED, POT} <= {card.code for card in obs.hand}
        assert MST in {card.code for card in env.engine.probe.observation(1).hand}
        summoned = mst_set = pot_activated = mst_chained = target_chosen = checked = False
        deck_before = None
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / "skilled_mst_pot.json"
                write_trajectory(path, env.trajectory())
                replay = read_trajectory(path)
                assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(
                    replay.decisions)
                audit_trajectory_visibility(replay)
                return
            actions = env.legal_actions()
            action = None
            if not checked and obs.turn == 1 and obs.acting_player == 0 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == SKILLED), None)
                summoned = action is not None
            if not checked and obs.turn == 2 and obs.acting_player == 1 and not mst_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == MST), None)
                mst_set = action is not None
            if not checked and obs.turn == 3 and obs.acting_player == 0 \
                    and not pot_activated:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == POT), None)
                if action is not None:
                    pot_activated = True
                    deck_before = obs.deck_counts[0]
            if not checked and pot_activated and obs.acting_player == 1 \
                    and not mst_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == MST), None)
                if action is not None:
                    assert [link.card_code for link in obs.chain] == [POT]
                    mst_chained = True
            if not checked and mst_chained and not target_chosen \
                    and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 0
                               and a.parameters.get("location") == 8
                               and a.parameters.get("code") == POT), None)
                assert action is not None
                target_chosen = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if target_chosen and not checked and not obs.chain \
                    and {POT, MST} <= {card.code for grave in obs.graveyards
                                       for card in grave}:
                assert obs.deck_counts[0] == deck_before - 2
                own_skilled = next(card for card in obs.field if card.code == SKILLED)
                assert sum(amount for _, amount in own_skilled.counters) == 2
                opponent_skilled = next(card for card in env.engine.probe.observation(1).field
                                        if card.code == SKILLED)
                assert opponent_skilled.counters == own_skilled.counters
                assert {f"goat/c{SKILLED}.lua", f"official/c{POT}.lua",
                        f"official/c{MST}.lua"} <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail("Skilled / MST / Pot fixture exceeded decision budget")
