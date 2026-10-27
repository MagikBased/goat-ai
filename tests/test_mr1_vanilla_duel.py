"""MR1 protocol regression; these fixtures do not certify Edison gameplay."""

import hashlib
import os
from dataclasses import replace
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.mr1_vanilla_adapter import Mr1VanillaEngine
from goat_ai.engine.ocgcore_probe import MR1_FLAGS
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory
from scripts.render_replay import render_replay

ROOT = Path(__file__).resolve().parents[1]
DECKS = (ROOT / "examples/decks/vanilla_probe.ydk",
         ROOT / "examples/decks/vanilla_reverse.ydk")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_mr1_vanilla_complete_duel_replay_and_visibility(tmp_path):
    native_root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    engine = Mr1VanillaEngine(native_root)
    with GoatEnvironment(*(str(deck) for deck in DECKS), seed=42, engine=engine) as env:
        view = env.reset()
        assert engine.probe.flags == MR1_FLAGS
        assert engine.probe.loaded_script_sha256["utility.lua"] == hashlib.sha256(
            (native_root / "scripts/utility.lua").read_bytes()).hexdigest()
        agents = (RandomAgent(42), RandomAgent(43))
        for _ in range(5000):
            actions = env.legal_actions()
            assert actions
            if view.turn == 1 and view.phase == "draw":
                assert view.life_points == (8000, 8000)
            view = env.step(agents[view.acting_player].select_action(view, actions))
            if env.is_terminal():
                break
        else:
            pytest.fail("MR1 vanilla duel exceeded decision cap")
        trajectory = env.trajectory()
    assert trajectory.ruleset == "mr1-vanilla-protocol"
    assert trajectory.rules_profile["april_2005_banlist"] is False
    assert len(trajectory.decisions) == 1368
    assert trajectory.winner == 1
    path = tmp_path / "mr1_vanilla.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    assert verify_trajectory(loaded, Mr1VanillaEngine(native_root)) == 1368
    assert audit_trajectory_visibility(loaded)["decisions"] == 1368
    assert render_replay(path, tmp_path / "mr1_vanilla.html", native_root,
                         reviewer_reveal=True)[0] == 1368


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_mr1_vanilla_rejects_effect_deck_and_illegal_action(tmp_path):
    native_root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    with GoatEnvironment(*(str(deck) for deck in DECKS), seed=42,
                         engine=Mr1VanillaEngine(native_root)) as env:
        env.reset()
        action = env.legal_actions()[0]
        with pytest.raises(ValueError, match="illegal action"):
            env.step(replace(action, id="invalid"))
    bad = tmp_path / "effect.ydk"
    bad.write_text(DECKS[0].read_text().replace("15025844", "55144522", 1))
    with (GoatEnvironment(str(bad), str(DECKS[1]), seed=42,
                          engine=Mr1VanillaEngine(native_root)) as env,
          pytest.raises(ValueError, match="Normal Monster")):
        env.reset()


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_mr1_vanilla_opening_view_hides_opponent_deck_identity(tmp_path):
    native_root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    changed_deck = tmp_path / "different_opponent.ydk"
    changed_deck.write_text(DECKS[0].read_text().replace("15025844", "32864", 1))
    with (GoatEnvironment(str(DECKS[0]), str(DECKS[0]), seed=42,
                          engine=Mr1VanillaEngine(native_root)) as same,
          GoatEnvironment(str(DECKS[0]), str(changed_deck), seed=42,
                          engine=Mr1VanillaEngine(native_root)) as different):
        same_view = same.reset()
        different_view = different.reset()
        assert same_view.acting_player == different_view.acting_player == 0
        assert same_view == different_view
        assert same.legal_actions() == different.legal_actions()
