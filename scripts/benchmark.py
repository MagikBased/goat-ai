"""Real-duel benchmark entry point; refuses to report fabricated performance."""

from goat_ai.engine import SimulatorUnavailable
from goat_ai.environments import GoatEnvironment


def main() -> None:
    try:
        GoatEnvironment("deck1.ydk", "deck2.ydk").reset()
    except SimulatorUnavailable as exc:
        raise SystemExit(f"No valid duel benchmark is available: {exc}") from exc


if __name__ == "__main__":
    main()

