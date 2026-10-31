"""Ring destroys Sangan under Skill Drain; the Graveyard search still resolves."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SANGAN = 504700178
RING = 511000824
SKILL_DRAIN = 82732705
MYSTICAL_ELF = 15025844


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("drain_active", [False, True])
def test_ring_destroyed_sangan_searches_under_skill_drain(tmp_path, drain_active):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"goat/c{SANGAN}.lua", f"pre-errata/c{RING}.lua",
               f"official/c{SKILL_DRAIN}.lua")
    if any(not (root / "scripts" / path).is_file() for path in scripts):
        pytest.skip("required card scripts not installed")
    owner = tmp_path / "sangan.ydk"
    opponent = tmp_path / "ring_drain.ydk"
    owner.write_text("#main\n" + "\n".join(map(str, (
        SANGAN, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    opponent.write_text("#main\n" + "\n".join(map(str, (
        RING, SKILL_DRAIN, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(owner), str(opponent), seed=1605,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert SANGAN in {card.code for card in obs.hand}
        assert {RING, SKILL_DRAIN} <= {
            card.code for card in env.engine.probe.observation(1).hand}
        summoned = drain_set = ring_set = drain_used = ring_used = False
        ring_targeted = searched = resolved = False
        deck_before_ring = None
        agents = (RandomAgent(520), RandomAgent(521))
        for _ in range(3000):
            if env.is_terminal():
                assert summoned and drain_set and ring_set and ring_used
                assert ring_targeted and searched and resolved
                assert drain_used == drain_active
                path = tmp_path / f"sangan_ring_drain_{int(drain_active)}.json"
                write_trajectory(path, env.trajectory())
                saved = read_trajectory(path)
                assert verify_trajectory(saved, ExperimentalOcgcoreEngine(root)) == len(
                    saved.decisions)
                assert audit_trajectory_visibility(saved)["decisions"] == len(
                    saved.decisions)
                assert set(scripts) <= env.engine.probe.loaded_script_sha256.keys()
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == SANGAN), None)
                summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not drain_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == SKILL_DRAIN), action)
                    drain_set |= action is not None and action.kind == "set_spell_trap"
                elif not ring_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == RING), action)
                    ring_set |= action is not None and action.kind == "set_spell_trap"
            if ring_set and obs.acting_player == 1 and not resolved:
                if drain_active and not drain_used:
                    action = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == SKILL_DRAIN), action)
                    drain_used |= action is not None and action.kind == "chain" \
                        and action.parameters.get("code") == SKILL_DRAIN
                elif not ring_used:
                    action = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == RING), action)
                    ring_used |= action is not None and action.kind == "chain" \
                        and action.parameters.get("code") == RING
                    if ring_used:
                        deck_before_ring = obs.deck_counts[0]
            if ring_used and not ring_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == SANGAN
                               and a.parameters.get("controller") == 0), None)
                ring_targeted |= action is not None
            if ring_targeted and not searched and actions[0].kind == "select_card" \
                    and any(a.parameters.get("location") == 1 for a in actions):
                assert SANGAN in {card.code for card in obs.graveyards[0]}
                assert obs.life_points == (7000, 6000 if drain_active else 7000)
                assert any(card.code == SKILL_DRAIN and
                           card.position == ("faceup" if drain_active else "facedown")
                           for card in env.engine.probe.observation(1).field)
                action = next((a for a in actions if a.parameters.get("code") == MYSTICAL_ELF
                               and a.parameters.get("location") == 1), None)
                assert action is not None
                searched = True
            if searched and not resolved and MYSTICAL_ELF in {
                    card.code for card in obs.hand}:
                assert obs.deck_counts[0] == deck_before_ring - 1
                assert env.engine.probe.observation(1).known_opponent_hand_cards == (
                    MYSTICAL_ELF,)
                resolved = True
            if action is None:
                action = (agents[obs.acting_player].select_action(obs, actions) if resolved
                          else next((a for a in actions if a.kind in
                                     ("pass", "place", "end_phase")), actions[0]))
            obs = env.step(action)
    pytest.fail("Sangan / Ring / Skill Drain duel did not terminate")
