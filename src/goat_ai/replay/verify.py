"""Check that a recorded decision sequence reproduces on a rules engine."""

from dataclasses import asdict
from pathlib import Path

from goat_ai.engine.protocol import RulesEngine
from goat_ai.replay.fingerprint import sha256_file
from goat_ai.replay.trajectory import Trajectory


class ReplayMismatch(ValueError):
    """A recorded trajectory differs from the engine at a decision or result."""


def verify_trajectory(trajectory: Trajectory, engine: RulesEngine,
                      deck_paths: tuple[str | Path, str | Path] | None = None) -> int:
    """Replay exact actions; return the number of verified decisions.

    ``deck_paths`` can relocate a trajectory's two YDK files. The caller must
    supply the same deck contents and pinned engine assets used for recording.
    Every observation and complete legal-action list is compared before an
    action is sent, so an unsupported native request cannot pass silently.
    """
    if trajectory.ruleset != engine.ruleset.name:
        raise ReplayMismatch("ruleset differs from recorded trajectory")
    if trajectory.rules_profile is not None and trajectory.rules_profile != asdict(engine.ruleset):
        raise ReplayMismatch("rules profile differs from recorded trajectory")
    from goat_ai.environments import GoatEnvironment

    paths = deck_paths or trajectory.decks
    if trajectory.deck_sha256 is not None:
        try:
            hashes = tuple(sha256_file(path) for path in paths)
        except OSError as exc:
            raise ReplayMismatch(f"recorded deck file unavailable: {exc}") from exc
        if hashes != trajectory.deck_sha256:
            raise ReplayMismatch("deck contents differ from recorded trajectory")
    with GoatEnvironment(str(paths[0]), str(paths[1]), trajectory.seed, engine) as env:
        observation = env.reset()
        for index, record in enumerate(trajectory.decisions):
            if env.is_terminal():
                raise ReplayMismatch(f"decision {index}: engine terminated early")
            if observation != record.observation:
                raise ReplayMismatch(f"decision {index}: observation differs")
            if env.legal_actions() != record.legal_actions:
                raise ReplayMismatch(f"decision {index}: legal actions differ")
            observation = env.step(record.selected_action)
        if not env.is_terminal():
            raise ReplayMismatch("record ended before engine terminal state")
        if env.result() != trajectory.winner:
            raise ReplayMismatch("winner differs from recorded trajectory")
        if trajectory.asset_sha256 is not None:
            manifest = getattr(engine, "replay_manifest", None)
            if manifest is None or manifest() != trajectory.asset_sha256:
                raise ReplayMismatch("native assets differ from recorded trajectory")
    return len(trajectory.decisions)
