# Initial policy and imitation pipeline

`LegalActionPolicy` scores the legal options supplied by `GoatEnvironment`. It uses only the `Observation` and `Action` values that baseline agents receive. A sorted vocabulary comes from the pinned GOAT whitelist; hidden or absent card identities map to token 0 and visible cards missing from that vocabulary map to an unknown token. The model embeds visible cards, their zones, owners, and positions; pools them into a state vector; then scores each action using its kind, referenced card, selected-card identities, and numeric parameters. It returns one logit per legal action, with no fixed option count or model access to native core state. Feature version 2 also encodes each selected target's visible controller, zone, and slot, including when its card identity is hidden. Target presence has its own mask so hidden IDs are not mistaken for padding. Feature version 3 resolves a face-down opponent card's ID from `known_opponent_field_cards` only when its controller, field zone, and slot match a public memory entry; it applies this to state and action card features. Feature version 4 adds a public disabled-zone bitmask to the state and represents each selected field zone as a structured target, with new action kinds for multi-zone prompts. Feature version 5 separately pools card embeddings from the player's sorted initial Main Deck composition. Feature version 6 distinguishes Attribute, number, and card-name announcement actions with separate kinds; Attribute and number choices also have numeric features. Feature version 7 pairs each selected card embedding with its original slot and chosen rank, allowing distinct ordered Deck-top choices to receive different logits. Feature version 8 projects current ATK, DEF, total counters, and Spell Counter counts for face-up monsters; hidden and face-down card stats remain absent. Feature version 9 separately pools an unordered multiset of publicly known opponent hand cards from schema-v17 observations. Private draws remain unknown and no native hand slot is encoded. Feature version 10 adds an ordered recurrent encoding of the public chain card identities and controllers, so reversing two chain links changes the state representation; it does not use private native state. Feature version 11 is an equal-capacity unordered-chain ablation. Feature version 12 matches each direct or multi-card field selection to its corresponding card in the visible field, adding that card's embedding and visible current stats to the action score. This resolves an ambiguity when identical cards in different slots have different current ATK, DEF, or counters. It adds no model parameters. Opt-in feature version 13 binds each visible face-up Equip Spell to the visible card in its target monster slot and projects the paired embeddings before pooling; a representation test distinguishes two possible equip targets. Opt-in feature version 14 encodes schema-v21 public chain target slots with each link in the ordered chain, binding targets to visible field cards when present. Its target-slot embeddings reveal no hidden card IDs. A matched v13/v14 experiment found no target-specific or held-out strength gain; see [evaluation](evaluation.md). Version 10 remains the default. A first matched v12/v13 experiment found no equip-specific decision change or held-out strength gain; see [evaluation](evaluation.md). Older checkpoints retain their versioned encoder and weights. Version 9 has a representation test and a controlled sourced-deck comparison: it won 18/32 against a version-8 model trained on the same schema-v17 demonstrations, with a paired 95% interval of 40.625–71.875%; see [the evaluation log](evaluation.md). This does not establish a strength gain. Existing checkpoints without a feature version load with the original version-1 encoder. The encoder does not yet use historical public Deck reveals or all restrictions. Opt-in feature version 17 adds four action-specific numbers at an attack-target choice: the public attacker ATK, the target’s visible battle stat, their margin, and a visibility flag. It uses the acting player’s own attacker slot from schema-v22 observations and leaves face-down target stats unknown. A first matched held-out tournament did not establish a playing-strength gain; see [evaluation](evaluation.md). `PolicyAgent` uses scores through the common agent API. Inference version 2 also applies a generic liveness guard at multi-step selections: it avoids a legal `cancel` when another choice is available, finishes a selection instead of unselecting when possible, and avoids immediately unselecting the card it just selected if another card can be selected. These choices can change strategy; reports identify the inference and feature versions.

