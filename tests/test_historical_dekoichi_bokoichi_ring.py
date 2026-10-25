"""Dekoichi counts face-up Bokoichi when its Flip Effect resolves."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

DEKOICHI = 87621407
BOKOICHI = 8715625
RING = 511000824  # pre-errata variant


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_ring", [False, True])
def test_ring_removes_bokoichi_before_dekoichi_counts_it(tmp_path, chain_ring):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{DEKOICHI}.lua", f"pre-errata/c{RING}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    flip_deck = tmp_path / "dekoichi_bokoichi.ydk"
    flip_deck.write_text("#main\n" + "\n".join(map(str, (
        *([DEKOICHI] * 3), *([BOKOICHI] * 3), *VANILLA_DECK[6:])))
        + "\n#extra\n!side\n")
    trap_deck = tmp_path / "ring.ydk"
    trap_deck.write_text("#main\n" + "\n".join(map(str, (
        RING, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(flip_deck), str(trap_deck), seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {DEKOICHI, BOKOICHI} <= {card.code for card in obs.hand}
        assert RING in {card.code for card in env.engine.probe.observation(1).hand}
        bokoichi_summoned = dekoichi_set = ring_set = flipped = responded = False
        ring_targeted = checked = False
        deck_before = hand_before = None
        agents = (RandomAgent(15), RandomAgent(16))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"dekoichi_bokoichi_ring_{chain_ring}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not bokoichi_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == BOKOICHI), None)
                bokoichi_summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not ring_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == RING), None)
                ring_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not dekoichi_set:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == DEKOICHI), None)
                dekoichi_set |= action is not None
            if obs.turn == 5 and obs.acting_player == 0 and not flipped:
                action = next((a for a in actions if a.kind == "flip_summon"
                               and a.parameters.get("code") == DEKOICHI), None)
                if action is not None:
                    assert any(card.code == BOKOICHI and card.position == "faceup"
                               for card in obs.field)
                    deck_before = obs.deck_counts[0]
                    hand_before = len(obs.hand)
                    flipped = True
            if flipped and obs.acting_player == 1 and not responded \
                    and [link.card_code for link in obs.chain] == [DEKOICHI]:
                ring = next((a for a in actions if a.kind == "chain"
                             and a.parameters.get("code") == RING), None)
                assert ring is not None
                action = ring if chain_ring else next(a for a in actions if a.kind == "pass")
                responded = True
            if chain_ring and responded and not ring_targeted \
                    and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 0
                               and a.parameters.get("code") == BOKOICHI), None)
                ring_targeted |= action is not None
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            expected_draw = 1 if chain_ring else 2
            if responded and not checked and not obs.chain \
                    and obs.deck_counts[0] == deck_before - expected_draw:
                assert len(obs.hand) == hand_before + expected_draw
                assert any(card.code == DEKOICHI and card.position == "faceup"
                           for card in obs.field)
                assert (BOKOICHI in {card.code for card in obs.graveyards[0]}) \
                    == chain_ring
                assert (BOKOICHI in {card.code for card in obs.field}) != chain_ring
                assert (RING in {card.code for card in obs.graveyards[1]}) == chain_ring
                assert obs.life_points == ((7500, 7500) if chain_ring else (8000, 8000))
                assert f"official/c{DEKOICHI}.lua" in env.engine.probe.loaded_script_sha256
                if chain_ring:
                    assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                    assert ring_targeted
                checked = True
    pytest.fail("Dekoichi / Bokoichi / Ring duel did not finish")
