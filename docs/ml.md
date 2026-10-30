# Initial policy and imitation pipeline

An opt-in `--on-policy-teacher tactical_v14` mode can label a saved
`policy_evaluation` trajectory at states visited by the policy itself. It
requires `--init-checkpoint` to match the replay's checkpoint SHA-256 and
replay-verifies and visibility-audits the complete duel before producing
labels. Only multi-option decisions by the policy seat are used; the opponent
seat and the reviewer's hidden-card sidecar are excluded. Tactical v14 sees
the same player-visible observation and legal actions as the policy, and its
choice is checked against that legal set. The executed trajectory stays
unchanged. Checkpoints count these decisions separately as
`automated_teacher_tactical_v14`, with teacher version and disagreement counts
in per-game provenance. This is synthetic on-policy distillation, not human
demonstration or a claim that the teacher's choice is always best. The first
held-out experiment [did not improve playing strength](evaluation.md).

`--on-policy-disagreement-weight 4` optionally samples policy/teacher
disagreements four times as often during cloning. It requires unfiltered
on-policy teacher labels and records the weight and disagreement count in
the checkpoint. It does not create new decisions or imply an expert label.
In a 64-duel collection, it improved score versus Tactical on two held-out
deck pairings but regressed on a separate Dimension Fusion family; see the
[expanded evaluation](evaluation.md). The unchanged parent remains the
neural reference.

The additional opt-in `tactical_card_advantage` teacher changes only the
visible Heavy Storm trade preference; it remains a synthetic heuristic.
`--on-policy-teacher-activation-focus-only` limits labels to decisions where
one of the specified `--focus-card` IDs has a legal activation. This retains
both good and bad activation opportunities and records their count and
teacher disagreements in checkpoint provenance. The 32-game resource
experiment and its held-out limits are in [evaluation](evaluation.md).

`LegalActionPolicy` scores the legal options supplied by `GoatEnvironment`. It uses only the `Observation` and `Action` values that baseline agents receive. A sorted vocabulary comes from the pinned GOAT whitelist; hidden or absent card identities map to token 0 and visible cards missing from that vocabulary map to an unknown token. The model embeds visible cards, their zones, owners, and positions; pools them into a state vector; then scores each action using its kind, referenced card, selected-card identities, and numeric parameters. It returns one logit per legal action, with no fixed option count or model access to native core state. Feature version 2 also encodes each selected target's visible controller, zone, and slot, including when its card identity is hidden. Target presence has its own mask so hidden IDs are not mistaken for padding. Feature version 3 resolves a face-down opponent card's ID from `known_opponent_field_cards` only when its controller, field zone, and slot match a public memory entry; it applies this to state and action card features. Feature version 4 adds a public disabled-zone bitmask to the state and represents each selected field zone as a structured target, with new action kinds for multi-zone prompts. Feature version 5 separately pools card embeddings from the player's sorted initial Main Deck composition. Feature version 6 distinguishes Attribute, number, and card-name announcement actions with separate kinds; Attribute and number choices also have numeric features. Feature version 7 pairs each selected card embedding with its original slot and chosen rank, allowing distinct ordered Deck-top choices to receive different logits. Feature version 8 projects current ATK, DEF, total counters, and Spell Counter counts for face-up monsters; hidden and face-down card stats remain absent. Feature version 9 separately pools an unordered multiset of publicly known opponent hand cards from schema-v17 observations. Private draws remain unknown and no native hand slot is encoded. Feature version 10 adds an ordered recurrent encoding of the public chain card identities and controllers, so reversing two chain links changes the state representation; it does not use private native state. Feature version 11 is an equal-capacity unordered-chain ablation. Feature version 12 matches each direct or multi-card field selection to its corresponding card in the visible field, adding that card's embedding and visible current stats to the action score. This resolves an ambiguity when identical cards in different slots have different current ATK, DEF, or counters. It adds no model parameters. Opt-in feature version 13 binds each visible face-up Equip Spell to the visible card in its target monster slot and projects the paired embeddings before pooling; a representation test distinguishes two possible equip targets. Opt-in feature version 14 encodes schema-v21 public chain target slots with each link in the ordered chain, binding targets to visible field cards when present. Its target-slot embeddings reveal no hidden card IDs. A matched v13/v14 experiment found no target-specific or held-out strength gain; see [evaluation](evaluation.md). Version 10 remains the default. A first matched v12/v13 experiment found no equip-specific decision change or held-out strength gain; see [evaluation](evaluation.md). Older checkpoints retain their versioned encoder and weights. Version 9 has a representation test and a controlled sourced-deck comparison: it won 18/32 against a version-8 model trained on the same schema-v17 demonstrations, with a paired 95% interval of 40.625–71.875%; see [the evaluation log](evaluation.md). This does not establish a strength gain. Existing checkpoints without a feature version load with the original version-1 encoder. The encoder does not yet use historical public Deck reveals or all restrictions. Opt-in feature version 17 adds four action-specific numbers at an attack-target choice: the public attacker ATK, the target’s visible battle stat, their margin, and a visibility flag. It uses the acting player’s own attacker slot from schema-v22 observations and leaves face-down target stats unknown. A first matched held-out tournament did not establish a playing-strength gain; see [evaluation](evaluation.md). `PolicyAgent` uses scores through the common agent API. Inference version 2 also applies a generic liveness guard at multi-step selections: it avoids a legal `cancel` when another choice is available, finishes a selection instead of unselecting when possible, and avoids immediately unselecting the card it just selected if another card can be selected. These choices can change strategy; reports identify the inference and feature versions.

