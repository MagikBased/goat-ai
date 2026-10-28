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