Opt-in feature version 19 adds two public state numbers for the turn owner:
whether the acting player's own turn is in progress and whether the replay
records a turn owner at all. Schema-v23 demonstrations are required for this
version. A response window can belong to one player during the other's turn;
older policy feature versions do not represent that distinction. Version 19
adds capacity to learn timing choices such as Scapegoat at an opponent's End
Phase. It has not yet been trained or shown to improve playing strength.

This is a first representation, not a validated strong architecture. It does not yet model public event history, recipient-scoped reveals, other restrictions, changes to the Deck since duel start, or individual Damage Step substeps. Unknown card IDs share one embedding. Target context is pooled and may still lose relationships among cards. The model does not infer hidden hands or deck order. It currently scores one decision at a time; opt-in behavioral-clone minibatches accumulate gradients before an optimizer update, but batched inference, recurrent memory, and action-set attention remain open experiments. A held-out three-batch comparison found higher training throughput but no demonstrated strength gain; the original batch size 1 remains the default. See [the measured training comparison](evaluation.md).

For local replay review, `scripts/score_reviewed_decisions.py` verifies the
native trajectory and its visibility, checks SHA-256-bound annotation indices,
and reports the model's rank and logit margin for each reviewed legal action.
It also reports exact replay and seed overlap with the checkpoint's training
provenance. These margins diagnose fixed decisions; held-out duel results
remain the playing-strength gate. See [the replay audit](replay_audit.md).

Install the optional ML dependency and record a native fixture duel:

```bash
python -m pip install -e '.[dev,ml]'
python examples/play_vanilla.py --seed 42 --trajectory replays/vanilla_42.json
python scripts/train_behavioral_clone.py replays/vanilla_42.json \
  --output checkpoints/vanilla_bc.pt --epochs 1 --seed 42
```

The training command first replays every input trajectory against the selected pinned native engine, checking each visible observation, legal-action list, chosen action, result, deck hash, and loaded asset hashes. It requires fingerprinted schema-v3 through v17 recordings. Use `--engine experimental` for an experimental-adapter trajectory. It then fits cross-entropy to selected actions and saves a versioned checkpoint containing model weights, card vocabulary, seed, PyTorch version, source counts, trajectory hashes, and epoch losses. Generated replays and checkpoints live in ignored directories. Only ingest demonstrations whose use is authorized.

The fixture command demonstrates software integration. Its source is random self-play, not skilled human data, and its training loss says nothing about playing strength. No automated EDOPro or DuelingBook human replay parser, authorized tournament human dataset, or trained competitive checkpoint is available yet. Before using human imitation as a strength baseline, collect authorized trajectories with legal actions and visibility reconstructed, split them by players/decks/matches, verify them, and measure win rate against held-out agents and deck families.

A local version-3 pipeline check on 2026-10-24 replay-verified a schema-v6 vanilla duel with seed 42 and 1,368 decisions, trained one epoch at width 16 with mean decision loss 0.5268, then loaded the checkpoint for seat-swapped inference on seeds 43–44. It won 2/4 against RandomAgent, with both wins in the second seat. This is a protocol check on two seeds and random demonstration labels, not evidence of stronger play. The replay and checkpoint were kept under ignored `.cache/goat-ai/`.

A version-4 pipeline check on 2026-10-24 replay-verified the schema-v9 Ground Collapse fixture produced by `examples/record_ground_collapse.py`: 1,126 decisions, including one selected two-zone action and 1,119 observations with disabled-zone state. One epoch at width 16 and seed 17 completed with mean decision loss 0.5452. The demonstration is mostly random play and the resulting checkpoint has no held-out strength evaluation. This verifies training compatibility with the new action and observation fields only.

A version-5 pipeline check on the same date regenerated that fixture under schema v11, replay-verified all 1,126 decisions, rendered its HTML view with each acting player's starting Deck, and trained one epoch at width 16 and seed 17. Mean decision loss was 0.5430. This training check establishes that the own-Deck feature survives recording, replay, and training without access to shuffled Deck order; its loss is not a measure of playing strength.

