# Early replay decision audit

Review each agent's decisions from its own player-visible observation and legal
actions. The replay viewer's reviewer reveals are for human diagnosis only; they
must never feed a policy or a baseline. Viewer frames below are one-based; JSON
`decisions` indices are one less. The agent is identified from trajectory
`skill_metadata`, not inferred from the viewer's opponent/your-view label.

## Recent sampled self-play review

Four recent self-play trajectories were replay-verified against the pinned native
engine and passed the visibility audit. The learner's actions were **sampled**
from a positive-temperature policy during training. These examples diagnose
exploration and training feedback; they do not prove that a saved greedy
checkpoint would choose the same moves. Existing files identify the learner
seat but do not contain the exact per-game policy weights or temperature.
New recordings include the parent checkpoint hash, episode index, sampling
temperature, and action-selection method for clearer provenance.

| Replay (under `replays/`) | Viewer frame | Player-visible choice and legal alternative |
| --- | ---: | --- |
| `selfplay_value_smoke_3000/episode_00001_seed_3001.json` | 54 | Learner P1 Normal Summons 300 ATK Magician of Faith into an empty monster board; Set of the same card is legal. |
| `selfplay_value_smoke_3000/episode_00002_seed_3002.json` | 336 | Learner P0 activates its Set Heavy Storm with only its own Set Trap Dustshoot as collateral and no opposing Spell/Trap; End Phase is legal. |
| `selfplay_value_smoke_3000/episode_00003_seed_3003.json` | 1081 | Learner P1's Breaker targets its own Set Trap Dustshoot while an opposing Set Spell/Trap is a legal target. |
| `selfplay_fourroles_2820_2883/episode_00063_seed_2883.json` | 386 | Learner P1's Mystical Space Typhoon targets its own Set Dust Tornado while two opposing Set Spell/Traps are legal targets. |

The scripted shortlist found ten prompts across these four duels, including
these four. Other prompts require separate manual review; a flag is not a
mistake label. The ignored report is
`artifacts/selfplay_review_candidates_3001_3003_2883.json` (SHA-256
`7dd2263c48b781909f566e28476047d5209bffec72f72e4455dc6d58d5013c1d`).
Reproduce it with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/audit_selfplay_replays.py \
  replays/selfplay_value_smoke_3000/episode_00001_seed_3001.json \
  replays/selfplay_value_smoke_3000/episode_00002_seed_3002.json \
  replays/selfplay_value_smoke_3000/episode_00003_seed_3003.json \
  replays/selfplay_fourroles_2820_2883/episode_00063_seed_2883.json \
  --output artifacts/selfplay_review_candidates_3001_3003_2883.json
```

The next correction experiment should score owner, source, and resource loss
at removal target prompts and at the earlier activation choice; compare it
with the unchanged policy on held-out decks and seats. Set preference for
Flip monsters needs the same comparison. Review Scapegoat timing separately
because an early activation or a pass can both be right in specific board
states. The offline viewer now exports learner-seat corrections to these
games as `self_play_review`, which the trainer tracks separately from human
gameplay and policy-checkpoint reviews. Do not turn the sampled actions
themselves into expert demonstrations.

Three SHA-256-bound learner-seat review labels preserve the legal alternatives
at the Faith, Heavy Storm, and Breaker frames in
`examples/annotations/selfplay_value_seed3001_faith_set.review.json`,
`selfplay_value_seed3002_heavy_hold.review.json`, and
`selfplay_value_seed3003_breaker_enemy.review.json`. A fixed-state scorecard
replay-verified their three source duels, audited visibility, and confirmed
that neither exact replay nor seed was in the unchanged feature-19 parent's
training provenance. That parent ranked the reviewed Faith Set **5th of 6**
(reviewed minus recorded summon logit **−2.253**), Heavy Storm hold **1st of 2**
(**+0.583**), and Breaker's enemy target **2nd of 3** (**−0.045**). The
parent's best Faith action at that frame was to Set a different Spell/Trap,
so the pairwise summon-versus-Set margin does not prove it would greedily
Summon Faith in a complete duel. The Heavy Storm error in this sample is
exploration, whereas the target and Flip preferences expose weaker fixed-state
ordering. Three states are not a strength estimate.

The ignored scorecard is `artifacts/feature19_selfplay_review_scorecard.json`
(SHA-256 `28e92ac9c5b602277959bb7a528f6d10dd1cbd76f4c40c9c8fbe999c625ed501`).
Reproduce it with `scripts/score_reviewed_decisions.py`, the feature-19 parent
checkpoint, and the three matching replay/annotation pairs above. Regenerate
the ignored source replays first with the four-game value-baseline smoke command
in [evaluation](evaluation.md); a fresh run reproduced all four decision
streams exactly after excluding only the added recording-provenance fields.
The MST frame is intentionally not a one-choice label: two opposing Set Spell/Traps
are legal and neither hidden identity is available to the acting player.
Its actionable preference is for an opposing target over the own Dust Tornado,
without claiming which opposing slot is better. The separate preference
format below represents both acceptable opponent slots while preserving the
recorded own-card target as the disfavored action.

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/score_reviewed_decisions.py \
  --checkpoint checkpoints/tactical_v3_fv19_2500_2503.pt \
  --case replays/selfplay_value_smoke_3000/episode_00001_seed_3001.json \
         examples/annotations/selfplay_value_seed3001_faith_set.review.json \
  --case replays/selfplay_value_smoke_3000/episode_00002_seed_3002.json \
         examples/annotations/selfplay_value_seed3002_heavy_hold.review.json \
  --case replays/selfplay_value_smoke_3000/episode_00003_seed_3003.json \
         examples/annotations/selfplay_value_seed3003_breaker_enemy.review.json \
  --output artifacts/feature19_selfplay_review_scorecard.json
```

The new `examples/preferences/` files express all four audited corrections
as preferred-versus-disfavored **sets** of legal action indices. The MST case
prefers both opposing hidden backrow slots over the recorded own Dust
Tornado, without picking an arbitrary winner between those two unknown
cards. Breaker's case prefers its unique opposing target over either own Set
Trap Dustshoot. The learner seat, replay SHA-256, and legal indices are
validated after native replay verification and a visibility audit. The
unchanged feature-19 parent scored preferred-minus-disfavored log-mean-exp
margins of **−2.253** for Faith, **+0.583** for Heavy Storm, **+0.019** for
Breaker, and **−0.515** for MST. Positive margins mean the preferred set's
mean exponential score was higher; a positive set margin does not guarantee
the greedy choice belongs to that set. The parent greedily chose a preferred
action in only the Heavy Storm state. No source seed or exact replay was in
that parent's training provenance.

