"""The local human recording path saves only a verified, visible duel."""

import os
import sys
from pathlib import Path

import pytest

from examples import play_goat
from goat_ai.agents import RandomAgent
from goat_ai.replay import read_trajectory


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_human_recording_path_round_trips_a_native_duel(tmp_path, monkeypatch,
                                                       capsys):
    # The test supplies deterministic input in place of a person; the artifact
    # remains in tmp_path and is never admitted as a human training sample.
    monkeypatch.setattr(play_goat, "HumanAgent", lambda **_kwargs: RandomAgent(42))
    decks = Path(__file__).resolve().parents[1] / "examples/decks"
    output = tmp_path / "recorded.json"
    monkeypatch.setattr(sys, "argv", [
        "play_goat.py", "--deck1", str(decks / "vanilla_probe.ydk"),
        "--deck2", str(decks / "vanilla_reverse.ydk"),
        "--human-seat", "0", "--opponent", "random", "--seed", "42",
        "--native-root", os.environ["GOAT_AI_NATIVE_ROOT"],
        "--trajectory", str(output),
    ])
    play_goat.main()
    saved = read_trajectory(output)
    assert saved.source == "human_cli"
    assert saved.skill_metadata["authorization"] == "self_recorded"
    assert saved.skill_metadata["demonstrator_seat"] == 0
    assert saved.skill_metadata["opponent"] == "RandomAgent"
    assert saved.winner in (0, 1, None)
    assert saved.decisions
    with pytest.raises(SystemExit) as error:
        play_goat.main()
    assert error.value.code == 2
    assert "already exists" in capsys.readouterr().err

    rejected = tmp_path / "rejected.json"
    monkeypatch.setattr(sys, "argv", [*sys.argv[:-1], str(rejected)])
    def reject_verification(*_args):
        raise ValueError("replay mismatch")
    monkeypatch.setattr(play_goat, "verify_trajectory", reject_verification)
    with pytest.raises(ValueError, match="replay mismatch"):
        play_goat.main()
    assert not rejected.exists()
    assert not list(tmp_path.glob(".rejected.json.*.tmp"))