Opt-in feature version 19 adds two public state numbers for the turn owner:
whether the acting player's own turn is in progress and whether the replay
records a turn owner at all. Schema-v23 demonstrations are required for this
version. A response window can belong to one player during the other's turn;
older policy feature versions do not represent that distinction. Version 19
adds capacity to learn timing choices such as Scapegoat at an opponent's End
Phase. Feature-19 checkpoints and held-out results are in
[evaluation](evaluation.md); a broad strength gain remains unproven.

Opt-in feature version 20 encodes each bit of an announced monster Type as a
separate action feature. Earlier versions divided the Type mask by
`2**32 - 1`, leaving common Type choices only millionths apart in the input.
The change is limited to action encoding: no hidden card identities or native
state are added. Schema-v24 observations now supply current public Type for
face-up monsters, including Type-changing effects; the current feature-20
policy does not encode that field-to-announcement relationship. Opt-in feature
version 21 adds four action features for each announced Type: the count and
current ATK sum of matching opponent and own face-up monsters. It reads only
schema-v24 public Type values. The training command rejects older replay
schemas for this version, and feature-20 checkpoints retain their original
action layer.
Version-19 checkpoints retain their original 19-number
action layer; version 20 uses 81 numbers and requires a new checkpoint. A
replay review found a Tribe-Infecting Virus Type choice whose old policy
scored all three actions almost equally; the [replay audit](replay_audit.md)
and [evaluation](evaluation.md) track the measured follow-up.

This is a first representation, not a validated strong architecture. It does not yet model public event history, recipient-scoped reveals, other restrictions, changes to the Deck since duel start, or individual Damage Step substeps. Unknown card IDs share one embedding. Target context is pooled and may still lose relationships among cards. The model does not infer hidden hands or deck order. Ordinary inference scores one decision at a time; behavioral cloning can optionally pad variable-length decisions and score a minibatch together with `--batched-forward`. Batched inference across live duels, recurrent memory, and action-set attention remain open experiments. The original batch size 1 remains the default because faster training has not demonstrated stronger play. See [the measured training comparison](evaluation.md) and [throughput benchmark](benchmarks.md).

Feature v32 is an opt-in action feature for schema-v28 decisions where one
visible card offers multiple effects. It encodes the public effect-option
index, distinguishing choices that earlier encoders represented identically.
The behavioral-cloning command can zero-extend a v23 parent with
`--upgrade-feature-23-to-32`; its initial logits remain those of the parent.
No v32 playing-strength result is available yet.