The ignored report is `artifacts/feature19_selfplay_preference_scorecard.json`
(SHA-256 `bc54a64bdf6ae1093cf5d816299c8d2c5ab451ddf1cbf641ed2fb86cb01a3bec`).
The scalar seed-2883 replay was regenerated with current recording metadata;
its full trajectory matched the earlier saved version after removing only
those added metadata fields. The original scalar checkpoint byte hash was
preserved as recorded in [evaluation](evaluation.md). An opt-in preference
trainer now consumes these four reviews; its corrected-state results and
held-out comparison are recorded in [evaluation](evaluation.md). Four fixed
states cannot establish a strength gain.

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/score_reviewed_preferences.py \
  --checkpoint checkpoints/tactical_v3_fv19_2500_2503.pt \
  --case replays/selfplay_value_smoke_3000/episode_00001_seed_3001.json \
         examples/preferences/selfplay_value_seed3001_faith.preference.json \
  --case replays/selfplay_value_smoke_3000/episode_00002_seed_3002.json \
         examples/preferences/selfplay_value_seed3002_heavy.preference.json \
  --case replays/selfplay_value_smoke_3000/episode_00003_seed_3003.json \
         examples/preferences/selfplay_value_seed3003_breaker.preference.json \
  --case replays/selfplay_fourroles_2820_2883/episode_00063_seed_2883.json \
         examples/preferences/selfplay_scalar_seed2883_mst.preference.json \
  --output artifacts/feature19_selfplay_preference_scorecard.json
```

## Extended visible-state shortlist, feature-19 checkpoint

`scripts/audit_policy_replays.py` now uses pinned printed card metadata to
surface Normal Summons of Flip monsters with at most 500 printed ATK when a Set
of the same card was legal. It also flags Tribe-Infecting Virus activations
with no face-up opposing monster and Tribe Type announcements that destroy an
own face-up monster while an offered Type would hit a visible opposing monster.
The reviewer sees only the acting player's observation and legal actions.
These are prompts for review, not automatic labels: a face-up Flip summon or
deliberate own-monster destruction can be correct in a particular line.

All eight saved feature-19 policy games from seeds 2640–2647 replay-verified
against today's pinned assets. Their 5,478 decisions include 2,780 choices
matched exactly to `tactical_v3_fv19_2500_2503.pt`. The extended shortlist
found **three Magician of Faith face-up summons** with a legal Set alternative
(viewer frames 536 of `policy_batch_v19_cc_war_2641_p0.json`, and 93 and 906
of `policy_batch_v19_daryl_cas_2647_p1.json`). The Daryl/Cas policy also
activated Tribe with no face-up opposing monster at frames **250** and **356**;
`pass` was legal before it discarded a card. At frame **115** of
`policy_batch_v19_jesse_daryl_2644_p1.json`, it named Spellcaster, hitting
two of its own face-up Gravekeeper's Spies, while Beast was a legal Type that
would hit four opposing Sheep Tokens. That last choice closely matches the
reported self-destruction mistake and has a player-visible alternative; the
earlier Tribe activations should be reviewed at the activation decision, not
at their later forced Type prompts.

The ignored report is
`artifacts/policy_review_candidates_batch_extended_2640_2647.json` (SHA-256
`dc8a66535c12833a6fddb85b0e596671362bc6443ab9b3cbf105e6f17f3f1f5e`).
Regenerate it with `--checkpoint checkpoints/tactical_v3_fv19_2500_2503.pt`
and the eight `replays/policy_batch_v19_*json` files. It contains 14 review
prompts in total, including the previously reported Heavy Storm and
Scapegoat prompts. No new training labels or policy weights were changed.

An optional guard v4 changed all three saved Faith choices to Set and retained
the guard v3 corrections at those three Tribe decisions. A complete guard-v4
duel replay-verified, but v4 scored 23–25 directly against v3 on held-out deck
compositions and seeds; see [evaluation](evaluation.md). This preference is an
experiment, not a promoted stronger agent. Use `--tactical-guard
--weak-flip-guard` when recording or evaluating guard v4; recordings identify
it as `greedy_tactical_guard_v4` so the replay auditor can reproduce its
decisions without confusing it with v3.

## Independent policy-seat review, seeds 2641, 2644, and 2647

The four trajectories below identify the **greedy feature-19 policy** by
checkpoint SHA-256 `fe197724523b33a8d555e90ab9f7b669dab2081b000346b9b31d1788d7e07fc2`
and `demonstrator_seat` in their metadata. Its opponent is
TacticalHeuristicAgent v3. All four complete duels replay-verified against
the pinned native assets (712, 649, 801, and 1,212 decisions respectively).
The shortlist now flags the two Soldier self-targets and Typhoon's own-card
target; the other two findings came from independent frame review. Viewer
frames are one-based; each parenthesized number is the JSON index.

| Replay and policy seat | Frame | Player-visible decision and legal alternative | Improvement candidate |
| --- | --- | --- | --- |
| `policy_batch_v19_cc_war_2641_p0.json`, P0 | 219–220 (218–219) | P0 voluntarily activates its face-up Black Luster Soldier's banish effect, then selects **that same 3000 ATK Soldier**. An opposing Set monster is the other legal target. The Soldier is banished by frame 223. Opponent LP is 700. The Set monster's identity is unknown to P0. | Do not select the source Soldier when a legal opposing target exists unless a concrete payoff for self-banish is present. Separately compare effect use with keeping a ready attacker. A legal-target mask alone does not value that activation. |
| `policy_batch_v19_daryl_cas_2647_p1.json`, P1 | 740–741 (739–740) | P1 again activates its own Black Luster Soldier and selects itself for banishment. The opponent's face-up Sinister Serpent is a legal alternative; two own Sheep Tokens are also offered. The Soldier is banished by frame 744. | Add a visible target/source relation and explicit value of preserving a 3000 ATK body. Check the activation decision as well as the target prompt. |
| `policy_batch_v19_cc_war_2641_p1.json`, P1 | 154–158 (153–157) | P1 chains Mystical Space Typhoon from hand in its own Draw Phase with no pending chain; `pass` is legal. It targets its own Set Solemn Judgment at frame 156, although an opposing Set Spell/Trap is also a legal target. At frame 158 P1 passes instead of chaining Solemn, and Solemn leaves the field. The opposing Set card's identity is unknown to P1. | Prefer preserving one's own live response card. For a targeted removal effect, score the public owner and zone of every legal target; also penalize unsolicited activation when there is no visible threat. |
| `policy_batch_v19_jesse_daryl_2644_p1.json`, P1 | 39 (38) | P1 Normal Summons Gravekeeper's Spy in 1200 ATK while the opponent controls a Set monster, face-up Swords of Revealing Light, and four Set Spell/Traps. Setting that same 2000 DEF Flip monster is legal. | Value the printed Flip effect and defensive position before committing a normal summon; score the immediate attack opportunity from visible restrictions. |
| `policy_batch_v19_daryl_cas_2647_p1.json`, P1 | 410 (409) | On P1's own Main Phase, P1 activates Scapegoat **from hand** while another Scapegoat is already Set and the opponent has only a face-up 300 ATK Sinister Serpent. Setting the hand copy, proceeding to Battle, or ending the turn is legal. There is no pending chain or attack. | Consider Set from hand and hold the existing copy for the opponent's turn. The guard must distinguish hand and field copies and the current turn owner. |

All five target, timing, and summon findings were checked directly against the
saved legal lists and next states. They are action-level evidence, not proof that
changing the move would reverse a game's result. The separate guard-v4 duel
`replays/policy_v4_guard_daryl_cas_2647_p1.json` also replay-verified for
399 decisions; this small review found no equally clear example in it. That
does not establish the guarded policy's overall strength.

An opt-in guard v5 filters own BLS or Typhoon targets at these target prompts
when an enemy target is legal. It changes all three saved choices to opposing
targets, but does not evaluate the earlier activation. A held-out 48-duel
comparison scored 25–23 against v3 with an interval including 50%; see
[evaluation](evaluation.md). Keep v5 experimental.

Three SHA-256-bound `policy_review` annotations preserve the offered opposing
targets at these decisions without calling them human demonstrations:
`examples/annotations/feature19_bls_cc_war_2641_p0.review.json`,
`examples/annotations/feature19_mst_cc_war_2641_p1.review.json`, and
`examples/annotations/feature19_bls_daryl_cas_2647_p1.review.json`.
`scripts/score_reviewed_decisions.py` replay-verifies each source duel,
checks the visibility audit and legal annotation indices, then reports the
checkpoint's raw action-score margin. Across these three choices, the
unchanged feature-19 checkpoint ranks the annotated opposing targets
**2nd, 3rd, and 4th** of their legal sets, respectively, with annotated-minus-
recorded logit margins of **−1.011, −0.478, and −0.881**. The earlier five
seed-2612 review choices all rank 2nd. None of the four source trajectories
or their seeds appear in this checkpoint's training provenance. The ignored
eight-label report is `artifacts/feature19_review_scorecard.json` (SHA-256
`0d949e1d64145cef908937f531a27c3b9dac6458bc4d41bb49cda4bf4fb4a9a8`).
This is a fixed-state diagnostic; eight reviewer choices cannot establish a
policy's competitive strength or justify training on their replay outcomes.

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/score_reviewed_decisions.py \
  --checkpoint checkpoints/tactical_v3_fv19_2500_2503.pt \
  --case replays/policy_audit_v19_jesse_daryl_seed2612.json examples/annotations/feature19_seed2612.review.json \
  --case replays/policy_batch_v19_cc_war_2641_p0.json examples/annotations/feature19_bls_cc_war_2641_p0.review.json \
  --case replays/policy_batch_v19_cc_war_2641_p1.json examples/annotations/feature19_mst_cc_war_2641_p1.review.json \
  --case replays/policy_batch_v19_daryl_cas_2647_p1.json examples/annotations/feature19_bls_daryl_cas_2647_p1.review.json \
  --output artifacts/feature19_review_scorecard.json
```

