"""A sourced 2008 Synchro pair in MR1; not a complete Edison rules test."""

import hashlib
import json
import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.mr1_synchro_probe import (
    BOKOICHI,
    JUNK_SYNCHRON,
    JUNK_WARRIOR,
    Mr1SynchroProbeEngine,
)
from goat_ai.engine.ocgcore_probe import MR1_FLAGS
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory
from scripts.record_mr1_synchro_probe import select_setup_action
from scripts.render_replay import render_replay

ROOT = Path(__file__).resolve().parents[1]
DECK = ROOT / "examples/decks/mr1_junk_warrior_probe.ydk"
OPPONENT = ROOT / "examples/decks/vanilla_reverse.ydk"


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_mr1_junk_warrior_synchro_complete_duel(tmp_path):
    native_root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    engine = Mr1SynchroProbeEngine(native_root)
    with GoatEnvironment(str(DECK), str(OPPONENT), seed=3, engine=engine) as env:
        view = env.reset()
        agents = (RandomAgent(3), RandomAgent(4))
        summoned_at = None
        for index in range(5000):
            actions = env.legal_actions()
            action = (select_setup_action(view, actions) if summoned_at is None else
                      agents[view.acting_player].select_action(view, actions))
            view = env.step(action)
            if summoned_at is None and any(card.code == JUNK_WARRIOR
                                           for card in view.field):
                summoned_at = index + 1
                assert view.acting_player == 0
                assert {card.code for card in view.graveyards[0]} >= {
                    JUNK_SYNCHRON, BOKOICHI}
            if env.is_terminal():
                break
        else:
            pytest.fail("MR1 Synchro duel exceeded decision cap")
        trajectory = env.trajectory()
        assert engine.probe.flags == MR1_FLAGS
        assert engine.probe.loaded_script_sha256["utility.lua"] == hashlib.sha256(
            (native_root / "scripts/utility.lua").read_bytes()).hexdigest()
        assert "official/c63977008.lua" in engine.probe.loaded_script_sha256
        assert "official/c60800381.lua" in engine.probe.loaded_script_sha256
    assert summoned_at == 55
    assert len(trajectory.decisions) == 1439
    assert trajectory.winner == 1
    assert trajectory.ruleset == "mr1-synchro-protocol"
    path = tmp_path / "mr1_synchro.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    assert verify_trajectory(loaded, Mr1SynchroProbeEngine(native_root)) == 1439
    assert audit_trajectory_visibility(loaded)["decisions"] == 1439
    output = tmp_path / "mr1_synchro.html"
    assert render_replay(path, output, native_root, reviewer_reveal=True)[0] == 1439
    review = json.loads(output.with_suffix(".review.json").read_text())
    assert review["source_trajectory_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert len(review["frames"]) == 1440
    assert any(JUNK_WARRIOR in frame["extra"][0] for frame in review["frames"])


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_mr1_synchro_probe_rejects_unsourced_extra_card(tmp_path):
    native_root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck = tmp_path / "stardust.ydk"
    deck.write_text(DECK.read_text().replace(str(JUNK_WARRIOR), "44508094"))
    with (GoatEnvironment(str(deck), str(OPPONENT), seed=3,
                          engine=Mr1SynchroProbeEngine(native_root)) as env,
          pytest.raises(ValueError, match="Junk Warrior")):
        env.reset()
