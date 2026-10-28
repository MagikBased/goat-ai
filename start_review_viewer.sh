#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python="$project_root/.venv/bin/python"

if [[ ! -x "$python" ]]; then
    printf 'GOAT AI virtual environment is missing. Set it up using README.md first.\n' >&2
    exit 1
fi

exec "$python" "$project_root/scripts/launch_review_server.py" "$@"