The updated local shortlist independently replay-verified and checkpoint-matched
the three trajectories containing self-targets (712, 649, and 1,212 decisions;
368, 320, and 632 policy choices). It found the Soldier choices at frames 220
and 741 and Typhoon at frame 156. Its ignored JSON report is
`artifacts/policy_review_candidates_self_target_2641_2647.json`. The command is:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/audit_policy_replays.py \
  --checkpoint checkpoints/tactical_v3_fv19_2500_2503.pt \
  replays/policy_batch_v19_cc_war_2641_p0.json \
  replays/policy_batch_v19_cc_war_2641_p1.json \
  replays/policy_batch_v19_daryl_cas_2647_p1.json \
  --output artifacts/policy_review_candidates_self_target_2641_2647.json
```

Reproduce the Mystical Space Typhoon line (change `--policy-seat` to `0` and
the output name to reproduce the first Black Luster Soldier line):

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/record_policy_match.py \
  checkpoints/tactical_v3_fv19_2500_2503.pt \
  --deck1 examples/decks/chaos_control_insids_worlds_2022.ydk \
  --deck2 examples/decks/warrior_montague_clash.ydk \
  --seed 2641 --policy-seat 1 --opponent tactical \
  --output replays/policy_batch_v19_cc_war_2641_p1.json
```

Reproduce the Daryl/Cas lines with the same recorder and checkpoint using
`--deck1 examples/decks/gravekeeper_daryl_gessler_indianapolis_2005.ydk`,
`--deck2 examples/decks/flip_control_cas_stomphorst_indianapolis_2005.ydk`,
`--seed 2647 --policy-seat 1 --opponent tactical`, and output
`replays/policy_batch_v19_daryl_cas_2647_p1.json`.

### Tribe Type choice from the verified policy replay

At viewer frame **115** (decision index 114) of
`replays/policy_batch_v19_jesse_daryl_2644_p1.json`, the greedy feature-19
policy's Tribe-Infecting Virus chose Spellcaster. The acting player's visible
field held two face-up Gravekeeper's Spies and Tribe; the opponent held four
face-up Sheep Tokens. The offered Type choices were Spellcaster, Machine, and
Beast. Spellcaster destroys the two own Spies, while Beast removes the four
opposing Tokens without hitting an own monster. This judgment uses only the
acting player's visible cards and published card Types. The complete
801-decision duel replay-verified and passed the visibility audit.

