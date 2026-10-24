# Initial policy and imitation pipeline

`LegalActionPolicy` scores the legal options supplied by `GoatEnvironment`. It uses only the `Observation` and `Action` values that baseline agents receive. A sorted vocabulary comes from the pinned GOAT whitelist; hidden or absent card identities map to token 0 and visible cards missing from that vocabulary map to an unknown token. The model embeds visible cards, their zones, owners, and positions; pools them into a state vector; then scores each action using its kind, referenced card, selected-card identities, and numeric parameters. It returns one logit per legal action, with no fixed option count or model access to native core state. `PolicyAgent` chooses the highest-scoring legal action through the common agent API.

This is a first representation, not a validated strong architecture. It does not yet model public event history, known opponent cards, restrictions, deck composition, detailed target locations for multi-card choices, or individual Damage Step substeps. Unknown card IDs share one embedding. The model does not infer hidden hands or deck order. It currently scores one decision at a time; batched inference, recurrent memory, and action-set attention remain open experiments.

Install the optional ML dependency and record a native fixture duel:

```bash
python -m pip install -e '.[dev,ml]'
python examples/play_vanilla.py --seed 42 --trajectory replays/vanilla_42.json
python scripts/train_behavioral_clone.py replays/vanilla_42.json \
  --output checkpoints/vanilla_bc.pt --epochs 1 --seed 42
```

The training command first replays every input trajectory against the selected pinned native engine, checking each visible observation, legal-action list, chosen action, result, deck hash, and loaded asset hashes. It requires fingerprinted schema-v3 recordings. Use `--engine experimental` for an experimental-adapter trajectory. It then fits cross-entropy to selected actions and saves a versioned checkpoint containing model weights, card vocabulary, seed, PyTorch version, source counts, trajectory hashes, and epoch losses. Generated replays and checkpoints live in ignored directories. Only ingest demonstrations whose use is authorized.

The fixture command demonstrates software integration. Its source is random self-play, not skilled human data, and its training loss says nothing about playing strength. No human replay parser, held-out deck evaluation, self-play improvement algorithm, or trained competitive checkpoint is available yet. Before using imitation learning as a strength baseline, collect authorized human trajectories with legal actions and visibility reconstructed, split them by players/decks/matches, verify them, and measure win rate against held-out agents and deck families.

To measure a saved checkpoint against RandomAgent on seeds excluded from its training recordings:

```bash
python scripts/evaluate_policy.py checkpoints/vanilla_bc.pt --seed 43 --seeds 4 \
  --opponent random --output artifacts/vanilla_bc_eval.json
```

The evaluator refuses seeds present in checkpoint training-game metadata. It uses paired seat swaps and reports individual results, seat splits, a paired score interval, and core/deck/checkpoint hashes. `--workers 2` uses spawned native and policy workers; `--matchup DECK_A DECK_B` accepts additional deck pairs, and `--engine experimental` selects the broader unaudited adapter. A held-out seed on the same fixture decks is a protocol and baseline check; it is not held-out deck-family evaluation. See [the measured evaluation log](evaluation.md).

## Initial self-play experiment

`scripts/train_self_play.py` implements an episodic score-function policy-gradient update inspired by [Williams's REINFORCE paper](https://doi.org/10.1007/bf00992696). It samples legal actions from the current policy, plays native duels against a mixture of frozen historical policy snapshots and RandomAgent, and applies terminal rewards of +1 for a win, −1 for a loss, and 0 for a draw. A moving return baseline and entropy bonus are optional variance and exploration aids. Frozen snapshots preserve past opponents during updates; the first snapshot remains in the pool. The trainer alternates learner seats, records seeds and opponents, and can write complete player-visible trajectories with `--record-dir`. It never grants the learner access to an opponent's hidden cards.

```bash
OMP_NUM_THREADS=1 python scripts/train_self_play.py checkpoints/vanilla_bc.pt \
  --output checkpoints/vanilla_rl.pt --seed 100 --games 16 \
  --record-dir replays/vanilla_rl
python scripts/evaluate_policy.py checkpoints/vanilla_rl.pt --seed 200 --seeds 8
```

This is an experiment, not a selected final RL algorithm. Terminal reward is sparse; no value function, PPO update, opponent league, or checkpoint selection by held-out win rate exists. The first measured run from random imitation did not improve against RandomAgent; see [the evaluation log](evaluation.md). Future work should compare stronger demonstrations, a richer action encoder, value baselines and PPO under the same held-out schedule, while keeping training opponents separate from evaluation opponents.
