"""Run one real vanilla-fixture duel through a narrow all-pass native policy."""

import argparse
import json
from pathlib import Path

from goat_ai.engine.native_messages import decode_decision
from goat_ai.engine.ocgcore_probe import GOAT_FLAGS, OcgcoreProbe
from goat_ai.engine.probe_deck import VANILLA_DECK


def run(native_root: Path, seed: int, max_decisions: int = 1000) -> dict:
    with OcgcoreProbe(native_root / "build/libocgcore.so",
                      native_root / "database/cards.cdb", native_root / "scripts") as probe:
        probe.first_decision(seed, VANILLA_DECK)
        for index in range(max_decisions):
            decision = decode_decision(probe._pending_message)
            # On the vanilla fixture, these choices pass chain priority, end
            # each main phase, and discard the first card at hand limit.
            action = next((choice for choice in decision.choices
                           if choice.kind == "end_phase"), decision.choices[0])
            transition = probe.respond(action.response)
            if transition.terminal:
                return {"seed": seed, "decisions": index + 1, "winner": transition.winner,
                        "core_version": probe.version, "ruleset_flags": GOAT_FLAGS,
                        "policy": "pass_only_vanilla"}
    raise RuntimeError(f"duel did not finish within {max_decisions} decisions")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-root", type=Path, default=Path(".cache/goat-ai"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(json.dumps(run(args.native_root, args.seed), indent=2))


if __name__ == "__main__":
    main()