`examples/preferences/feature19_tribe_spies_tokens_2644_p1.preference.json`
binds that replay's SHA-256 and prefers Beast (legal index 2) over the
recorded Spellcaster (index 0); it leaves Machine unlabeled. The unchanged
feature-19 checkpoint ranks Beast third, with an almost-zero score margin
against Spellcaster (−0.00000018). Its old action encoding scaled the Type
bitmask by `2**32 - 1`, making these choices nearly identical in float32.
Opt-in feature version 20 encodes the exact Type bits. A same-data feature-20
clone still ranks Beast second and chooses Spellcaster in this state; after an
opt-in five-review preference update, Beast ranks first. Those are
**training-state diagnostics** for the update, not competitive evidence. The
held-out results and checkpoint hashes are in [evaluation](evaluation.md).

For the current-Type feature experiment, the original verified replay was
deterministically upgraded to a separate schema-v24 file, and the same
frame-115 review was rebound to its new SHA-256 in
`examples/preferences/feature21_tribe_spies_tokens_2644_p1.preference.json`.
The legal action list and indices are unchanged. This is a transfer of the
existing judgment, **not a second independent review**. A same-data
feature-21 clone ranks Beast first at this held-out frame, while a feature-20
control ranks it second; the 64-duel match did not establish stronger play.

## Seed 2202, policy versus CombatHeuristicAgent v3

Replay: `replays/policy_vs_combat_2202.json`. Policy P0 uses
`combat_fourdeck_fv17_v3_17000_17003.pt`; P1 is CombatHeuristicAgent v3.
This is a saved feature-17 checkpoint experiment, not the later tactical-v3
feature-18/19 checkpoints discussed below. Do not transfer its individual
mistakes or match result to those later weights without testing them.

| Viewer frame | Actor | Visible mistake | Response |
| --- | --- | --- | --- |
| 1 | Policy P0 | Activates Scapegoat from hand in its own Draw Phase with `pass` legal. | Optional tactical guard waits for Battle Phase, End Phase, or a threat to the Set card. |
| 19 | Policy P0 | Activates Heavy Storm with one own Set Spell/Trap and no opposing backrow. | Guard defers activation. |
| 103 | Policy P0 | Breaker destroys its own Set Spell Shield Type-8 although three opposing Spell/Traps are legal targets. | Guard removes own targets when an opposing target exists. |
| 171 | Policy P0 | Sends Wave-Motion Cannon to the Graveyard for 1000 damage with no visible immediate threat. | Review item, medium confidence. A fixed early-use ban needs more evidence. |
| 275, 345, 383 | CombatHeuristicAgent v3 P1 | Tribe-Infecting Virus names a race that destroys only its own monsters. | Experimental TacticalHeuristicAgent v2 reads public printed races from the pinned CDB and values visible targets. The old v3 baseline stays unchanged for reproducible past evaluations. |
| 311–314 | Policy P0 | Uses Enemy Controller from hand in its own Draw Phase to switch an opposing 1200 ATK / 2000 DEF Gravekeeper's Spy into Defense Position. | Guard defers unchained Draw/Standby activation. The target valuation problem remains open. |

The tactical guard is opt-in for the learned policy with `--tactical-guard` in
`scripts/record_policy_match.py` and `scripts/evaluate_policy.py`. It filters
legal actions based on public state; it does not change simulator legality or
checkpoint weights. These filters encode common preferences, not universally
correct plays. For example, destroying one's own Spell/Trap can sometimes be
valuable, and Scapegoat can be used earlier to block an attack or answer
removal. Schema v23 now records the turn player separately from the acting
player; new recordings defer Scapegoat until the opponent's Battle or End Phase
unless the Set card is threatened. Older trajectories lack that field and use
the broader timing rule. A stronger policy also needs opponent-aware value
estimates and training
examples for these exceptions.

To inspect the guarded seed 2202 duel, open
`replays/policy_guard_vs_combat_2202.html`. The JSON trajectory is independently
replayed through the native engine before the recorder accepts it. Because the
guard changes early actions, later frame numbers differ from the original.

## Feature-19 learned policy versus TacticalHeuristicAgent v3, seed 2612

Replay: `replays/policy_audit_v19_jesse_daryl_seed2612.json`. This is an
on-policy, complete 534-decision duel with the feature-19 checkpoint
`tactical_v3_fv19_2500_2503.pt` (SHA-256
`fe197724523b33a8d555e90ab9f7b669dab2081b000346b9b31d1788d7e07fc2`).
Trajectory metadata identifies the **greedy policy on P0**, TacticalHeuristicAgent
v3 on P1, seed 2612, Jesse Goat Control versus Daryl Gravekeepers, and
inference version 5. Native replay verification succeeded; P1 won. Later
experimental timing warm-start checkpoints exist, so this is evidence about
the named feature-19 checkpoint only. The replay is an ignored local artifact;
regenerate it with the command below.

| Viewer frame (JSON index) | P0's visible state and chosen action | Legal alternative and improvement |
| --- | --- | --- |
| 11 (10) | On turn 1, P0 activates Heavy Storm with its own Set Torrential Tribute and Metamorphosis as the **only** Spell/Traps. After resolution the field has no Spell/Traps. | `end_phase` or other legal actions preserve both cards. The optional tactical guard rejects this activation on the saved observation; train the policy to value resource balance directly, including exceptions where clearing one's own backrow helps. |
| 142–143 (141–142) | P0 has declared an attack with its 1700 ATK D.D. Assailant against an unknown Set monster. With no pending chain or newly revealed threat, it chains its own Book of Moon and targets the attacker. The attacker is Set and its attack ends. | `pass` was legal at frame 142. Score response cards against the effect of *continuing the already chosen attack*; a card use that cancels that attack needs a concrete reason. |
| 163 and 181 (162 and 180) | P0 chains Royal Decree to the opponent's Gravekeeper's Spy monster effect while its own Sakuretsu Armor is Set. Decree cannot negate that monster effect. Later P0 activates Sakuretsu Armor against an attack despite its own Royal Decree still face-up; the attacker remains after resolution and Sakuretsu is spent. | `pass` was legal at both decisions; Scapegoat was also legal. Add visible continuous-effect context to Trap action valuation, and penalize activating a Trap while one's own Royal Decree negates it. The earlier Decree activation also merits a separate check because it disables the policy's own defense. |
| 209, 288–339, 469–470 (208, 287–338, 468–469) | P0 repeatedly passes with Set Scapegoat legally chainable. Frame 209 is the opponent's End Phase with no own monster and three opponent monsters. On turn 8 it passes at Battle Start and several Battle Step prompts with **zero own monsters**, four opposing monsters, and 6500 LP; by the End Phase it has 2600 LP and still passes. At the opponent's later End Phase it has 500 LP and still passes. | Activating at the opponent's End Phase or in response to an attack would create blockers without the same-turn summon restriction carrying into P0's next turn. The timing guard only removes premature uses; it does not force useful activation. Add labeled defensive and End Phase examples, then test both missed defenses and false-positive activations on held-out games. |

