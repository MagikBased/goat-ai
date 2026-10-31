#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
client="${GOAT_AI_EDOPRO_CLIENT:-$project_root/.cache/goat-ai/edopro_probe/ProjectIgnis/EDOPro}"

if [[ ! -x "$client" ]]; then
    printf 'EDOPro client is missing or not executable: %s\n' "$client" >&2
    printf 'Install EDOPro locally, then set GOAT_AI_EDOPRO_CLIENT to its executable path.\n' >&2
    exit 1
fi

"$project_root/start_review_viewer.sh" --game-creator "$@"
client_dir="$(cd -- "$(dirname -- "$client")" && pwd)"
client_name="$(basename -- "$client")"
cd -- "$client_dir"
exec "./$client_name"
