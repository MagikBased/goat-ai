# GOAT AI

Research foundation for a general-purpose Yu-Gi-Oh! GOAT Format agent. A restricted native adapter runs complete duels with 40-card normal-monster decks and one tested spell, Pot of Greed. General effect-card support and historical rules validation are unfinished. No training or playing strength is claimed.

## Status

| Component | Status |
| --- | --- |
| Engine selection and source review | Initial research complete |
| Native GOAT-mode startup | First decision reached with pinned core/assets; historical correctness unverified |
| Complete headless duel | Restricted native adapter reaches terminal through `GoatEnvironment`; general card support unfinished |
| Environment contract and illegal-action validation | Implemented |
| Player-visible observation schema | Implemented; native hand/facedown redaction tested on fixture |
| Random, heuristic, CLI human agents | Implemented; random agent completes vanilla native duels |
| JSON trajectory round trip | Implemented and verified on a native random-agent duel |
| Tournaments | Pending general card support and evaluation harness |
| Native throughput benchmark | Implemented for vanilla fixture only; see `docs/benchmarks.md` |

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

The API is `GoatEnvironment(player1_deck, player2_deck, seed, engine=...)`; `reset()`, `legal_actions()`, `step()`, `is_terminal()`, `result()`, and `trajectory()` are defined. Pass `RestrictedOcgcoreEngine` for the restricted native path. The default engine raises `SimulatorUnavailable` because general GOAT support is unfinished.

## Native setup (Linux)

The M0 probe calls a real, pinned ocgcore build with `DUEL_MODE_GOAT`. Its raw messages stay inside the adapter. The restricted adapter uses player-visible queries and redacts hidden card identities in observations and action parameters. Visibility coverage remains limited to the vanilla fixture.

```bash
python -m pip install -e '.[dev,native]'
python scripts/setup_native.py
python scripts/probe_native.py --seed 42
python scripts/run_native_smoke.py --seed 42
GOAT_AI_NATIVE_ROOT=.cache/goat-ai python -m pytest -q tests/test_ocgcore_probe.py
```

Setup downloads and builds external dependencies under ignored `.cache/goat-ai/`. See [native setup](docs/native_setup.md) for pinned revisions, licensing, and the probe's limits.

The smoke runner validates its 40-card fixture against a pinned Project Ignis GOAT whitelist, decodes empty chain windows, idle choices, and single-card selections, then ends turns and discards at hand limit until the native core reports a winner. This is a protocol regression for one simple fixture, not a general GOAT environment or an agent-strength benchmark.

The restricted `RestrictedOcgcoreEngine` connects the same native core to `GoatEnvironment` for 40-card normal-monster decks, optionally containing Pot of Greed. To run a real duel between two fixture decks with a `RandomAgent`:

```bash
python examples/play_vanilla.py --seed 42 --trajectory replays/vanilla_42.json
python examples/play_vanilla.py --human-seat 0
python scripts/benchmark_native.py --games 3 --seed 42
```

The example prints the winner and decision count and optionally writes a JSON trajectory. `--human-seat` uses the same action API for a CLI player. Its supported decision types are limited to the requests exercised by these decks; unsupported requests fail explicitly. The default environment still fails closed because general GOAT effects and visibility cases are unfinished. The benchmark includes reset and Python action selection; results are specific to this fixture and machine.

## Contributions and data

Original code is MIT licensed. Third-party engines, scripts, and card databases are separate dependencies under their own licenses and are not vendored here. Do not commit replay collections, models, card databases, or binaries. Only ingest gameplay data you have permission to use.