On these saved decisions, the optional tactical guard changes frame 11 away
from Heavy Storm and now removes frame 181's Sakuretsu Armor while a face-up
Royal Decree would negate it. It does **not** change the Book of Moon or
Scapegoat choices. This is an off-policy diagnostic on fixed observations;
once a different action is taken, the rest of the duel changes, so it is not
a measured match-strength gain. A small paired held-out check is recorded in
[evaluation](evaluation.md); it does not establish a gain either. No reviewer
reveal was used to identify an opponent Set card.

Five high-confidence legal alternatives from this game are saved as
`examples/annotations/feature19_seed2612.review.json`. They use the separate
`policy_review` provenance and only the policy seat. A parent-preserving
training probe learned the Scapegoat choices in fixed states but did not
improve a 64-game held-out direct match; see [evaluation](evaluation.md).

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/record_policy_match.py \
  checkpoints/tactical_v3_fv19_2500_2503.pt \
  --deck1 examples/decks/goat_control_jesse_twohig_indianapolis_2005.ydk \
  --deck2 examples/decks/gravekeeper_daryl_gessler_indianapolis_2005.ydk \
  --seed 2612 --policy-seat 0 --opponent tactical \
  --output replays/policy_audit_v19_jesse_daryl_seed2612.json
```

## Repeatable policy replay shortlist, seeds 2640–2647

`scripts/audit_policy_replays.py` replays each complete duel against the pinned
native assets, runs the legal-choice visibility audit, verifies every recorded
policy action against the named checkpoint and inference version, then searches
**only the policy seat's player-visible decisions** for review candidates.
It reports selected Heavy Storm with only other own backrow, Sakuretsu under
visible Royal Decree, own-only Torrential or Ring use, and Scapegoat passes in
an opponent Battle or End Phase with an open monster field. Repeated priority
passes in the same turn and phase are collapsed. The script never produces
training labels or claims that each candidate is a mistake; the reviewer must
check card context, alternatives, and later outcomes.
It also flags a Black Luster Soldier choosing itself as a target and a
Mystical Space Typhoon choosing an own card when an opposing target was offered.
The recorder now tags the updated opt-in guard as
`greedy_tactical_guard_v3`; the audit rejects older guard versions rather
than silently rescoring them with changed filters. A guarded seed-2648
Chaos Return/Warrior duel replay-verified for 803 decisions, and all its
checkpoint actions reproduced under the v3 tag.

Eight new greedy feature-19 checkpoint games against TacticalHeuristicAgent v3
completed and replay-verified, totaling **5,478 decisions**, including **2,780
checkpoint-matched policy decisions**. Chaos Return and
Chaos Control each played Warrior with the policy in both seats; four other
games paired Jesse Goat Control, Matt Goat Control, Daryl Gravekeepers, and Cas
Flip Control at seeds 2644–2647. The shortlist found **eight candidates**:
one Heavy Storm, six Battle Phase Scapegoat passes, and one opponent End Phase
Scapegoat pass. These eight games are a diagnostic sample, not a balanced
strength estimate. Both batches passed the separate visibility audit.

The strongest new finding is viewer frame **785** of
`replays/policy_batch_v19_jesse_daryl_2644_p1.json`: policy P1 activated a
previously Set Heavy Storm while its own face-up pre-errata Necrovalley was
the only *other* Spell/Trap on the field. The opponent had no backrow and
`battle_phase` was legal. The opponent had 100 LP and a face-up 1500 ATK
monster; P1 had a ready 1600 ATK Breaker, so proceeding to battle offered an
immediate visible winning attack. The Storm consumed the policy's Field Spell
without removing an opposing Spell/Trap. This is one action-level resource
error in a game P1 eventually won, not evidence of an outcome change.
Open `replays/policy_batch_v19_jesse_daryl_2644_p1.html#decision=785` for the
player-visible frame.

Frames **849** and **867** of
`replays/policy_batch_v19_jesse_cas_2646_p0.json` merit review: P0 had no
monsters and passed on a legal Set Scapegoat during the opponent's Battle Step
at 2400 LP, then again at that opponent's End Phase at 1300 LP after taking
1100 damage. In contrast, frames 132 and 137 of the Chaos Control/Warrior
game show only one 2000 ATK attacker against 6000 LP; preserving Scapegoat
there may be sound. None of these seven timing prompts has been added as a
training label. The classifier uses no future state; the damage comparison
above is a reviewer observation after the game.

The two ignored local shortlist reports are
`artifacts/policy_review_candidates_batch_2640_2641.json` (SHA-256
`fb861d1004ab3ceb8259973045efe22d156bd6a873fa0c7a050bfaad3904c48b`)
and `artifacts/policy_review_candidates_batch_2644_2647.json` (SHA-256
`d8eb6361a54c35358eee2febf84b8098f1470fc0671242de1e0a7fa396768cdb`).
For example, regenerate the strong Heavy Storm case and its shortlist with:

```bash
OMP_NUM_THREADS=1 .venv/bin/python scripts/record_policy_match.py \
  checkpoints/tactical_v3_fv19_2500_2503.pt \
  --deck1 examples/decks/goat_control_jesse_twohig_indianapolis_2005.ydk \
  --deck2 examples/decks/gravekeeper_daryl_gessler_indianapolis_2005.ydk \
  --seed 2644 --policy-seat 1 --opponent tactical \
  --output replays/policy_batch_v19_jesse_daryl_2644_p1.json
PYTHONPATH=src .venv/bin/python scripts/audit_policy_replays.py \
  --checkpoint checkpoints/tactical_v3_fv19_2500_2503.pt \
  replays/policy_batch_v19_jesse_daryl_2644_p1.json \
  --output artifacts/policy_review_candidates_2644.json
```

## Scapegoat turn-owner timing probe, seed 52

