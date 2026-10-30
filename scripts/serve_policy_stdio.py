"""Serve a policy over one JSON decision request per input line."""

import argparse
import sys
from pathlib import Path

from goat_ai.interop import decode_request, select_response
from goat_ai.training import load_policy_agent

MAX_LINE_BYTES = 8 * 1024 * 1024


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    args = parser.parse_args()
    agent = load_policy_agent(args.checkpoint)
    while line := sys.stdin.buffer.readline(MAX_LINE_BYTES + 1):
        if len(line) > MAX_LINE_BYTES or not line.endswith(b"\n"):
            print("decision request exceeds line limit or lacks newline", file=sys.stderr)
            return 2
        try:
            response = select_response(agent, decode_request(line))
        except (ValueError, TypeError, KeyError) as error:
            print(f"invalid decision request: {error}", file=sys.stderr)
            return 2
        print(response, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
