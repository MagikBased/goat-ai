"""Sangan searches from the Graveyard despite active Skill Drain."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SANGAN = 504700178  # GOAT variant
JINZO = 77585513
SKILL_DRAIN = 82732705
MYSTICAL_ELF = 15025844


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
@pytest.mark.parametrize("drain_active", (False, True))
def test_sangan_graveyard_trigger_survives_skill_drain(tmp_path, drain_active):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{SANGAN}.lua", f"official/c{JINZO}.lua",
                     f"official/c{SKILL_DRAIN}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    sangan_deck = tmp_path / "sangan.ydk"
    sangan_deck.write_text("#main\n" + "\n".join(map(str, (
        SANGAN, JINZO, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    drain_deck = tmp_path / "drain.ydk"
    drain_deck.write_text("#main\n" + "\n".join(map(str, (
        SKILL_DRAIN, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(sangan_deck), str(drain_deck), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert {SANGAN, JINZO}.issubset(card.code for card in observation.hand)
        assert SKILL_DRAIN in {card.code for card in env.engine.probe.observation(1).hand}
        summoned = drain_set = drain_used = jinzo_summoned = searched = resolved = False
        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(3000):
            if env.is_terminal():
                assert summoned and drain_set and jinzo_summoned and searched and resolved
                assert drain_used == drain_active
                path = tmp_path / f"sangan_drain_{int(drain_active)}.json"
                write_trajectory(path, env.trajectory())
                saved = read_trajectory(path)
                assert verify_trajectory(saved, ExperimentalOcgcoreEngine(root)) == len(
                    saved.decisions)
                audit_trajectory_visibility(saved)
                return
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 \
                    and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == SANGAN), None)
                summoned |= action is not None
            if observation.turn == 2 and observation.acting_player == 1 \
                    and not drain_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SKILL_DRAIN), None)
                drain_set |= action is not None
            if (drain_active and observation.turn == 3
                    and observation.acting_player == 1 and not drain_used):
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SKILL_DRAIN), None)
                drain_used |= action is not None
            if (observation.turn == 3 and observation.acting_player == 0
                    and (drain_used or not drain_active) and not jinzo_summoned):
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == JINZO), None)
                jinzo_summoned |= action is not None
            if jinzo_summoned and actions[0].kind == "tribute":
                action = next((a for a in actions if a.kind == "tribute"
                               and a.parameters.get("code") == SANGAN), None)
                assert action is not None
            if (jinzo_summoned and not searched and actions[0].kind == "select_card"
                    and any(a.parameters.get("location") == 1 for a in actions)):
                assert SANGAN in {card.code for card in observation.graveyards[0]}
                assert observation.life_points == (8000, 7000 if drain_active else 8000)
                assert any(card.code == SKILL_DRAIN
                           and card.position == ("faceup" if drain_active else "facedown")
                           for card in env.engine.probe.observation(1).field)
                action = next((a for a in actions if a.parameters.get("location") == 1
                               and a.parameters.get("code") == MYSTICAL_ELF), None)
                assert action is not None
                searched = True
            if searched and not resolved and sum(card.code == MYSTICAL_ELF
                                                 for card in observation.hand) == 2:
                assert MYSTICAL_ELF in env.engine.probe.observation(
                    1).known_opponent_hand_cards
                assert observation.deck_counts[0] == 32
                resolved = True
            if action is None:
                action = (agents[observation.acting_player].select_action(
                    observation, actions) if resolved else
                    next((a for a in actions if a.kind in ("pass", "place", "end_phase")),
                         actions[0]))
            observation = env.step(action)
    pytest.fail("Sangan / Skill Drain duel did not terminate")