Feature v27 is an opt-in action-to-visible-card attention branch from v23.
It uses the same player-visible input and starts with identical v23 logits.
The first matched 437-label experiment split 32–32 against its v23 control
across two unseen-deck families, with opposite family results. Keep the v23
reference selected; see [the held-out comparison](evaluation.md#action-conditioned-visible-card-attention-feature-v27-27-october-2026).

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

The training command first replays every input trajectory against the selected
pinned native engine, checking each visible observation, legal-action list,
chosen action, result, deck hash, and loaded asset hashes. It accepts
fingerprinted schema-v3 through v25 recordings; feature versions 17–18
require schema v22, versions 19–20 require schema v23, and version 21 or
later requires schema v24. Use `--engine experimental` for an
experimental-adapter trajectory. `--verification-workers 4` optionally
verifies independent trajectories in isolated processes while retaining
input order and the same checks; the default is one worker. Parallel
verification checks each trajectory's byte hash before the main process
uses it. The trainer then fits cross-entropy to selected actions and saves
a versioned checkpoint containing model weights, card vocabulary, seed,
PyTorch version, source counts, trajectory hashes, and epoch losses.
Generated replays and checkpoints live in ignored directories. Only ingest
demonstrations whose use is authorized.

To enrich a verified schema-v23 recording with current public Type without
changing its original bytes or SHA-bound review labels, run
`scripts/upgrade_trajectory_schema.py` with a **new** `--output` path. It
verifies the source, deterministically replays the exact legal choices, and
verifies the resulting schema-v24 file. It accepts v23 only; a newer
observation or action contract still needs its own compatibility review.

The fixture command demonstrates software integration. Its source is random self-play, not skilled human data, and its training loss says nothing about playing strength. No automated EDOPro or DuelingBook human replay parser, authorized tournament human dataset, or trained competitive checkpoint is available yet. Before using human imitation as a strength baseline, collect authorized trajectories with legal actions and visibility reconstructed, split them by players/decks/matches, verify them, and measure win rate against held-out agents and deck families.

A local version-3 pipeline check on 2026-10-24 replay-verified a schema-v6 vanilla duel with seed 42 and 1,368 decisions, trained one epoch at width 16 with mean decision loss 0.5268, then loaded the checkpoint for seat-swapped inference on seeds 43–44. It won 2/4 against RandomAgent, with both wins in the second seat. This is a protocol check on two seeds and random demonstration labels, not evidence of stronger play. The replay and checkpoint were kept under ignored `.cache/goat-ai/`.

A version-4 pipeline check on 2026-10-24 replay-verified the schema-v9 Ground Collapse fixture produced by `examples/record_ground_collapse.py`: 1,126 decisions, including one selected two-zone action and 1,119 observations with disabled-zone state. One epoch at width 16 and seed 17 completed with mean decision loss 0.5452. The demonstration is mostly random play and the resulting checkpoint has no held-out strength evaluation. This verifies training compatibility with the new action and observation fields only.

A version-5 pipeline check on the same date regenerated that fixture under schema v11, replay-verified all 1,126 decisions, rendered its HTML view with each acting player's starting Deck, and trained one epoch at width 16 and seed 17. Mean decision loss was 0.5430. This training check establishes that the own-Deck feature survives recording, replay, and training without access to shuffled Deck order; its loss is not a measure of playing strength.

The training CLI accepts `--feature-version` for controlled encoder comparisons. Repeating the same schema-v11 Ground Collapse training data with `--feature-version 4` produced tensors exactly equal to the earlier version-4 checkpoint; the saved files have different hashes because their trajectory metadata differs. On held-out seeds 60–63, version 5 won 11/16 against RandomAgent and 7/16 directly against version 4, while version 4 won 14/16 against RandomAgent. These small, unaudited-deck results give no evidence that the new Deck feature improved play. See [the evaluation log](evaluation.md).

## Seat-labeled demonstrations

A full-duel trajectory can name `skill_metadata.demonstrator_seat` as 0 or 1. Behavioral cloning verifies the **entire** native replay, then uses only that seat's selected actions as labels. This prevents an opponent's random decisions from contaminating a heuristic or human demonstration. The CLI human player in `examples/play_vanilla.py --human-seat 0` records `source=human_cli`, `authorization=self_recorded`, and the selected seat when a trajectory path is supplied. This is a local interactive recording path; it does not parse tournament videos or third-party replays.

Raw behavioral-clone labels are admitted only from known local sources:
`self_play`, `self_play_rl`, `heuristic`, `combat_heuristic`, `combat_flip`,
`tactical`, and `human_cli`. The generic
[`examples/play_goat.py`](../examples/play_goat.py) records a CLI human seat
against a baseline or policy on user-selected GOAT Decks and checks the saved
duel against the native engine and player-visible audit before publication to
the local trajectory path. Teacher and CLI recordings require a valid
demonstrator seat; CLI recordings also require the `self_recorded` authorization
declaration. Checkpoint policy replays need explicit review labels or an
automated teacher. Scripted scenarios need matching scripted annotations.
Unknown sources cannot silently become raw demonstrations, and EDOPro
reconstruction is excluded from this trainer pending its separate admission
gates. These metadata checks do not authenticate a person's declaration of
rights; contributors must still provide permission for external recordings.

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

To record many policy-visited states reproducibly, use the batch recorder:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python \
  scripts/collect_policy_matches.py checkpoints/policy.pt \
  --matchup examples/decks/goat_control_jesse_twohig_indianapolis_2005.ydk \
            examples/decks/warrior_montague_clash.ydk \
  --matchup examples/decks/chaos_return_dingosig_worlds_2022.ydk \
            examples/decks/flip_control_goatformat_guide.ydk \
  --seed 12000 --seeds 8 --workers 4 --opponent tactical \
  --output-dir .cache/goat-ai/policy_collection_12000
```

It records both policy seats for every matchup and seed, replay-verifies
each complete native duel, audits player-visible information, and writes a
manifest with the checkpoint, deck, and trajectory hashes. The output
directory must be empty, so existing recordings cannot be overwritten.
Use `matchup_*.json` when passing the trajectories to the trainer; the
directory also contains `manifest.json`. These are synthetic opponent games,
not authorized human demonstrations.

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

Preference schema v2 is reserved for `authorization=automated_rule` with
`rule_set_id=visible_resource_v3`. It permits the recorded action in either
the preferred or disfavored set, provided both sets are disjoint, legal, and
one contains the recorded choice. Schema v1 keeps its original contract:
the recorded choice must be disfavored. The trainer independently recomputes
all automated comparisons from the verified source replay.

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
cards.

Cloning can use `--fast-trajectory-json` with the optional `.[speed]` extra to
decode source replays with `orjson` in both the main process and verification
workers. It changes only JSON decoding; native replay verification, visibility
auditing, source hashes, and feature encoding remain required. A matched
eight-replay check produced identical model tensors and a small wall-time
reduction; see [evaluation](evaluation.md#optional-fast-trajectory-reading-for-cloning-27-october-2026).

Parent-KL example:

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
step. Behavioral cloning now collects each minibatch's losses and makes one
backward call per optimizer update. `--batched-forward` pads visible states
and legal-action sets, batches the chain encoder, and masks padded actions
from the loss. It supports feature versions 10–13 and 16–25; versions
14–15 retain the individual path because their chain-target encoder needs
field-dependent inputs. It is opt-in and can produce slightly different
floating-point updates from the individual path. Replay
verification, model fitting, and total wall time are reported separately.
The [measured optimization run](benchmarks.md) shows where time went on one
32-trajectory workload. The earlier minibatch experiment preserved overall win rate against its parent in one
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

This teacher is the project's generic `HeuristicAgent`, not a human player. The measured results and limits are in [the evaluation log](evaluation.md). The same schema can hold authorized human choices, but card-by-card historical correctness and broad visibility coverage still need expansion before using the experimental adapter for research training. Browser-recorded `human_web` trajectories additionally carry explicit human decision indices: automatic passes, phase travel, and zone placement are retained for full-duel replay but excluded from cloning. Earlier browser recordings without these indices are rejected as raw human training data because their automatic choices cannot be distinguished reliably.

To measure a saved checkpoint against RandomAgent on seeds excluded from its training recordings:

```bash
python scripts/evaluate_policy.py checkpoints/vanilla_bc.pt --seed 43 --seeds 4 \
  --opponent random --output artifacts/vanilla_bc_eval.json
```

The evaluator refuses seeds present in checkpoint training-game metadata. `--reject-training-deck-hashes` additionally rejects exact evaluation YDK file bytes found in either checkpoint's training-game Deck hashes and requires Deck-hash provenance. New behavioral-clone checkpoints and self-play episodes also store a versioned SHA-256 of each training Main Deck card multiset. A self-play child of an older checkpoint retains that parent’s missing hashes and therefore cannot pass the stricter gate. `--require-unseen-main-decks` compares those composition hashes for both checkpoints and fails closed if the metadata is absent. This catches reordered cards, changed YDK comments, and Side/Extra Deck changes, but does not identify related lists with different Main Deck compositions or prove an unseen archetype. Older checkpoints without composition provenance must be retrained or evaluated with the weaker exact-file gate. It uses paired seat swaps and reports individual results, seat splits, a paired score interval, and core/deck/checkpoint hashes. `--opponent-checkpoint PATH` compares two saved policies and checks both checkpoints' training seeds. `--workers 2` uses spawned native and policy workers; `--matchup DECK_A DECK_B` accepts additional deck pairs, and `--engine experimental` selects the broader unaudited adapter. A held-out seed on the same fixture decks is a protocol and baseline check; it is not held-out deck-family evaluation. See [the measured evaluation log](evaluation.md).

## Initial self-play experiment

`scripts/train_self_play.py` implements an episodic score-function policy-gradient update inspired by [Williams's REINFORCE paper](https://doi.org/10.1007/bf00992696). It samples legal actions from the current policy, plays native duels against a mixture of frozen historical policy snapshots and RandomAgent, and applies terminal rewards of +1 for a win, −1 for a loss, and 0 for a draw. A moving return baseline and entropy bonus are optional variance and exploration aids. Frozen snapshots preserve past opponents during updates; the first snapshot remains in the pool. The trainer alternates learner seats, records seeds and opponents, and can write complete player-visible trajectories with `--record-dir`. It never grants the learner access to an opponent's hidden cards.
For replay-heavy CPU runs, `pip install '.[speed]'` makes self-play use the
optional fast trajectory writer automatically. Use `--standard-trajectory-json`
to reproduce the standard writer or `--fast-trajectory-json` to require the
optional dependency. Matched one-duel comparisons produced identical replay
bytes and policy tensors; see [benchmarks](benchmarks.md).

```bash
OMP_NUM_THREADS=1 python scripts/train_self_play.py checkpoints/vanilla_bc.pt \
  --output checkpoints/vanilla_rl.pt --seed 100 --games 16 \
  --record-dir replays/vanilla_rl
python scripts/evaluate_policy.py checkpoints/vanilla_rl.pt --seed 200 --seeds 8
```

This is an experiment, not a selected final RL algorithm. Terminal reward
is sparse, and neither update has an opponent league or checkpoint selection
by held-out win rate. Early runs from random and heuristic imitation did not
demonstrate an improvement in greedy playing strength; see
[evaluation](evaluation.md). Keep training opponents separate from evaluation
opponents when comparing future updates.

`--baseline-opponent tactical` optionally uses the version-14 generic
TacticalHeuristicAgent instead of RandomAgent on duels where a frozen policy
snapshot was not sampled. The default remains RandomAgent. The checkpoint
records this choice and each duel records the actual opponent. Tactical uses
the same player-visible observation and legal-action interface as the learner.
A 64-duel matched PPO continuation with this option produced reproducible,
replay-verified games but was weaker than its unchanged parent against
Tactical on unseen Main Decks; see [the evaluation](evaluation.md#tactical-baseline-opponent-in-ppo-27-october-2026).

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
[A3C](https://proceedings.mlr.press/v48/mniha16.html). The
four-game native smoke and matched held-out results are in
[evaluation](evaluation.md). The held-out comparison does not establish an
improvement over the per-deck baseline or the unchanged parent.

`--parent-kl-weight` optionally adds a per-decision KL penalty toward the
frozen starting checkpoint's action distribution. The parent and learner
score only the same visible observation and legal-action list, and the
weight is stored in `self_play_config`. Zero preserves the original update.
A matched 32-game pilot found different direct child-versus-child results
across held-out deck families and no advantage against the unchanged parent;
see [evaluation](evaluation.md). This is a tested regularizer, not a selected
self-play algorithm.

`--policy-update clipped_ppo` is an opt-in implementation of the clipped
probability-ratio objective from [Schulman et al., 2017](https://arxiv.org/abs/1707.06347).
It freezes the pre-update action probabilities for each sampled duel, then
reuses player-visible decisions for `--ppo-epochs` minibatch passes with
`--ppo-batch-size` and `--ppo-clip-epsilon`. `--ppo-rollout-games N` can
collect N complete duels before updating the policy; all N duels use the
same policy weights. `--ppo-rollout-weighting per_episode` scales decision
losses so each duel contributes equal total weight, while the default
`per_decision` gives longer duels more weight. Multi-duel rollouts require
terminal games, a moving return baseline, and a snapshot interval divisible
by N; the experimental state-value baseline is not supported in this mode.
The policy supports feature versions 10–13 and 16–25. Advantage remains
terminal outcome minus the baseline; there is no generalized advantage
estimation. Rollout batching is not a measured speedup or strength gain, and
neither PPO mode is evidence of superhuman play. The original REINFORCE path
remains the default. The controlled native comparisons are in
[evaluation](evaluation.md).

For a feature-v23 checkpoint on one CPU process, `--trace-rollout-inference`
can reduce repeated scorer overhead during multi-duel clipped PPO. It needs
`--ppo-rollout-games` of at least two, keeps one trace only while policy weights
are frozen, and leaves the optimizer on eager PyTorch. It cannot be combined
with rollout workers or batched rollout inference. Two matched 16-duel runs
saved about 4–6% of complete trainer time with identical replays and model
tensors; see [the measured comparison](benchmarks.md#reused-torchscript-trace-for-frozen-ppo-rollout-inference).

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

### Experimental feature version 23: position decisions

Version 23 extends opt-in version 22 with eight action-specific values for a
`change_position` choice: whether its own visible monster was found, whether
it is currently defending, its current ATK and DEF, their difference, and the
maximum and minimum **visible** opposing battle stats plus a complete-
visibility flag. A face-down opposing monster contributes no battle stat. The
values come from the same player-visible observation given to baseline agents;
no native hidden state or inferred card identity is used. A representation
test verifies that changing only the selected monster's current ATK changes
v23 action features while leaving v22 action features unchanged. Existing
checkpoints retain their feature versions. This is an experiment, not a
promotion of a stronger policy.

### Experimental feature versions 24 and 25: visible card trades

Version 24 adds three action values for a Heavy Storm or Nobleman of Crossout
activation: a before-chain visible card-trade estimate, friendly collateral,
and an estimate-present flag. For Heavy Storm, the estimate is opposing back
row minus friendly back row destroyed minus the Storm itself. The Set Storm
source is excluded from collateral. For Nobleman, it records whether an
opposing Set monster exists or the only available Set monster is friendly.
It uses field counts and positions in the acting player's observation; Set
opponent identities, chain responses, and future effects are unknown. The
estimate is a learning input, not a hard legality filter or a full card-value
model.

Version 25 keeps those features and adds a two-weight learned trade scorer to
the action logits. The explicit `--upgrade-feature-23-to-25` warm start copies
the v23 checkpoint, zero-extends its action input, and initializes this scorer
to zero, preserving the parent's initial logits. Training only
`--trainable-module trade_head` leaves every other policy weight frozen.
Tests verify initial logit equality and that only a visible trade changes
the new score. The default feature version remains 10; v24 and v25 are
experimental until held-out match strength supports promotion.

### Action-kind sampling in behavioral cloning

The cloning CLI accepts an opt-in `--label-kind-weight KIND=WEIGHT` for a
selected teacher action kind. Ordinary behavioral cloning multiplies this
factor by any source and card-opportunity factors, then draws the same total
number of decisions per epoch with replacement. Parent-KL continuation uses
the same option as a label-loss weight, retaining its existing behavior.
Unweighted runs still shuffle every input once per epoch. Checkpoints record
the action-kind weights and sampling mode. This changes the training
distribution, not the engine's legal actions or what the acting player can
observe. A matched experiment must check both held-out choices and competitive
results before using an oversampled checkpoint by default.

### Automated visible-rule preference experiment

`scripts/derive_visible_rule_preferences.py` can turn six conservative replay
audit flags into pairwise legal-action preferences. It verifies each complete
native replay and audits hidden-information isolation first. Historical v1
output uses `authorization=automated_rule` and
`rule_set_id=visible_audit_v1`; it is **synthetic feedback**, not a human
annotation. The v1 rules cover
self-banish with an opposing target, empty Thunder Dragon searches, weak Flip
monsters Summoned face up when a Set is available, Pot of Greed before an
available Thunder Dragon activation, and Ring of Destruction on an own monster
with a safe opposing target. The generator selects only alternatives present
in that decision's recorded legal-action set. It does not claim those
alternatives are always optimal.

The CLI now defaults to versioned rule set `visible_audit_no_weak_flip_v14`.
It keeps the other v2 visible-audit comparisons but leaves weak Flip Normal
Summons for human review: seven exact-state Magical Merchant branch checks
included one where Normal Summon won and Set lost. The older v1 and v2 rule
sets remain available explicitly, so existing synthetic files continue to
validate against their recorded semantics. A v14 preference file has schema
version 2 and distinct rule-set provenance. Removing an uncertain label is a
training-data correction, not evidence of a stronger policy; any child still
needs held-out match evaluation.

`scripts/train_review_preferences.py` accepts these files alongside its
existing human-review formats, records their distinct provenance, and
recomputes the rule output from the verified source replay before fitting.
An edited or forged automated preference that does not match the rule is
rejected. Reviewer-only hidden-card sidecars never enter this path. Training
still needs held-out, matched competitive checks before any child checkpoint
becomes the reference. The first post-patch experiment did **not** meet that
gate; see [evaluation](evaluation.md#automated-visible-rule-preference-experiment-27-october-2026).

`--rule-set visible_resource_v3` scans each recorded acting-player main-phase
legal set for two visible resource losses: Nobleman of Crossout when only the
acting player has a Set monster, and Heavy Storm when the opponent's visible
backrow count is no greater than the acting player's other backrow count.
The Set Heavy Storm source is excluded from its own collateral count. If the
recorded choice avoids the loss, that choice is preferred to the flagged
activations. If the recorded choice is flagged, an offered phase transition
is preferred. Near-identical contexts within a replay are deduplicated.
These labels compare a narrow card trade; they do not certify the preferred
action as strategically optimal. They use public counts and the acting
player's own cards, never opponent Set-card identities. The measured
experiment and its uneven cross-deck results are in
[evaluation](evaluation.md#visible-resource-v3-counterfactual-preference-experiment-27-october-2026).

`train_review_preferences.py --recorded-bad-weight N` is an opt-in ablation
for schema-v2 sets that contain both recorded safe and recorded bad choices.
It increases the pairwise-loss weight of comparisons where the replay chose
the disfavored action, normalizing by total comparison weight and recording
the setting in the checkpoint. Schema-v1 files always record a disfavored
choice, so a common weight does not rebalance them. An eightfold setting did
not establish a held-out gain or fix the inspected Nobleman decision; see
[evaluation](evaluation.md#recorded-bad-preference-weight-ablation-27-october-2026).

### Frozen moving baseline within a PPO rollout

Multi-duel PPO already collects several games under one frozen policy.
`--ppo-baseline-timing frozen_rollout` now optionally snapshots the moving
global or learner-deck return baseline at the start of that rollout, so all
games in the batch calculate advantages against the same prior estimate.
The default `online` mode continues updating the baseline between games.
The snapshot changes only learning weights; it reads no extra simulator state.
The checkpoint stores the selected timing. Native tests confirm identical
trajectories and updates across serial, worker, and batched-inference paths
for both modes. The first held-out comparison did not establish a playing-
strength gain; see [evaluation](evaluation.md#frozen-rollout-baseline-ablation-27-october-2026).

Opt-in policy feature version 29 adds the public face-up field-card age from
trajectory schema v26 as a sixth card number. It inherits v28's action inputs,
so a feature-v23 checkpoint can be loaded with `--upgrade-feature-23-to-29`:
the new age and counter-allocation weights start at zero and preserve the
parent's logits before training. New behavioral-cloning data for this version
must use schema v26; existing older checkpoints retain their original encoder.
This only makes timing information available to the model. No competitive
strength gain has been measured for v29.

Opt-in feature version 30 gives each `select_option` action its ordinal in the
player-visible legal list. The native prompt IDs for adjacent choices can
differ by one; dividing their low 32 bits by `2^32-1` makes them identical in
float32 under feature v23. In eight recent reviewed replays, all six prompts
with multiple `select_option` actions had this collision. The old checkpoint
cannot learn a preference between those choices from its current input.
Version 30 inherits v29's counter and public-age inputs and adds the ordinal
as one action number. `--upgrade-feature-23-to-30` zero-extends the selected
v23 weights, preserving its initial logits and training provenance. This is
a representation correction, not evidence of a playing-strength gain; the
feature-v23 checkpoint remains selected pending a held-out comparison.
