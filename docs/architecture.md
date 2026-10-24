# Architecture and engine contract

`GoatEnvironment` validates action membership and delegates every rules transition to a `RulesEngine`. `Decision` returns one acting player's `Observation` and its variable-length legal `Action` tuple. The current default engine raises `SimulatorUnavailable`; no custom Yu-Gi-Oh! rules are simulated in Python. The restricted `RestrictedOcgcoreEngine` now connects a [native core](native_setup.md) to this environment for normal-monster fixture decks and Pot of Greed. General response decoding and complete observation coverage are still unfinished, so the default remains fail-closed.

The observation schema has explicit visible zones, public counts and history, own hand, and known opponent cards. It has no opponent hand identities or deck order. Schema shape alone cannot prove the native adapter redacts data. The native adapter must use the engine's player-scoped queries, hide facedown cards where appropriate, and test identical visible states with different hidden cards. Action IDs are local to a decision and must map to the exact native response payload; effects with targets or multiple choices may take several decisions.

## Next adapter implementation

1. Pin ocgcore, card database, and script revisions with checksums. Build the native core outside this repository or as a separately licensed optional package.
2. Start duels with `DUEL_MODE_GOAT`, 8000 LP, five starting cards, one draw per turn, and seeded PRNG. Parse `.ydk` and verify the April 2005 banlist and card pool before duel creation.
3. Parse every core request message into legal actions, including card/effect selection, chained responses, targets, positions, tribute choices, attacks, and phase transitions. Map each selected action back to exact response bytes; reject overflow or unsupported messages explicitly.
4. Construct player-scoped observations from native queries. Test hidden opponent hands, deck order, facedown identities, and privately revealed information. Capture public history and known-card memory only through observed events.
5. Run a complete duel with two random agents; add historical ruling fixtures. Then add multiworker runs and measured benchmarks.

Do not use `ygoenv`'s current EDOPro binary as a GOAT engine: its source currently selects MR5. The direct `ctypes` probe reaches real native decisions without a fixed option-list size, so it is the current M1 adapter direction. Its response protocol and visibility boundary are only partially implemented. The interface avoids coupling downstream agent and replay code to this choice.

Trajectory JSON schema v1 stores the visible observation, full legal action list, chosen action, acting player and phase (inside the observation), deck identifiers, ruleset, source, optional skill metadata, and result. It excludes native full-state snapshots. A future training process can map variable-length actions to masked scores; any PyTorch encoder and algorithm remain independent of the simulator.

