# Initial policy and imitation pipeline

`LegalActionPolicy` scores the legal options supplied by `GoatEnvironment`. It uses only the `Observation` and `Action` values that baseline agents receive. A sorted vocabulary comes from the pinned GOAT whitelist; hidden or absent card identities map to token 0 and visible cards missing from that vocabulary map to an unknown token. The model embeds visible cards, their zones, owners, and positions; pools them into a state vector; then scores each action using its kind, referenced card, selected-card identities, and numeric parameters. It returns one logit per legal action, with no fixed option count or model access to native core state. Feature version 2 also encodes each selected target's visible controller, zone, and slot, including when its card identity is hidden. Target presence has its own mask so hidden IDs are not mistaken for padding. Feature version 3 resolves a face-down opponent card's ID from `known_opponent_field_cards` only when its controller, field zone, and slot match a public memory entry; it applies this to state and action card features. Feature version 4 adds a public disabled-zone bitmask to the state and represents each selected field zone as a structured target, with new action kinds for multi-zone prompts. Older checkpoints retain their versioned encoder and weights. Existing checkpoints without a feature version load with the original version-1 encoder. The encoder does not yet use historical public Deck reveals or all restrictions. `PolicyAgent` uses scores through the common agent API. Inference version 2 also applies a generic liveness guard at multi-step selections: it avoids a legal `cancel` when another choice is available, finishes a selection instead of unselecting when possible, and avoids immediately unselecting the card it just selected if another card can be selected. These choices can change strategy; reports identify the inference and feature versions.

This is a first representation, not a validated strong architecture. It does not yet model public event history, other private reveals, restrictions, deck composition, or individual Damage Step substeps. Unknown card IDs share one embedding. Target context is pooled and may still lose relationships among cards. The model does not infer hidden hands or deck order. It currently scores one decision at a time; batched inference, recurrent memory, and action-set attention remain open experiments.

Install the optional ML dependency and record a native fixture duel:

```bash
python -m pip install -e '.[dev,ml]'
python examples/play_vanilla.py --seed 42 --trajectory replays/vanilla_42.json
python scripts/train_behavioral_clone.py replays/vanilla_42.json \
  --output checkpoints/vanilla_bc.pt --epochs 1 --seed 42
```

The training command first replays every input trajectory against the selected pinned native engine, checking each visible observation, legal-action list, chosen action, result, deck hash, and loaded asset hashes. It requires fingerprinted schema-v3 through v9 recordings. Use `--engine experimental` for an experimental-adapter trajectory. It then fits cross-entropy to selected actions and saves a versioned checkpoint containing model weights, card vocabulary, seed, PyTorch version, source counts, trajectory hashes, and epoch losses. Generated replays and checkpoints live in ignored directories. Only ingest demonstrations whose use is authorized.

The fixture command demonstrates software integration. Its source is random self-play, not skilled human data, and its training loss says nothing about playing strength. No automated EDOPro or DuelingBook human replay parser, authorized tournament human dataset, or trained competitive checkpoint is available yet. Before using human imitation as a strength baseline, collect authorized trajectories with legal actions and visibility reconstructed, split them by players/decks/matches, verify them, and measure win rate against held-out agents and deck families.

A local version-3 pipeline check on 2026-10-24 replay-verified a schema-v6 vanilla duel with seed 42 and 1,368 decisions, trained one epoch at width 16 with mean decision loss 0.5268, then loaded the checkpoint for seat-swapped inference on seeds 43–44. It won 2/4 against RandomAgent, with both wins in the second seat. This is a protocol check on two seeds and random demonstration labels, not evidence of stronger play. The replay and checkpoint were kept under ignored `.cache/goat-ai/`.

A version-4 pipeline check on 2026-10-24 replay-verified the schema-v9 Ground Collapse fixture produced by `examples/record_ground_collapse.py`: 1,126 decisions, including one selected two-zone action and 1,119 observations with disabled-zone state. One epoch at width 16 and seed 17 completed with mean decision loss 0.5452. The demonstration is mostly random play and the resulting checkpoint has no held-out strength evaluation. This verifies training compatibility with the new action and observation fields only.

