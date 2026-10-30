"""Skill Drain removes Skilled's counters before a chained Spell resolves."""

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
UPSTART = 70368879
SKILL_DRAIN = 82732705
MST = 5318639


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_drain", [False, True])
def test_skill_drain_removes_skilled_counters_and_blocks_pot_counter(tmp_path, chain_drain):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    required = (f"goat/c{SKILLED}.lua", *(f"official/c{code}.lua" for code in
                                             (POT, UPSTART, SKILL_DRAIN)))
    if any(not (root / "scripts" / script).is_file() for script in required):
        pytest.skip("required GOAT or official card script not installed")
    own = tmp_path / "skilled.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        SKILLED, POT, UPSTART, *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    other = tmp_path / "skill_drain.ydk"
    other.write_text("#main\n" + "\n".join(map(str, (
        SKILL_DRAIN, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(other), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {SKILLED, POT, UPSTART} <= {card.code for card in obs.hand}
        assert SKILL_DRAIN in {card.code for card in
                               env.engine.probe.observation(1).hand}
        summoned = upstart_used = drain_set = pot_used = response_seen = checked = False
        deck_before = None
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"skilled_drain_{chain_drain}.json"
                write_trajectory(path, env.trajectory())
                replay = read_trajectory(path)
                assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(
                    replay.decisions)
                audit_trajectory_visibility(replay)
                return
            actions = env.legal_actions()
            action = None
            if not checked and obs.turn == 1 and obs.acting_player == 0:
                if not summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == SKILLED), None)
                    summoned = action is not None
                elif not upstart_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == UPSTART), None)
                    upstart_used = action is not None
            if not checked and upstart_used and obs.turn == 2 \
                    and obs.acting_player == 1 and not drain_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SKILL_DRAIN), None)
                drain_set = action is not None
            if not checked and drain_set and obs.turn == 3 \
                    and obs.acting_player == 0 and not pot_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == POT), None)
                if action is not None:
                    pot_used = True
                    deck_before = obs.deck_counts[0]
                    skilled = next(c for c in obs.field if c.code == SKILLED)
                    assert sum(amount for _, amount in skilled.counters) == 1
            if not checked and pot_used and obs.acting_player == 1 \
                    and not response_seen:
                drain = next((a for a in actions if a.kind == "chain"
                              and a.parameters.get("code") == SKILL_DRAIN), None)
                if drain is not None:
                    assert [link.card_code for link in obs.chain] == [POT]
                    action = drain if chain_drain else next(
                        a for a in actions if a.kind == "pass")
                    response_seen = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if response_seen and not checked and not obs.chain \
                    and POT in {card.code for card in obs.graveyards[0]}:
                assert obs.deck_counts[0] == deck_before - 2
                assert obs.life_points[1] == (8000 if chain_drain else 9000)
                own_skilled = next(c for c in obs.field if c.code == SKILLED)
                assert sum(amount for _, amount in own_skilled.counters) == (
                    0 if chain_drain else 2)
                assert next(c for c in env.engine.probe.observation(1).field
                            if c.code == SKILLED).counters == own_skilled.counters
                assert any(c.code == SKILL_DRAIN and
                           c.position == ("faceup" if chain_drain else "facedown")
                           for c in env.engine.probe.observation(1).field)
                assert {f"goat/c{SKILLED}.lua", *(f"official/c{code}.lua" for code in
                                               (POT, UPSTART, SKILL_DRAIN))} <= \
                    env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail("Skilled / Skill Drain fixture exceeded decision budget")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_skilled_gains_counters_again_after_skill_drain_is_destroyed(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    required = (f"goat/c{SKILLED}.lua", *(f"official/c{code}.lua" for code in
                                             (POT, UPSTART, SKILL_DRAIN, MST)))
    if any(not (root / "scripts" / script).is_file() for script in required):
        pytest.skip("required GOAT or official card script not installed")
    own = tmp_path / "skilled_recovery.ydk"
    cards = list(VANILLA_DECK)
    for index, code in ((0, SKILLED), (1, UPSTART), (2, UPSTART),
                        (13, POT), (17, MST)):
        cards[index] = code
    own.write_text("#main\n" + "\n".join(map(str, cards))
                   + "\n#extra\n!side\n")
    other = tmp_path / "skill_drain.ydk"
    other.write_text("#main\n" + "\n".join(map(str, (
        SKILL_DRAIN, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(other), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert [c.code for c in obs.hand].count(UPSTART) == 2
        assert {SKILLED, POT, MST} <= {c.code for c in obs.hand}
        stage = 0
        # 0: Summon Skilled; 1: first Upstart; 2: Set Drain;
        # 3: Pot; 4: chain Drain; 5: wait for Pot; 6: MST;
        # 7: choose Drain; 8: wait for MST; 9: second Upstart.
        agents = (RandomAgent(54), RandomAgent(55))
        checked = False
        for _ in range(5000):
            if env.is_terminal():
                assert stage == 10 and checked
                path = tmp_path / "skilled_recovery.json"
                write_trajectory(path, env.trajectory())
                replay = read_trajectory(path)
                assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(
                    replay.decisions)
                audit_trajectory_visibility(replay)
                assert set(required) <= env.engine.probe.loaded_script_sha256.keys()
                return
            actions = env.legal_actions()
            action = None
            if stage == 0 and obs.turn == 1 and obs.acting_player == 0:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == SKILLED), None)
                if action is not None:
                    stage = 1
            elif stage == 1 and obs.turn == 1 and obs.acting_player == 0:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == UPSTART), None)
                if action is not None:
                    stage = 2
            elif stage == 2 and obs.turn == 2 and obs.acting_player == 1:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SKILL_DRAIN), None)
                if action is not None:
                    stage = 3
            elif stage == 3 and obs.turn == 3 and obs.acting_player == 0:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == POT), None)
                if action is not None:
                    skilled = next(c for c in obs.field if c.code == SKILLED)
                    assert sum(n for _, n in skilled.counters) == 1
                    stage = 4
            elif stage == 4 and obs.acting_player == 1:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SKILL_DRAIN), None)
                if action is not None:
                    stage = 5
            elif stage == 6 and obs.turn == 3 and obs.acting_player == 0:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == MST), None)
                if action is not None:
                    stage = 7
            elif stage == 7 and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == SKILL_DRAIN
                               and a.parameters.get("controller") == 1), None)
                if action is not None:
                    stage = 8
            elif stage == 9 and obs.turn == 3 and obs.acting_player == 0:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == UPSTART), None)
                if action is not None:
                    stage = 10
            if action is None and stage < 10:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if stage == 5 and not obs.chain and any(
                    c.code == POT for c in obs.graveyards[0]):
                skilled = next(c for c in obs.field if c.code == SKILLED)
                assert skilled.counters == ()
                assert any(c.code == SKILL_DRAIN and c.position == "faceup"
                           for c in obs.field)
                stage = 6
            if stage == 8 and not obs.chain and any(
                    c.code == SKILL_DRAIN for c in obs.graveyards[1]):
                skilled = next(c for c in obs.field if c.code == SKILLED)
                assert sum(n for _, n in skilled.counters) == 1
                assert next(c for c in env.engine.probe.observation(1).field
                            if c.code == SKILLED).counters == skilled.counters
                stage = 9
            if stage == 10 and not checked and not obs.chain and sum(
                    c.code == UPSTART for c in obs.graveyards[0]) == 2:
                skilled = next(c for c in obs.field if c.code == SKILLED)
                assert sum(n for _, n in skilled.counters) == 2
                assert next(c for c in env.engine.probe.observation(1).field
                            if c.code == SKILLED).counters == skilled.counters
                checked = True
    pytest.fail("Skilled did not regain counters after Skill Drain left")
