# Project plan

GOAT AI's first goal is a **verified, headless GOAT duel that two random agents can finish**. Playing strength comes after rule correctness and information isolation. This plan uses evidence gates rather than calendar dates: a milestone is complete only when its exit criteria pass on a clean checkout.

## Current baseline

The repository has a Python environment contract, observation and action types, three baseline agents, JSON trajectory serialization, and CI. The default engine raises `SimulatorUnavailable`. A restricted native adapter now completes normal-monster fixture duels; this is not a historical correctness claim. The selected engine is modern ocgcore with `DUEL_MODE_GOAT`, subject to ruling validation. See [native setup](native_setup.md).

## M0 — Prove the native engine path

**Status: complete for the first-decision prototype.** Reproduction and exact pins are in [native setup](native_setup.md). The implementation uses a direct `ctypes` binding; M1 must still decode responses and enforce player-visible observations.

**Work**

1. Pin exact ocgcore, card database, and script revisions with URLs, hashes, licenses, and reproducible setup instructions. Keep third-party artifacts out of Git.
2. Build and call the native core from a minimal Python harness. Use an explicit GOAT rules flag, 8000 LP, five opening cards, first-turn draw, and a fixed seed.
3. Inspect native decision messages, query APIs, and card/script loading. Record which message types and state queries are needed for full duels.
4. Decide between a direct C API binding and a patched ygoenv fork using a small measured prototype. The choice must preserve unrestricted legal option counts and player-scoped views.

**Exit:** A reproducible command starts a real GOAT-mode duel, reaches its first decision, and records the exact native versions and seed. A test checks the opening draw. Any unsupported message fails explicitly.

## M1 — Complete a duel safely

**Status: in progress.** A direct native binding completes 40-card normal-monster fixture duels with Pot of Greed, Book of Moon, and GOAT-variant Nobleman of Crossout. It handles optional chain choices, exposes structured public chain links and monster battle positions, and redacts the ID of a set opponent monster targeted by Nobleman. `.ydk` parsing, pinned whitelist and GOAT-variant database checks, and deterministic deck shuffling are implemented. General effect and decision coverage, independently audited historical legality, and complete player-visible observations are still required.

**Work**

1. Implement `.ydk` parsing and April 2005 deck/card-pool validation. Begin with two small legal fixture decks and expand coverage.
2. Convert each native decision request into a variable-length list of structured actions. Map selected actions to exact native responses, including multi-step targets, effect choices, chains, and phase changes.
3. Build observations solely from player-visible native queries and observed public events. Maintain known-card memory without reading hidden identities from internal state.
4. Connect the adapter to `GoatEnvironment`; run two `RandomAgent` instances through terminal states. Record decision trajectories and replay seeds.
5. Add an interactive CLI duel and a real benchmark command. Record crashes, unsupported requests, and infinite loops as failures.

**Exit:** A clean setup completes seeded random-agent duels with valid outcomes and no unhandled native messages in the fixture decks. Illegal actions are rejected. Repeated seeds reproduce action/observation/outcome traces. Changing a hidden opponent hand or deck order while holding the visible state fixed cannot change the observation supplied to the agent.

## M2 — Historical correctness gate

**Status: in progress.** The source-backed Cannon Soldier / Book of Moon fixture checks historical Ignition priority after a summon, and the GOAT Nobleman fixture checks a representative historical banish ruling. The remaining timing and card-specific cases below are untested.

**Work:** Create source-backed regression fixtures for first-turn draw, summon response and Ignition priority, chain construction and resolution, trigger ordering and missed timing, Damage Step restrictions, flip effects, summon negation, historical field spells, the April 2005 list, and representative pre-errata card rulings. Track unresolved rulings in `docs/goat_rules.md` with the chosen interpretation and evidence.

**Exit:** Every required fixture passes with pinned engine assets, or is marked as a known incompatibility that blocks a GOAT-correct claim. Run differential checks against documented examples or independently observed duels where practical. Expand the legal-card test corpus beyond the initial fixture decks.

## M3 — Evaluation and data

**Status: in progress.** A seeded tournament runner swaps seats for each deck matchup, records individual outcomes, reports seat and matchup splits, and gives Wilson intervals for decisive win rates. A restricted-fixture baseline report is in [the evaluation log](evaluation.md). Broader deck families, held-out opponents, authorized human replay reconstruction, and training/evaluation separation remain outstanding.

**Work:** Build seeded agent tournaments with deck and matchup splits, seat swaps, confidence intervals, and held-out evaluation opponents. Measure duel throughput, decisions per second, runtime memory, and initialization overhead on named hardware. Validate self-play trajectory round trips. Investigate `.yrp` and `.yrpX` reconstruction; ingest human games only when permission, legal-action recovery, and player-visible knowledge can be established.

**Exit:** A reproducible benchmark report and tournament report exist for the tested core/assets/decks. Replay support is claimed only for formats that have parser and reconstruction tests.

## M4 — Learn a competitive policy

**Work:** Implement a PyTorch policy that scores variable-length legal actions from visible observations. Establish random and heuristic baselines first. Train behavioral cloning on verified demonstrations, then self-play with a historical checkpoint pool and held-out deck families. Compare PPO or other algorithms on win rate and stability rather than selecting one in advance.

**Exit:** A versioned model beats the baseline agents over held-out seeds and decks with confidence intervals, and its decisions use no hidden engine state. Record training compute, data provenance, and evaluation protocol.

## M5 — Search and other formats

Evaluate policy-guided search and belief sampling only after M2 and M4. Search must sample hidden information from a player-consistent belief and must never inspect the real hidden state when choosing actions. Add Edison as a separately validated rules profile, not a changed banlist.

### Possible Stardust PC-port integration

Keep training in Python. Define a versioned, game-independent decision boundary: the game supplies a player-visible observation and legal actions; the agent returns an action identifier. When Stardust exposes those decisions in a PC port, implement a small C or C++ bridge and native model inference. Stardust's 2009 rules, card IDs, and action protocol need their own adapter and validation; GOAT checkpoints should not be assumed directly compatible. This is future work and does not block the GOAT milestones.

## Immediate next work item

Broaden M1 by fetching and validating effect-card scripts, decoding their decision messages, and auditing hidden-information boundaries. Begin M2 with source-backed priority and ruling fixtures before training. Keep each implementation change small enough to demonstrate with a command, test, and documented limitation.
