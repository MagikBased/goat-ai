# GOAT AI

Research foundation for a general-purpose Yu-Gi-Oh! GOAT Format agent. **This repository does not yet run a GOAT duel.** The Python environment API, baseline agents, and trajectory format are implemented, but the historical rules engine adapter is unfinished and fails explicitly. No training or playing strength is claimed.

## Status

| Component | Status |
| --- | --- |
| Engine selection and source review | Initial research complete |
| Native GOAT-mode startup | First decision reached with pinned core/assets; historical correctness unverified |
| Complete headless duel | Narrow vanilla-fixture smoke duel reaches terminal; general adapter unfinished |
| Environment contract and illegal-action validation | Implemented |
| Player-visible observation schema | Implemented; native hand/facedown redaction tested on fixture |
| Random, heuristic, CLI human agents | Implemented against contract |
| JSON trajectory round trip | Implemented |
| Real duel, tournaments, throughput benchmarks | Blocked on engine adapter |

The selected direction is [Project Ignis/edo9300 ocgcore](https://github.com/edo9300/ygopro-core), configured with its `DUEL_MODE_GOAT` flag, historical card data and scripts, and an audited Python-facing decision adapter. A 2005 banlist alone is insufficient. See [research](docs/research.md), [architecture](docs/architecture.md), and [roadmap](docs/roadmap.md).

## Install and check

Requires Python 3.10+. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest
python examples/show_contract.py
```

PyTorch is an optional future training dependency: `python -m pip install -e '.[ml]'`. No PyTorch model or training algorithm is implemented yet.

The API is `GoatEnvironment(player1_deck, player2_deck, seed, engine=...)`; `reset()`, `legal_actions()`, `step()`, `is_terminal()`, and `result()` are defined. Without an audited engine, `reset()` raises `SimulatorUnavailable` with the outstanding integration tasks. This is intentional: it prevents a modern-rules duel from being presented as GOAT.

## Native first-decision probe (Linux)

The separate M0 probe calls a real, pinned ocgcore build with `DUEL_MODE_GOAT`. It is **not yet connected to `GoatEnvironment`** and its raw messages must not be passed to an agent because their visibility has not been audited. It uses a 40-card normal-monster fixture to verify startup and the first-turn draw; full deck legality is planned for M1.

```bash
python -m pip install -e '.[dev,native]'
python scripts/setup_native.py
python scripts/probe_native.py --seed 42
python scripts/run_native_smoke.py --seed 42
GOAT_AI_NATIVE_ROOT=.cache/goat-ai python -m pytest -q tests/test_ocgcore_probe.py
```

Setup downloads and builds external dependencies under ignored `.cache/goat-ai/`. See [native setup](docs/native_setup.md) for pinned revisions, licensing, and the probe's limits.

The smoke runner validates its 40-card fixture against a pinned Project Ignis GOAT whitelist, decodes empty chain windows, idle choices, and single-card selections, then ends turns and discards at hand limit until the native core reports a winner. This is a protocol regression for one simple fixture, not a general GOAT environment or an agent-strength benchmark.

## Contributions and data

Original code is MIT licensed. Third-party engines, scripts, and card databases are separate dependencies under their own licenses and are not vendored here. Do not commit replay collections, models, card databases, or binaries. Only ingest gameplay data you have permission to use.

