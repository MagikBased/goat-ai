"""Skill Drain chained to Dekoichi's Flip Effect prevents its draw."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

DEKOICHI = 87621407
SKILL_DRAIN = 82732705


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("activate_drain", [False, True])
def test_dekoichi_flip_draw_against_chained_skill_drain(tmp_path, activate_drain):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (DEKOICHI, SKILL_DRAIN):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    flip_deck = tmp_path / "dekoichi.ydk"
    flip_deck.write_text("#main\n" + "\n".join(map(str, (
        DEKOICHI, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    drain_deck = tmp_path / "skill_drain.ydk"
    drain_deck.write_text("#main\n" + "\n".join(map(str, (
        SKILL_DRAIN, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(flip_deck), str(drain_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        set_flip = set_drain = flipped = responded = resolved = False
        deck_before = None
        for _ in range(125):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not set_flip:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == DEKOICHI), None)
                set_flip |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not set_drain:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SKILL_DRAIN), None)
                set_drain |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not flipped:
                action = next((a for a in actions if a.kind == "flip_summon"
                               and a.parameters.get("code") == DEKOICHI), None)
                if action is not None:
                    flipped = True
                    deck_before = obs.deck_counts[0]
            if (flipped and not responded and obs.acting_player == 1
                    and [link.card_code for link in obs.chain] == [DEKOICHI]):
                drain = next((a for a in actions if a.kind == "chain"
                              and a.parameters.get("code") == SKILL_DRAIN), None)
                assert drain is not None
                responded = True
                if activate_drain:
                    action = drain
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if responded and not resolved and obs.turn == 3 and obs.acting_player == 0 \
                    and not obs.chain and any(a.kind == "end_phase" for a in env.legal_actions()):
                resolved = True
                assert obs.deck_counts[0] == deck_before - (0 if activate_drain else 1)
                assert obs.life_points[1] == (7000 if activate_drain else 8000)
                assert any(c.code == DEKOICHI and c.position == "faceup"
                           for c in obs.field)
                assert (SKILL_DRAIN in {c.code for c in obs.field}) == activate_drain
                break
        assert set_flip and set_drain and flipped and responded and resolved
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(5000):
            if env.is_terminal():
                break
            obs = env.step(agents[obs.acting_player].select_action(
                obs, env.legal_actions()))
        assert env.is_terminal()
        path = tmp_path / f"dekoichi_drain_{activate_drain}.json"
        write_trajectory(path, env.trajectory())
        saved = read_trajectory(path)
        assert verify_trajectory(saved, ExperimentalOcgcoreEngine(root)) == len(
            saved.decisions)
        assert audit_trajectory_visibility(saved)["decisions"] == len(saved.decisions)