`scripts/generate_scapegoat_timing_probe.py` creates a complete, native,
replay-verified 711-decision synthetic duel with checked-in fixture decks.
Seat 1 Sets Scapegoat, passes at the opponent's End Phase on turn 3 to keep
the card available, passes on its own End Phase on turn 4, then activates it
on the opponent's End Phase on turn 5. These are viewer frames **21, 29, and
36**. The probe deliberately holds Scapegoat through the first opportunity;
it tests whether the later choices are distinguishable, not whether waiting
an extra turn is optimal. The fixture has no human-skill label and must not
be counted as human demonstration data.

Both `tactical_v3_fv18_2500_2503.pt` and `tactical_v3_fv19_2500_2503.pt`
chose `pass` at all three frames when scored off-policy. The optional tactical
guard also left the final `pass` intact: it filters bad timings, but does not
force Scapegoat activation at a good one. This is a concrete remaining policy
mistake, not evidence that either model is stronger. The generated replay is
`replays/scapegoat_end_timing_probe_seed52.json` (SHA-256
`39dd1ab9962555f0cc413720736d632c0bbe109edb2d3684a797beb6922cdbe0`),
with an offline viewer at the matching `.html` path. Reproduce the policy
comparison with:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/generate_scapegoat_timing_probe.py \
  --checkpoint checkpoints/tactical_v3_fv18_2500_2503.pt \
  --checkpoint checkpoints/tactical_v3_fv19_2500_2503.pt
```

The generator also writes a `.labels.json` file containing only the three
scripted actions, tagged `scripted_scenario`. The trainer accepts these as
`synthetic_annotation` after replay and visibility verification; see
[ML notes](ml.md). A targeted warm-start fit learned the final activation
on four other shuffle seeds, but its paired competitive result remains
inconclusive; see [evaluation](evaluation.md).

The next learning experiment should include genuine, authorized End Phase
choices from skilled players or explicitly marked synthetic timing examples
in training, then evaluate on separate native scenarios and held-out matches.

### Published-deck timing context

The same generator accepts `--deck-a` and `--deck-b`. Native duels with the
published Daryl Gravekeepers list opposite Cas Flip Control (seed 2601),
Matt Goat Control (seed 2604), and Jesse Goat Control (seed 2610) each reach
the scripted End Phase choices at viewer frames **21, 29, and 36**. Their
complete duels replay-verify, with 1,119, 1,255, and 872 decisions. Open
`replays/scapegoat_timing_jesse_seed2610.html` for the separate Jesse
timing replay. The parent checkpoint had already seen Jesse's Main Deck in
other duels. The generator exports both the original three-choice
`.labels.json` and a `.curriculum.labels.json` containing 19 choices per
duel: early Draw, Standby, and Main Phase passes, a Scapegoat Set, and the
later End Phase activation. All labels are marked synthetic.

```bash
PYTHONPATH=src:. .venv/bin/python scripts/generate_scapegoat_timing_probe.py \
  --seed 2610 \
  --deck-a examples/decks/gravekeeper_daryl_gessler_indianapolis_2005.ydk \
  --deck-b examples/decks/goat_control_jesse_twohig_indianapolis_2005.ydk \
  --output replays/scapegoat_timing_jesse_seed2610.json
PYTHONPATH=src:. .venv/bin/python scripts/render_replay.py \
  replays/scapegoat_timing_jesse_seed2610.json --reviewer-reveal \
  --output replays/scapegoat_timing_jesse_seed2610.html
```

The three-choice policy trained on Cas and Matt passed at the later opponent
End Phase in the Jesse replay. With the broader curriculum and a tenfold
`chain` label weight, it activated there and passed at Jesse's early Draw,
Standby, and Main Phase prompts. It also activated at the *earlier* opponent
End Phase, which may be reasonable. On a separate teacher holdout, it still
activated Scapegoat four times during an opponent Main Phase when the
teacher passed. The [evaluation log](evaluation.md) records the exact
agreement and tournament limits; this is not a promoted policy.

## Older CombatHeuristicAgent v2 versus RandomAgent, seed 17200

Replay: `replays/combat_fourdeck_holdout_cc_cr_17200/seed_17200_seat_1.json`.
Its metadata records CombatHeuristicAgent **v2 on P1** and RandomAgent on P0.
These are failures of an earlier baseline and its possible demonstration
labels, not observations of the current learned policy. The relevant decisions
use P1's player-visible observation; no reviewer-only card identity is needed.
The listed actions and alternatives were checked against the saved JSON. A
fresh native replay check of this older file currently stops at its recorded
asset-hash check (`ReplayMismatch: native assets differ from recorded
trajectory`), so this section does not claim verification against today's
native assets.

| Viewer frame (JSON index) | Visible state and chosen action | Better legal choice and follow-up |
| --- | --- | --- |
| 61–62 (60–61) | On turn 3 Draw Phase, P1 has only its own face-up 1400 ATK Dekoichi on the Monster Zone. It chains Set Ring of Destruction with no pending chain and must target that Dekoichi. Life Points are P1 8000, P0 5600; resolution brings them to 6600 and 4200. | `pass` was legal at frame 61. Preserve the monster and Ring for an opposing target, unless self-destruction enables a verified advantage. Teach the agent to check for a safe, valuable opposing target **before** activating a targeted removal card. |
| 72 (71) | With no monsters on either side, P1 Normal Summons Magician of Faith in 300 ATK. The legal list also offers `set_monster` for the same card. | Set the Flip monster to retain its Flip effect and avoid presenting a weak attacker. This is a preference, not a simulator rule: a face-up summon could be right in a specific lethal or combo line. Use printed Flip metadata and visible combat context. |
| 76 (75) | Immediately after that summon, P1 chains its own Set Torrential Tribute while its face-up Magician of Faith is the only monster on the field. `pass` is legal. | Pass; using the Trap here destroys only P1's monster and consumes the Trap. The tactical baseline now filters this pattern, but promotion still requires held-out duel evaluation. |
| 147 (146) | P1 activates Scapegoat from hand in its own Draw Phase with no pending chain. `pass` is legal. | Defer to a useful defensive timing or the opponent's End Phase; Set it first when possible. The current observation schema records turn owner so the new timing guard can distinguish the two players' End Phases. |

The Ring example is especially useful for labeling activation *and* target
selection: at frame 62 the own monster is the only legal target, so choosing a
different target at that prompt was impossible. The actionable earlier
decision is frame 61. Likewise, the Magician of Faith and Torrential sequence
should be assessed as two decisions with separate legal alternatives, rather
than a single unexplained loss.

## Repeatable review process

1. Record each match with the agent type/version, seat, seed, deck paths, and
   checkpoint hash in trajectory metadata.
2. Sample decisions in the viewer. Flag only mistakes supported by visible
   board, phase, chain, and legal choices. Give the viewer frame and agent.
3. Reopen the corresponding JSON decision to verify the action and alternatives.
4. Add a targeted regression test. Keep any play preference separate from the
   engine's historical legality tests.
5. Replay a complete duel, then evaluate against an unchanged checkpoint on
   held-out decks and seeds. A single improved frame or win is not sufficient
   evidence of stronger play.

## Additional self-destruction review prompts

The reviewer now flags a Tribe-Infecting Virus Type declaration that would
destroy only the acting player's face-up monsters even when **no** opposing
Type was available, as well as a Ring of Destruction choice targeting the
acting player's monster when a legal opposing face-up target has known ATK
below the acting player's LP. These remain human-review candidates: a
friendly monster may have a useful Graveyard effect, and chains may change
the field before resolution.

Re-auditing the saved greedy-policy game
`replays/policy_batch_v19_daryl_cas_2647_p1.json` verified all **1,212**
decisions and reproduced **632/632** policy choices. The new Tribe prompt
found two concrete decisions. At viewer frame **252**, after discarding
Sangan, the policy declared Warrior with no opposing monster and destroyed
its own Airknight Parshath. At frame **358**, after discarding Tsukuyomi,
it declared Aqua with only its own Tribe-Infecting Virus face-up and destroyed
Tribe. The auditor also flags the earlier activations at frames 250 and 356,
where `pass` was legal. A useful correction is to preserve the discard and
monster when no opposing Type can be hit, then test any proposed exception
against later game outcomes. No claim of improved win rate follows from the
new flags. The generated, ignored audit report is
`artifacts/policy_review_new_candidates_2647.json` (SHA-256
`d3b34dc763030383a2c77b621429e5bcae8ada58c23bea126a2f231137372bc7`).

```bash
OMP_NUM_THREADS=1 .venv/bin/python scripts/audit_policy_replays.py \
  replays/policy_batch_v19_daryl_cas_2647_p1.json \
  --checkpoint checkpoints/tactical_v3_fv19_2500_2503.pt \
  --native-root .cache/goat-ai \
  --output artifacts/policy_review_new_candidates_2647.json
