"""Ring removes Compulsory's target before the earlier chain link resolves."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

COMPULSORY = 94192409
RING = 511000824


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_ring", [False, True])
def test_ring_removes_compulsory_target_before_resolution(tmp_path, chain_ring):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"official/c{COMPULSORY}.lua", f"pre-errata/c{RING}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    decks = []
    for player in range(2):
        deck = tmp_path / f"compulsory_ring_p{player}.ydk"
        cards = list(VANILLA_DECK)
        if player == 0:
            cards[:3] = [COMPULSORY] * 3
        else:
            cards[6] = RING
        deck.write_text("#main\n" + "\n".join(map(str, cards))
                        + "\n#extra\n!side\n")
        decks.append(str(deck))
    with GoatEnvironment(*decks, seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert COMPULSORY in {c.code for c in obs.hand}
        assert RING in {c.code for c in env.engine.probe.observation(1).hand}
        compulsory_set = ring_set = monster_summoned = activated = False
        compulsory_targeted = ring_chained = ring_targeted = resolved = False
        monster_code = None
        monster_attack = None
        for _ in range(130):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not compulsory_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == COMPULSORY), None)
                compulsory_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not ring_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == RING), action)
                    ring_set |= action is not None and action.parameters.get("code") == RING
                if ring_set and not monster_summoned and action is None:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        monster_summoned = True
                        monster_code = action.parameters["code"]
            if obs.turn == 3 and obs.acting_player == 0 and monster_summoned \
                    and not activated:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == COMPULSORY), action)
                activated |= action is not None and action.parameters.get("code") == COMPULSORY
            if activated and not compulsory_targeted and actions[0].kind == "select_card":
                monster_attack = next(c.attack for c in obs.field
                                      if c.controller == 1 and c.zone == "monster")
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("code") == monster_code), None)
                compulsory_targeted |= action is not None
            if chain_ring and compulsory_targeted and obs.acting_player == 1 \
                    and not ring_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == RING), action)
                ring_chained |= action is not None and action.parameters.get("code") == RING
            if ring_chained and not ring_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("code") == monster_code), None)
                ring_targeted |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if compulsory_targeted and COMPULSORY in {c.code for c in obs.graveyards[0]}:
                if chain_ring:
                    assert ring_chained and ring_targeted
                    assert obs.life_points == (8000 - monster_attack,) * 2
                    assert monster_code in {c.code for c in obs.graveyards[1]}
                    assert monster_code not in {c.code for c in env.engine.probe.observation(1).hand}
                else:
                    assert obs.life_points == (8000, 8000)
                    assert monster_code in {c.code for c in env.engine.probe.observation(1).hand}
                    assert monster_code not in {c.code for c in obs.graveyards[1]}
                    assert RING not in {c.code for c in obs.graveyards[1]}
                assert not any(c.code == monster_code and c.zone == "monster"
                               for c in obs.field)
                resolved = True
                break
        assert resolved, "Compulsory/Ring response did not resolve"
        agents = (RandomAgent(117), RandomAgent(118))
        for _ in range(3000):
            if env.is_terminal():
                break
            obs = env.step(agents[obs.acting_player].select_action(
                obs, env.legal_actions()))
        else:
            pytest.fail("Compulsory/Ring duel did not terminate")
        trajectory = env.trajectory()
        path = tmp_path / f"compulsory_ring_{chain_ring}.json"
        write_trajectory(path, trajectory)
        saved = read_trajectory(path)
        assert verify_trajectory(saved, ExperimentalOcgcoreEngine(root)) \
            == len(trajectory.decisions)
        audit_trajectory_visibility(saved)