The training CLI accepts `--feature-version` for controlled encoder comparisons. Repeating the same schema-v11 Ground Collapse training data with `--feature-version 4` produced tensors exactly equal to the earlier version-4 checkpoint; the saved files have different hashes because their trajectory metadata differs. On held-out seeds 60–63, version 5 won 11/16 against RandomAgent and 7/16 directly against version 4, while version 4 won 14/16 against RandomAgent. These small, unaudited-deck results give no evidence that the new Deck feature improved play. See [the evaluation log](evaluation.md).

## Seat-labeled demonstrations

A full-duel trajectory can name `skill_metadata.demonstrator_seat` as 0 or 1. Behavioral cloning verifies the **entire** native replay, then uses only that seat's selected actions as labels. This prevents an opponent's random decisions from contaminating a heuristic or human demonstration. The CLI human player in `examples/play_vanilla.py --human-seat 0` records `source=human_cli`, `authorization=self_recorded`, and the selected seat when a trajectory path is supplied. This is a local interactive recording path; it does not parse tournament videos or third-party replays.

For `source=self_play_rl`, the learner is the only demonstrator. New recordings
store both `learner_seat` and matching `demonstrator_seat`; older recordings
with only `learner_seat` are filtered by that seat when reused for cloning or
policy agreement. Missing, invalid, or contradictory self-play seat metadata
is rejected. A `source=self_play` trajectory without a labeled seat still
represents both players' decisions. The training checkpoint records the
resolved demonstrator seat for each source game.

## Retrospective decision annotations

The offline replay viewer lets a reviewer label a displayed decision with
one of that frame's legal actions. For a checkpoint-attributed policy replay,
it offers only the policy seat's decisions and exports `policy_review` labels;
sampled `self_play_rl` replays offer only learner-seat decisions and export
`self_play_review` labels. Other supported replays export `self_recorded`
labels. The downloaded
schema-v1 JSON contains the source trajectory SHA-256, reviewer alias,
authorization, and pairs of zero-based decision and legal-action indexes.
No observation or hidden card state is added to the label file. The viewer
runs locally and does not submit labels to a server. The checkbox is the
reviewer's self-attestation; the software does not independently verify
identity or rights to third-party gameplay footage.

Pass one `--annotation` file per positional trajectory to
`scripts/train_behavioral_clone.py`, in the same order. In annotation mode
the trainer uses **only** the labeled decisions. It first replay-verifies the
complete fingerprinted trajectory against pinned native assets and audits
visible action safety for every training trajectory, then checks the exact
trajectory byte hash, authorization,
unique decision indexes, and legal-action indexes. The checkpoint records
`source=human_annotation`, the reviewer, authorization, annotation hash, and
selected decision count. These are hindsight choices on recorded states; a
reviewer can inspect future frames, so they must not be presented as live
human-gameplay demonstrations or assumed to reflect expert skill. Hold out
entire games and decklists before claiming any training benefit.

The same selective-label reader accepts `authorization=scripted_scenario`
only when the trajectory source begins with `scripted_` and every labeled
action is the one actually executed in that replay. It still requires the
source hash, replay verification, visibility audit, unique decision indexes,
and legal-action indexes. The trainer records these separately as
`source=synthetic_annotation`; they are never counted as human labels.
`scripts/generate_scapegoat_timing_probe.py` generates three such labels for
an End Phase Scapegoat diagnostic. This is a narrow curriculum tool, not an
expert-play dataset. Evaluate any model trained on it on separate seeds and
decks before claiming a gain.

For project-recorded policy games, `authorization=policy_review` accepts
retrospective corrections to legal actions **only for the checkpoint's policy
seat**. The trajectory must have `source=policy_evaluation`, a policy seat,
and a checkpoint SHA-256 in its metadata. Unlike a scripted-scenario label,
the reviewed choice may differ from the recorded action. Training provenance
uses `source=policy_review_annotation`, separate from human and scripted
labels. The reviewer is evaluating the saved player-visible state, so these
are hypotheses about better play, not demonstrated expert decisions. The
complete source duel is replay-verified before the corrected choices are used.