```

The schema-v24 version of that replay also has a SHA-256-bound review at
`examples/preferences/feature21_tribe_empty_board_2647_p1.preference.json`:
at viewer frames **250** and **356**, `pass` is preferred over activating
Tribe when no opposing monster is face-up. These are two decisions in one
game, not independent duel evidence. The unchanged feature-21 checkpoint
already ranked `pass` first at both frames, with respective logit margins
**+0.437** and **+0.490**. No update was fitted to these already-correct
choices.

## Feature-21 Magician of Faith review

In the complete seed-3700 feature-21 policy versus TacticalHeuristicAgent
replay (`replays/fv21_vs_tactical_3700_p0.json`), the policy Normal Summoned
Magician of Faith in 300 ATK at viewer frame **22**. Both Monster Zones were
empty, `set_monster` for the same Faith was legal, and its own Graveyard
already contained Book of Moon, Graceful Charity, and Upstart Goblin. Setting
Faith preserves the Flip effect and avoids exposing a weak attacker. The
policy's exact replay verified all **358** decisions; the audit reproduced
**177/177** policy choices and found this one candidate. The ignored replay
SHA-256 is `fd5b8dc9830bdecd826a83b673a6c27994018b8af24775eb53c9f8b7dea7732a`.

`examples/preferences/feature21_faith_set_3700_p0.preference.json` binds
that exact replay (SHA-256 of the preference file:
`d7065658f0fe0860f518085dfb5cb4c3f385c8860ddee0183cd90e841db11308`)
and prefers the legal Faith Set over its recorded Normal Summon. The parent
ranked Set **4th of 10**. A one-review parent-KL child moved Set to **1st**
at that training frame, but its separate 64-duel held-out match did not
establish a strength gain. This is a reviewed tactical preference, not a
historical legality ruling; [evaluation](evaluation.md) records the full
comparison and deck splits.

### Cross-deck Faith and Ring follow-up

Four additional feature-21 greedy-policy games against TacticalHeuristicAgent
v4, seeds **3900–3903**, used Chaos Control, Matt Peddle Goat Control, Flip
Control, and Chaos Turbo as the policy's decks. All four complete games
replay-verified, passed the visibility audit, and reproduced every recorded
policy choice; their ignored aggregate review report is
`artifacts/fv21_review_scan_3900_3903_audit.json` (SHA-256
`0e75c5ca97ba4dcf8640c1bb92b447ef19ff69ae0755b9daf3eb125142aa4a20`).

At seed **3900** viewer frame **15**, the policy Normal Summoned a 300-ATK
Magician of Faith with no monsters on either side and Pot of Greed already in
its Graveyard; setting that exact card was legal. At seed **3903** frame
**119**, it again Normal Summoned Faith despite a legal Set and useful Book of
Moon and Delinquent Duo in its Graveyard. At frame **466** of that same game,
its Ring of Destruction targeted its own face-up Faith while an opposing
2300-ATK Chaos Sorcerer was a legal target and the acting player had 5800 LP.
Set Faith and targeting Sorcerer are review preferences from player-visible
facts, not claims that every board state has those same best moves.

The two replay-bound files
`examples/preferences/feature21_faith_set_3900_p0.preference.json` and
`examples/preferences/feature21_faith_ring_3903_p0.preference.json` encode
these three exact alternatives. Along with seed 3700's Faith preference, the
unchanged parent ranked all four preferred actions below its recorded move.
A parent-KL child ranked all four first at their training frames, but its
separate 64-duel held-out comparison scored **31–32–1** versus the frozen
parent. See [evaluation](evaluation.md); the child is not promoted.

### Independent replay-agent audit of feature-21 policy

An independent read-only audit replay-verified the complete seed-3900,
seed-3901, and seed-3903 policy games against the pinned native engine. The
recorded feature-21 policy used greedy action selection; its checkpoint SHA-256
was `c6cc59780d665edf2c83b143d1b371e9aa05fcfff5ac988edfc48613ccd21011`.
The reviewer used only the acting player's observation and legal actions.

| Replay | Viewer frame / JSON index | Recorded choice and visible alternative | Improvement hypothesis |
| --- | ---: | --- | --- |
| Seed 3900 | 15 / 14 | Normal Summon Magician of Faith at 300 ATK into an empty field; Set the same card was legal. | Score Flip-effect readiness and low-ATK exposure. |
| Seed 3901 | 663 / 662 and 668 / 667 | Pass on opponent Turn 18 End Phase with Set Scapegoat and no own monsters, then activate that Scapegoat on own Turn 19 Main Phase; opponent had three face-up monsters and activation was legal at the earlier prompt. | Account for turn owner and next-turn summon restriction when valuing Scapegoat timing. |
| Seed 3903 | 465–466 / 464–465 | Chain Ring of Destruction on opponent Draw Phase and target own 300-ATK Faith while opposing 2300-ATK Chaos Sorcerer was a legal visible target. | Score whether activation is timely and compare target owner, threat, and life-point effects. |
| Seed 3903 | 925 / 924 | Activate Heavy Storm with only own Set Trap Dustshoot in backrow and no opposing Spell/Trap; Set Storm and End Phase were legal. | Compare own and opposing resources before global removal. |

These are review hypotheses, not universal card rules. For example, sending
one's own LIGHT monster to the Graveyard can sometimes have follow-up value.
The reviewer also replay-verified
`replays/selfplay_fourroles_2820_2883/episode_00062_seed_2882.json`:
viewer frame 12 / index 11 contains a similar own-only Heavy Storm activation,
but that learner action was sampled with temperature **2.0**. It must not be
counted as a greedy feature-21 policy choice. The current
`scripts/audit_policy_replays.py` also accepts sampled `self_play_rl`
trajectories. It verifies the native replay and visibility boundary and
requires the learner seat, parent checkpoint hash, `sampled_softmax` mode,
and positive finite temperature. Its output marks sampled choices as
`not_reproduced_exploratory_sampling`, with `verified_policy_choices: null`.
Passing `--checkpoint` additionally checks that the named parent weights
match the recorded hash. Greedy `policy_evaluation` audit still requires
`--checkpoint` and reproduces every recorded policy choice.

The seed-2882 sampled replay audit verified **986** decisions and flagged
**one** Heavy Storm candidate. Its ignored report is
`artifacts/selfplay_episode62_review_audit.json` (SHA-256
`221bad1a9e1be1e84a3c13cb8c25b9ec67ec0113795f864a7bd469974d3b8a42`).

```bash
OMP_NUM_THREADS=1 .venv/bin/python scripts/audit_policy_replays.py \
  replays/selfplay_fourroles_2820_2883/episode_00062_seed_2882.json \
  --native-root .cache/goat-ai \
  --output artifacts/selfplay_episode62_review_audit.json
