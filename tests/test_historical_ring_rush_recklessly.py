"""GOAT Ring damage uses current ATK at its own chain resolution."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

RING = 511000824  # Pre-errata GOAT variant.
RUSH = 504700114  # GOAT variant.
SOLDIER = 49881766


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("order", ("ring_only", "rush_chained", "ring_chained"))
def test_ring_uses_current_attack_at_resolution(tmp_path, order):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"pre-errata/c{RING}.lua", f"goat/c{RUSH}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("pinned GOAT Ring and Rush scripts not installed")
    soldier_deck = tmp_path / "soldier.ydk"
    filler = [code for code in VANILLA_DECK if code != SOLDIER][:36]
    soldier_deck.write_text("#main\n" + "\n".join(map(str, (
        SOLDIER, RUSH, RUSH, RUSH, *filler))) + "\n#extra\n!side\n")
    ring_deck = tmp_path / "ring.ydk"
    ring_deck.write_text("#main\n" + "\n".join(map(str, (
        RING, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(soldier_deck), str(ring_deck), seed=316,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {SOLDIER, RUSH} <= {card.code for card in obs.hand}
        assert RING in {card.code for card in env.engine.probe.observation(1).hand}
        summoned = rush_set = ring_set = ring_used = ring_targeted = False
        rush_used = rush_targeted = checked = False
        agents = (RandomAgent(316), RandomAgent(317))
        for _ in range(3000):
            if env.is_terminal():
                break
            actions = env.legal_actions()
            action = None
            if not checked:
                if obs.turn == 1 and obs.acting_player == 0:
                    if not summoned:
                        action = next((a for a in actions if a.kind == "normal_summon"
                                       and a.parameters.get("code") == SOLDIER), None)
                        summoned |= action is not None
                    if summoned and not rush_set and action is None:
                        action = next((a for a in actions if a.kind == "set_spell_trap"
                                       and a.parameters.get("code") == RUSH), None)
                        rush_set |= action is not None
                if obs.turn == 2 and obs.acting_player == 1 and not ring_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == RING), None)
                    ring_set |= action is not None
                if (order == "ring_chained" and obs.turn == 3
                        and obs.acting_player == 0 and ring_set and not rush_used):
                    action = next((a for a in actions if a.kind in ("activate", "chain")
                                   and a.parameters.get("code") == RUSH), None)
                    rush_used |= action is not None
                if (order == "ring_chained" and rush_used and not rush_targeted
                        and actions[0].kind == "select_card"):
                    action = next((a for a in actions if a.parameters.get("code") == SOLDIER),
                                  None)
                    rush_targeted |= action is not None
                if (obs.turn == 3 and obs.acting_player == 1 and ring_set and not ring_used
                        and (order != "ring_chained" or rush_targeted)):
                    soldier = next(c for c in obs.field if c.code == SOLDIER)
                    assert soldier.attack == 1900
                    action = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == RING), None)
                    ring_used |= action is not None
                if ring_used and not ring_targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == SOLDIER),
                                  None)
                    ring_targeted |= action is not None
                if (order == "rush_chained" and ring_targeted
                        and obs.acting_player == 0 and not rush_used):
                    action = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == RUSH), None)
                    rush_used |= action is not None
                if (order == "rush_chained" and rush_used and not rush_targeted
                        and actions[0].kind == "select_card"):
                    action = next((a for a in actions if a.parameters.get("code") == SOLDIER),
                                  None)
                    rush_targeted |= action is not None
            if action is None:
                action = (next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0]) if not checked else
                    agents[obs.acting_player].select_action(obs, actions))
            obs = env.step(action)
            if (not checked and order == "ring_chained" and ring_targeted
                    and action.kind == "select_card"):
                assert tuple(link.card_code for link in obs.chain) == (RUSH, RING)
            if (not checked and order == "rush_chained" and rush_targeted
                    and action.kind == "select_card"):
                assert tuple(link.card_code for link in obs.chain) == (RING, RUSH)
            if ring_targeted and not checked and RING in {
                    card.code for card in obs.graveyards[1]}:
                assert summoned and rush_set and ring_set and ring_used
                assert obs.chain == ()
                assert obs.life_points == ((5400, 5400) if order == "rush_chained"
                                           else (6100, 6100))
                assert SOLDIER in {card.code for card in obs.graveyards[0]}
                assert not any(card.code == SOLDIER for card in obs.field)
                assert (RUSH in {card.code for card in obs.graveyards[0]}) == (
                    order != "ring_only")
                if order != "ring_only":
                    assert rush_used and rush_targeted
                checked = True
        assert checked and env.is_terminal(), "Ring / Rush duel did not finish"
        assert f"pre-errata/c{RING}.lua" in env.engine.probe.loaded_script_sha256
        if order != "ring_only":
            assert f"goat/c{RUSH}.lua" in env.engine.probe.loaded_script_sha256
        path = tmp_path / f"ring_rush_{order}.json"
        trajectory = env.trajectory()
        audit_trajectory_visibility(trajectory)
        write_trajectory(path, trajectory)
    assert verify_trajectory(read_trajectory(path), ExperimentalOcgcoreEngine(root)) > 0
