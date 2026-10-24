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