Sampled self-play corrections use `authorization=self_play_review`, only on
the recorded learner seat. The trainer records them as
`source=self_play_review_annotation`, separate from live human play,
checkpoint policy reviews, and the sampled self-play action itself. The
source trajectory must be `self_play_rl` with valid matching learner-seat
metadata; a `self_recorded` annotation for that source is rejected. A
reviewer's choice remains a retrospective hypothesis until independently
evaluated. The viewer does not export labels while reviewer-only hidden-card
reveals are loaded.

For reviews where several legal choices are acceptable, the separate
`examples/preferences/` schema names nonempty preferred and disfavored
action-index sets at one replay decision. The disfavored set must include
the recorded action. `scripts/score_reviewed_preferences.py` verifies the
complete native replay and its visibility, checks the source hash, agent
seat, and legal indices, then scores the two sets without assigning an
arbitrary winner among equally plausible options. It subtracts the log of
each set's size from its log-sum-exp score so a set is not rewarded merely
for containing more actions. `scripts/train_review_preferences.py` is an
opt-in experiment that consumes the same replay-verified preferences. It
minimizes a pairwise logistic loss between the preferred and disfavored sets,
while matching a frozen parent policy on sampled, parent-provenance states.
The training checkpoint records both source hashes and counts these reviews
separately from demonstrations. The four current reviews come from sampled AI
self-play; they are retrospective play hypotheses, not expert human data.
Their fixed-state margins alone do not establish playing strength. See the
held-out child-versus-parent result in [evaluation](evaluation.md).

For rehearsal, pass `--annotation-for TRAJECTORY=LABELS` for the scripted
replay and leave ordinary teacher trajectories unannotated. A scripted
trajectory without labels is rejected, so its random filler decisions cannot
silently become demonstrations. `--source-weight synthetic_annotation=200`
changes sampling probability while keeping the
number of optimizer decisions per epoch fixed. The checkpoint records source
weights and new source counts. `--trainable-module state_numbers` and
`--trainable-module score` can restrict a warm-start update to those policy
modules; the tested timing fit using this restriction lost heavily in
held-out competition. See [evaluation](evaluation.md).