## Seat-labeled demonstrations

A full-duel trajectory can name `skill_metadata.demonstrator_seat` as 0 or 1. Behavioral cloning verifies the **entire** native replay, then uses only that seat's selected actions as labels. This prevents an opponent's random decisions from contaminating a heuristic or human demonstration. The CLI human player in `examples/play_vanilla.py --human-seat 0` records `source=human_cli`, `authorization=self_recorded`, and the selected seat when a trajectory path is supplied. This is a local interactive recording path; it does not parse tournament videos or third-party replays.

For a controlled baseline, collect heuristic decisions against RandomAgent in both seats and train on only those decisions:

```bash
python scripts/collect_heuristic_demos.py --seed 1000 --seeds 4 \
  --output-dir replays/heuristic_1000_1003
OMP_NUM_THREADS=1 python scripts/train_behavioral_clone.py \
  replays/heuristic_1000_1003/*.json \
  --output checkpoints/heuristic_bc_1000_1003.pt \
  --epochs 3 --width 32 --seed 17 --learning-rate 0.001
python scripts/evaluate_policy.py checkpoints/heuristic_bc_1000_1003.pt \
  --seed 2000 --seeds 8 --opponent random
```

This teacher is the project's generic `HeuristicAgent`, not a human player. The measured results and limits are in [the evaluation log](evaluation.md). The same schema can hold authorized human choices, but card-by-card historical correctness and broad visibility coverage still need expansion before using the experimental adapter for research training.

To measure a saved checkpoint against RandomAgent on seeds excluded from its training recordings:

```bash
python scripts/evaluate_policy.py checkpoints/vanilla_bc.pt --seed 43 --seeds 4 \
  --opponent random --output artifacts/vanilla_bc_eval.json
```

The evaluator refuses seeds present in checkpoint training-game metadata. It uses paired seat swaps and reports individual results, seat splits, a paired score interval, and core/deck/checkpoint hashes. `--opponent-checkpoint PATH` compares two saved policies and checks both checkpoints' training seeds. `--workers 2` uses spawned native and policy workers; `--matchup DECK_A DECK_B` accepts additional deck pairs, and `--engine experimental` selects the broader unaudited adapter. A held-out seed on the same fixture decks is a protocol and baseline check; it is not held-out deck-family evaluation. See [the measured evaluation log](evaluation.md).

## Initial self-play experiment

`scripts/train_self_play.py` implements an episodic score-function policy-gradient update inspired by [Williams's REINFORCE paper](https://doi.org/10.1007/bf00992696). It samples legal actions from the current policy, plays native duels against a mixture of frozen historical policy snapshots and RandomAgent, and applies terminal rewards of +1 for a win, −1 for a loss, and 0 for a draw. A moving return baseline and entropy bonus are optional variance and exploration aids. Frozen snapshots preserve past opponents during updates; the first snapshot remains in the pool. The trainer alternates learner seats, records seeds and opponents, and can write complete player-visible trajectories with `--record-dir`. It never grants the learner access to an opponent's hidden cards.

```bash
OMP_NUM_THREADS=1 python scripts/train_self_play.py checkpoints/vanilla_bc.pt \
  --output checkpoints/vanilla_rl.pt --seed 100 --games 16 \
  --record-dir replays/vanilla_rl
python scripts/evaluate_policy.py checkpoints/vanilla_rl.pt --seed 200 --seeds 8
```

This is an experiment, not a selected final RL algorithm. Terminal reward is sparse; no value function, PPO update, opponent league, or checkpoint selection by held-out win rate exists. Runs from random imitation and from the stronger heuristic imitation checkpoint did not demonstrate an improvement in greedy playing strength; see [the evaluation log](evaluation.md). Future work should compare a richer action encoder, value baselines and PPO under the same held-out schedule, while keeping training opponents separate from evaluation opponents.
