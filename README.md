# GOAT AI

Research foundation for a general-purpose Yu-Gi-Oh! GOAT Format agent. **This repository does not yet run a GOAT duel.** The Python environment API, baseline agents, and trajectory format are implemented, but the historical rules engine adapter is unfinished and fails explicitly. No training or playing strength is claimed.

## Status

| Component | Status |
| --- | --- |
| Engine selection and source review | Initial research complete |
| Historical GOAT rules in headless engine | Unfinished |
| Environment contract and illegal-action validation | Implemented |
| Player-visible observation schema | Implemented; engine redaction unverified |
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

## Contributions and data

Original code is MIT licensed. Third-party engines, scripts, and card databases are separate dependencies under their own licenses and are not vendored here. Do not commit replay collections, models, card databases, or binaries. Only ingest gameplay data you have permission to use.