For a separate stability experiment, `--parent-kl-steps` fits the selected
labels while matching a frozen parent policy on sampled multi-option states.
`--preserve-trajectories` must name games already fingerprinted in the parent
checkpoint; the trainer replay-verifies and visibility-audits them, then
checks their exact byte hashes against parent provenance. The sampled states,
KL weight, batch size, step count, and parent hash are saved with the child.
This is policy distillation on visible states, not simulator access to hidden
cards. Example:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/train_behavioral_clone.py \
  replays/scapegoat_end_timing_probe_seed52.json \
  --annotation replays/scapegoat_end_timing_probe_seed52.labels.json \
  --engine experimental --feature-version 19 --width 16 \
  --init-checkpoint checkpoints/tactical_v3_fv19_2500_2503.pt \
  --parent-kl-steps 500 --preserve-per-trajectory 32 \
  --preserve-batch 8 --parent-kl-weight 1 --learning-rate 0.001 --seed 19 \
  --preserve-trajectories replays/tactical_v3_cas_daryl_2500_2503/*.json \
  replays/tactical_v3_matt_jesse_2500_2503/*.json \
  --output checkpoints/tactical_v3_fv19_timing_parent_kl_52.pt
```

The `--batch-size` option belongs to ordinary behavioral cloning; parent-KL
uses all labeled decisions and `--preserve-batch` reference states at each
step. This experiment preserved overall win rate against its parent in one
held-out schedule but did not improve it, and Scapegoat agreement worsened
where the teacher passed. See [evaluation](evaluation.md).

The timing generator also supports `--deck-a`, `--deck-b`, and a required
`--output` for custom decks. Beside the trajectory, it writes a
`.curriculum.labels.json` with early Scapegoat passes and the later
activation. `--label-kind-weight chain=10` raises the training loss weight
of selected chain responses without hiding the early-pass labels. This
weight changes only the learning objective; the engine still supplies all
legal actions. The tested published-deck curriculum transferred its timing
choice to a separate Jesse replay, although Jesse's Main Deck was present
in the parent checkpoint's training games. It did not establish better duel
results.

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

The evaluator refuses seeds present in checkpoint training-game metadata. `--reject-training-deck-hashes` additionally rejects exact evaluation YDK file bytes found in either checkpoint's training-game Deck hashes and requires Deck-hash provenance. New behavioral-clone checkpoints and self-play episodes also store a versioned SHA-256 of each training Main Deck card multiset. A self-play child of an older checkpoint retains that parent’s missing hashes and therefore cannot pass the stricter gate. `--require-unseen-main-decks` compares those composition hashes for both checkpoints and fails closed if the metadata is absent. This catches reordered cards, changed YDK comments, and Side/Extra Deck changes, but does not identify related lists with different Main Deck compositions or prove an unseen archetype. Older checkpoints without composition provenance must be retrained or evaluated with the weaker exact-file gate. It uses paired seat swaps and reports individual results, seat splits, a paired score interval, and core/deck/checkpoint hashes. `--opponent-checkpoint PATH` compares two saved policies and checks both checkpoints' training seeds. `--workers 2` uses spawned native and policy workers; `--matchup DECK_A DECK_B` accepts additional deck pairs, and `--engine experimental` selects the broader unaudited adapter. A held-out seed on the same fixture decks is a protocol and baseline check; it is not held-out deck-family evaluation. See [the measured evaluation log](evaluation.md).

## Initial self-play experiment

`scripts/train_self_play.py` implements an episodic score-function policy-gradient update inspired by [Williams's REINFORCE paper](https://doi.org/10.1007/bf00992696). It samples legal actions from the current policy, plays native duels against a mixture of frozen historical policy snapshots and RandomAgent, and applies terminal rewards of +1 for a win, −1 for a loss, and 0 for a draw. A moving return baseline and entropy bonus are optional variance and exploration aids. Frozen snapshots preserve past opponents during updates; the first snapshot remains in the pool. The trainer alternates learner seats, records seeds and opponents, and can write complete player-visible trajectories with `--record-dir`. It never grants the learner access to an opponent's hidden cards.

```bash
OMP_NUM_THREADS=1 python scripts/train_self_play.py checkpoints/vanilla_bc.pt \
  --output checkpoints/vanilla_rl.pt --seed 100 --games 16 \
  --record-dir replays/vanilla_rl
python scripts/evaluate_policy.py checkpoints/vanilla_rl.pt --seed 200 --seeds 8
```

This is an experiment, not a selected final RL algorithm. Terminal reward is sparse; the original trainer has no value function, PPO update, opponent league, or checkpoint selection by held-out win rate. Runs from random imitation and from the stronger heuristic imitation checkpoint did not demonstrate an improvement in greedy playing strength; see [the evaluation log](evaluation.md). Future work should compare a richer action encoder, value baselines and PPO under the same held-out schedule, while keeping training opponents separate from evaluation opponents.

An opt-in `--baseline-scope state_value` now tests a learned Monte Carlo
baseline. A separate critic embeds the same **player-visible** card, zone,
owner, position, phase, and numeric observation features as the policy
interface; it never receives the simulator's complete state or a selected
action. Before each policy update, it predicts a value for every learner
decision, and the policy gradient uses terminal reward minus that frozen
prediction. The critic then fits the same terminal return by squared error.
Its architecture, weights, learning rate, per-episode value loss, and source
provenance are saved with the child checkpoint. Existing global and per-deck
moving baselines remain unchanged. This is a simple state-value control
variate related to the [policy-gradient baseline analysis by Sutton et al.](https://papers.nips.cc/paper_files/paper/1999/hash/464d828b85b0bed98e80ade0a5c43b0f-Abstract.html),
not a bootstrapped or asynchronous actor-critic implementation such as
[A3C](https://proceedings.mlr.press/v48/mniha16.html), and not PPO. The
four-game native smoke and matched held-out results are in
[evaluation](evaluation.md). The held-out comparison does not establish an
improvement over the per-deck baseline or the unchanged parent.

## Ordered-chain feature check

A feature-version-10 checkpoint trained on the same 4,630 replay-verified teacher decisions as version 9 won 20–11 with one draw in 32 paired, seat-swapped duels on sourced Chaos Return and Warrior lists. On separate held-out teacher decisions with a nonempty chain and multiple legal actions, it matched 116/135 choices versus version 9's 114/135; overall teacher agreement was slightly lower (4,073/4,139 versus 4,075/4,139). The small tournament and mixed agreement result are recorded in [the evaluation log](evaluation.md); they do not establish a general strength gain or isolate chain-order encoding from model-capacity changes.

Feature version 11 holds the model architecture and seeded initialization constant while sorting public chain links before the same GRU. With matched demonstrations and training settings, ordered version 10 scored 16–15 with one draw against this unordered ablation across 32 held-out Chaos Return/Warrior duels. Chain-decision teacher agreement was 116/135 versus 115/135. The [evaluation log](evaluation.md) records the schedule and intervals. There is no measured chain-order strength gain on this schedule; more deck families and training seeds are needed.

An additional 32-duel Chaos Control/Warrior schedule split 16–16 against the unordered control and gave ordered version 10 only a 17–15 result against version 9. A same-seed HeuristicAgent versus HeuristicAgent control favored Warrior 24–8 across the two deck orders. These comparisons expose a strong deck effect and do not establish an ordered-chain or version-10 strength gain. See [the evaluation log](evaluation.md).

## Sourced-deck imitation check

A feature-version-8 checkpoint was trained on 6,999 replay-verified HeuristicAgent decisions from 16 sourced Goat Control/Chaos Turbo duels. On separate verified trajectories with real choices, exact teacher-action agreement rose from 737/891 for the prior vanilla-trained version-2 checkpoint to 859/891. On held-out paired duels, the new checkpoint split 16–16 against that prior checkpoint and won only 18/32 against RandomAgent. The protocol, hashes, deck splits, and confidence intervals are in [the evaluation log](evaluation.md). This is evidence that the imitation pipeline can learn the teacher on these decks; it is not evidence of improved competitive strength. Authorized expert demonstrations and stronger self-play updates remain necessary for M4.

## Balanced sourced-deck self-play

The self-play schedule now cycles each matchup through both learner seats before advancing, preventing a reversed two-matchup list from training one deck exclusively. A 16-game experiment from the sourced imitation checkpoint covered both sourced decks in both seats. Four recorded duels replay-verified, but the resulting child won only 17/32 in a fresh direct paired comparison with its parent. It made the same choices as the parent on the held-out teacher-action audit. See [the evaluation log](evaluation.md) for the schedule, hashes, measurements, and limitations. This update remains an experimental terminal-reward baseline; it does not meet M4's competitive improvement gate.

The opt-in `--schedule-mode four_roles` now makes one listed matchup cover
**both decks in both learner seats** in four consecutive games. The CLI requires
a whole cycle for every listed matchup. The older `paired_seats` default is
retained for exact reproduction of previous runs; it trains the first listed
deck in both seats unless the reversed pairing is listed separately. The
chosen mode is saved in `self_play_config`. A four-game native smoke run and
its full replay/visibility checks are in [evaluation](evaluation.md). This
schedule fixes training coverage, not the sparse-reward learning problem.