```

### Player review of Thunder Dragon and opponent responses

The complete feature-21 seed-3900 replay (SHA-256
`3b4f4846638163cc91f3f0525458f4efed65dc89b0650a07278ee15299bb3b35`)
contains two additional reviewed **policy-seat** choices. At viewer frame
**3**, Player 1 activated Pot of Greed while activating its hand Thunder
Dragon was also legal. Searching first would avoid the chance of drawing
another copy before removing copies from Deck. The Main Deck actually has
**three** Thunder Dragons, not one. At frame **12**, after Thunder Dragon
resolved, **two** remaining copies were selectable, but the policy chose the
empty `select_cards` option, adding none. These legal alternatives are bound
to the replay in
`examples/preferences/feature21_thunder_order_search_3900_p0.preference.json`.
This is a decision problem, not evidence that the deck contains only one copy
or that the engine failed to offer the search.

At frame **15**, the policy Normal Summoned Magician of Faith; setting it or
Normal Summoning Sinister Serpent were legal. At frame **23**, it selected
Faith as Metamorphosis material with no opposing monsters. Serpent was still
in hand at that target prompt, so it was not a legal alternative there; the
earlier summon decision created that constraint. The automated shortlist now
flags the Pot/Thunder order, empty search, weak Flip summon, and this
Metamorphosis material choice for review. It does not turn them into blanket
rules: Metamorphosis into Thousand-Eyes Restrict can have other defensive or
tempo value.

The same replay's Player 2 was **TacticalHeuristicAgent v4**, not the learned
policy. It used Solemn Judgment on Player 1's Sinister Serpent Normal Summon
at frame **99**, paying from 7000 to 3500 LP, then on Scapegoat at frame
**128**, paying from 3500 to 1750 LP; Pass was legal at both prompts. The
Scapegoat response is now an automated opponent-seat review candidate. The
summon-negation observation currently lacks an explicit pending summoned-card
identity, so the shortlist does not infer that Solemn's target was Serpent
from the field alone.

In the feature-21 seed-3901 replay, Player 2 Tactical v4 selected its own
Black Luster Soldier as its banish target at frame **158** while five opposing
monsters were legal targets. The opponent-seat audit flags it. Tactical v5
now uses the visible target guard and chose an opposing monster at the same
decision state. It leaves a self-target available when a visible own Snatch
Steal is equipped to that BLS; a temporary Brain Control change cannot yet
be identified reliably from the observation's current-controller field.
Re-recording seed 3901 against Tactical v5 produced a **649-decision** native
replay, verified to terminal, where frame 158 targeted the opposing monster:
`replays/fv21_vs_tactical_v5_3901_p0.json` (SHA-256
`780f12517a3cf80f23a59a384593c5025ff17616b82d2c2ec613681599d53041`).
Tactical v5 also passed on the recorded Scapegoat/Solemn state when replayed
through its agent API. These are baseline behavior fixes, not a demonstrated
competitive gain for the learned policy.

The ignored two-seat audit report is
`artifacts/fv21_user_notes_both_seats_audit.json` (SHA-256
`106ba4ee4c5be3f9f65bd9b8656bca396a3a610385fe106ed4c46aa0c42c0f05`).
It verifies the policy's greedy choices; opponent choices are labeled
`native_replay_only_not_agent_reproduced`, preserving their separate
provenance.

```bash
OMP_NUM_THREADS=1 .venv/bin/python scripts/audit_policy_replays.py \
  replays/fv21_review_scan_3900_3903/seed_3900_seat_0.json \
  replays/fv21_review_scan_3900_3903/seed_3901_seat_0.json \
  --checkpoint .cache/goat-ai/fv21_casdaryl_schema24_experiment.pt \
  --native-root .cache/goat-ai --include-opponent \
  --output artifacts/fv21_user_notes_both_seats_audit.json
```
