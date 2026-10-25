"""A stolen Ring target returns to its owner through chained Compulsory."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SNATCH_STEAL = 45986603
RING = 511000824
COMPULSORY = 94192409
GEMINI_ELF = 69140098


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_compulsory", [False, True])
def test_compulsory_returns_snatch_stolen_ring_target_to_owner(
        tmp_path, chain_compulsory):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"official/c{SNATCH_STEAL}.lua",
                     f"pre-errata/c{RING}.lua",
                     f"official/c{COMPULSORY}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    own_cards = list(VANILLA_DECK)
    own_cards[0] = SNATCH_STEAL
    own_cards[1] = RING
    own = tmp_path / "snatch_ring.ydk"
    own.write_text("#main\n" + "\n".join(map(str, own_cards))
                   + "\n#extra\n!side\n")
    other_cards = list(VANILLA_DECK)
    other_cards[0] = GEMINI_ELF
    other_cards[6] = COMPULSORY
    other = tmp_path / "gemini_compulsory.ydk"
    other.write_text("#main\n" + "\n".join(map(str, other_cards))
                     + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(other), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {SNATCH_STEAL, RING} <= {c.code for c in obs.hand}
        assert {GEMINI_ELF, COMPULSORY} <= {
            c.code for c in env.engine.probe.observation(1).hand}
        ring_set = elf_summoned = compulsory_set = snatch_used = False
        snatch_targeted = ring_used = ring_targeted = compulsory_chained = False
        compulsory_targeted = False
        for _ in range(110):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not ring_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == RING), None)
                ring_set = action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not elf_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == GEMINI_ELF), None)
                    elf_summoned = action is not None
                if elf_summoned and not compulsory_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == COMPULSORY), None)
                    compulsory_set = action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not snatch_used:
                assert ring_set and elf_summoned and compulsory_set
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SNATCH_STEAL), None)
                snatch_used = action is not None
            if snatch_used and not snatch_targeted \
                    and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == GEMINI_ELF and a.parameters.get("controller") == 1), None)
                snatch_targeted = action is not None
            if snatch_targeted and not ring_used and obs.acting_player == 0 \
                    and any(c.code == GEMINI_ELF and c.controller == 0
                            for c in obs.field):
                assert any(c.code == SNATCH_STEAL and c.controller == 0
                           for c in obs.field)
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == RING), None)
                ring_used = action is not None
            if ring_used and not ring_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == GEMINI_ELF and a.parameters.get("controller") == 0), None)
                ring_targeted = action is not None
            if chain_compulsory and ring_targeted and obs.acting_player == 1 \
                    and not compulsory_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == COMPULSORY), None)
                if action is not None:
                    assert [link.card_code for link in obs.chain] == [RING]
                    compulsory_chained = True
            if compulsory_chained and not compulsory_targeted \
                    and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == GEMINI_ELF and a.parameters.get("controller") == 0), None)
                compulsory_targeted = action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if ring_targeted and RING in {c.code for c in obs.graveyards[0]} \
                    and obs.chain == ():
                thief = env.engine.probe.observation(0)
                owner = env.engine.probe.observation(1)
                assert not any(c.code == GEMINI_ELF for c in thief.field)
                assert SNATCH_STEAL in {c.code for c in thief.graveyards[0]}
                if chain_compulsory:
                    assert compulsory_chained and compulsory_targeted
                    assert thief.life_points == (8000, 8000)
                    assert GEMINI_ELF in {c.code for c in owner.hand}
                    assert thief.known_opponent_hand_cards == (GEMINI_ELF,)
                    assert GEMINI_ELF not in {c.code for c in owner.graveyards[1]}
                    assert COMPULSORY in {c.code for c in owner.graveyards[1]}
                else:
                    assert not compulsory_chained
                    assert thief.life_points == (6100, 6100)
                    assert GEMINI_ELF in {c.code for c in owner.graveyards[1]}
                    assert COMPULSORY not in {c.code for c in owner.graveyards[1]}
                    assert thief.known_opponent_hand_cards == ()
                assert {f"official/c{SNATCH_STEAL}.lua",
                        f"pre-errata/c{RING}.lua",
                        f"official/c{COMPULSORY}.lua"} <= (
                            env.engine.probe.loaded_script_sha256.keys())
                break
        else:
            pytest.fail("Snatch / Ring / Compulsory chain did not resolve")
        if not chain_compulsory:
            return
        for _ in range(40):
            actions = env.legal_actions()
            if obs.turn == 4 and obs.acting_player == 1:
                summon = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == GEMINI_ELF), None)
                if summon is not None:
                    assert env.engine.probe.observation(0).known_opponent_hand_cards \
                        == (GEMINI_ELF,)
                    obs = env.step(summon)
                    break
            action = next((a for a in actions if a.kind in ("pass", "end_phase")),
                          actions[0])
            obs = env.step(action)
        else:
            pytest.fail("owner did not re-Summon returned Gemini Elf")
        for _ in range(10):
            if any(c.code == GEMINI_ELF and c.controller == 1
                   for c in env.engine.probe.observation(0).field):
                break
            actions = env.legal_actions()
            action = next((a for a in actions if a.kind in (
                "place", "select_position", "pass")), actions[0])
            obs = env.step(action)
        else:
            pytest.fail("Gemini Elf Summon did not finish")
        former_controller = env.engine.probe.observation(0)
        assert former_controller.known_opponent_hand_cards == ()
        assert any(c.code == GEMINI_ELF and c.controller == 1
                   for c in former_controller.field)
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(3000):
            if env.is_terminal():
                break
            obs = env.step(agents[obs.acting_player].select_action(
                obs, env.legal_actions()))
        else:
            pytest.fail("Snatch / Ring / Compulsory duel exceeded 3000 decisions")
        trajectory = env.trajectory()
        assert trajectory.winner in (0, 1, None)
        assert any(record.observation.viewer == 0
                   and record.observation.known_opponent_hand_cards == (GEMINI_ELF,)
                   for record in trajectory.decisions)
    path = tmp_path / "snatch_ring_compulsory.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    assert verify_trajectory(loaded, ExperimentalOcgcoreEngine(root)) == len(
        trajectory.decisions)
