"""Unfinished human duels may teach choices without a fabricated outcome."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import torch

from goat_ai.replay.live_journal import read_live_journal_prefix, snapshot_live_journal
from scripts.create_viewer_game import GameCreator, ROOT
from scripts.live_human_game import LiveGameManager


DECK1 = "goat_control_rhymus_lizo_new_jersey_2005.ydk"
DECK2 = "chaos_bryan_coronel_new_jersey_2005.ydk"


def _saved_journal(tmp_path: Path, native_root: Path) -> tuple[Path, Path]:
    decks = tmp_path / "examples/decks"
    decks.mkdir(parents=True)
    for name in (DECK1, DECK2):
        shutil.copyfile(ROOT / "examples/decks" / name, decks / name)
    manager = LiveGameManager(GameCreator(root=tmp_path, native_root=native_root))
    try:
        state = manager.start({"deck1": DECK1, "deck2": DECK2, "human_seat": 0,
                               "opponent": "random", "seed": 4322})
        for kind in ("set_monster", "place"):
            index = next(index for index, action in enumerate(state["legal_actions"])
                         if action["kind"] == kind)
            state = manager.choose(state["id"], index, state["decisions"],
                                   manual=kind == "set_monster")
        path = manager.creator.output_dir / "_in_progress" / f"{state['id']}.json"
        assert path.is_file()
        return path, decks
    finally:
        manager.close_all()


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_verified_live_prefix_keeps_only_human_choices_and_freezes_journal(tmp_path):
    native = Path(os.environ["GOAT_AI_NATIVE_ROOT"]).resolve()
    journal, decks = _saved_journal(tmp_path, native)
    snapshot = snapshot_live_journal(journal, tmp_path / "private_snapshots")
    prefix = read_live_journal_prefix(snapshot, decks, native)
    assert prefix.verified_decisions >= 4
    assert len(prefix.records) == 1
    assert prefix.records[0].selected_action.kind == "set_monster"
    assert prefix.manual_indices == (2,)
    assert prefix.records[0].observation.viewer == prefix.human_seat == 0
    assert prefix.records[0].observation.opponent_hand_count == 5
    assert prefix.opponent_checkpoint_sha256 is None
    assert snapshot.name == f"{prefix.journal_sha256}.json"
    journal.write_text("changed", encoding="utf-8")
    assert read_live_journal_prefix(snapshot, decks, native) == prefix


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_live_prefix_rejects_changed_hashes_and_forged_human_origin(tmp_path):
    native = Path(os.environ["GOAT_AI_NATIVE_ROOT"]).resolve()
    journal, decks = _saved_journal(tmp_path, native)
    original = json.loads(journal.read_text())
    changed = dict(original)
    changed["entries"] = [dict(entry) for entry in original["entries"]]
    changed["entries"][2]["observation_sha256"] = "0" * 64
    journal.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="differs at decision 2"):
        read_live_journal_prefix(journal, decks, native)
    changed["entries"][2] = dict(original["entries"][2])
    changed["entries"][1]["origin"] = "manual"
    journal.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid decision origin at decision 1"):
        read_live_journal_prefix(journal, decks, native)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_behavioral_clone_accepts_only_verified_partial_human_choices(tmp_path):
    native = Path(os.environ["GOAT_AI_NATIVE_ROOT"]).resolve()
    journal, _decks = _saved_journal(tmp_path, native)
    output = tmp_path / "human_prefix.pt"
    result = subprocess.run([
        sys.executable, str(ROOT / "scripts/train_behavioral_clone.py"),
        "--human-journal", str(journal), "--native-root", str(native),
        "--engine", "experimental", "--output", str(output),
        "--feature-version", "23", "--epochs", "1", "--batch-size", "1",
    ], cwd=ROOT, env={**os.environ, "PYTHONPATH": f"{ROOT / 'src'}:{ROOT}"},
        capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr[-2000:]
    checkpoint = torch.load(output, map_location="cpu", weights_only=True)
    assert checkpoint["new_source_decisions"] == {"human_live_prefix": 1}
    assert checkpoint["training_games"][0]["partial_duel"] is True
    assert checkpoint["training_games"][0]["outcome"] is None
    assert checkpoint["training_games"][0]["manual_decision_indices"] == (2,)
