# Early replay decision audit

## Varied-deck own-card review additions (29 October 2026)

The [latest combined local queue](../.cache/goat-ai/own_removal_combined_queue_20261029_v3.html)
has **63** distinct decisions: the previous 55 and eight fresh flags from the
four-matchup seed-124900–124907 baseline. The additions include four idle
own-only Ring activations, three negative visible Heavy Storm trades, and one
MST chain to its own resolving one-shot card. The component queue is
`.cache/goat-ai/own_card_broad_review_124900_124907/queue.json` (SHA-256
`465f56552f510db49f56d1a1c712ea7e5392cb1d7d3f8c47d99e3b27c5ab6f93`).
All eight component source replays and 3,916 decisions replay-verified.
The combined builder verified **54** source replays and **35,899** decisions,
with no duplicate decision. Combined queue SHA-256:
`8f4ae31968981242e1d38dea7fe1a5a58f89937241fd035d097ea01fda29fdb3`.

```bash
./start_review_viewer.sh .cache/goat-ai/own_removal_combined_queue_20261029_v3.json
```

The prior v2 queue had no saved labels when v3 was built. Labels are not
silently imported from source queues; all new alternatives remain suggestions
until reviewed. To rebuild v3, pass
`own_removal_combined_queue_20261029_v2.json` and
`own_card_broad_review_124900_124907/queue.json` to
`scripts/combine_review_queues.py` with the v3 output path. The fresh
component queue came from `scripts/shortlist_policy_disagreements.py` with
the three categories named above as `--focus-audit-category` filters.

## Fresh own-card cases added to the combined queue (29 October 2026)

The [updated local review queue](../.cache/goat-ai/own_removal_combined_queue_20261029_v2.html)
contains **55** distinct decisions: the earlier 51 plus four fresh cases from
64 selected-v23/v1-guarded policy-versus-Tactical games. The new cases are two
optional Ring of Destruction activations with only friendly face-up targets,
one Ring own-target choice while an opposing target was offered, and one
Tribe-Infecting Virus Type declaration that would hit only friendly monsters
despite an opposing option. The queue builder verified all **46** source
replays and **31,983** decisions with the pinned native engine and visibility
audit. Queue SHA-256:
`75d8ea7433acc7083f348c9e350f200b036f0eb42043a8d4401e870490ce68a9`.

```bash
./start_review_viewer.sh .cache/goat-ai/own_removal_combined_queue_20261029_v2.json
```

The four additions are candidates, not accepted labels. The earlier combined
queue had no saved labels when v2 was built. The new queue does not import
labels from its component queues. Rebuild it with `scripts/combine_review_queues.py`
using `own_removal_combined_queue_20261029.json` and
`own_card_fresh_review_124100_124215/queue.json` as inputs and the v2 JSON
path as output. The fresh queue was created from the four flagged source
replays with `scripts/shortlist_policy_disagreements.py` and the three named
`--focus-audit-category` values.

## Combined own-card decision review (29 October 2026)

A [single local queue](../.cache/goat-ai/own_removal_combined_queue_20261029.html)
brings together **51 distinct** selected-v23 decisions: 17 Ring and Heavy
Storm cases, six focused own-card removal cases, and 28 MST activation or
non-use opportunities. The first group contains 14 idle Ring activations with
only friendly face-up targets. The focused group contains five Nobleman
decisions with only friendly Set monsters. The MST group contains 20 chosen
activations and eight non-uses. Review the optional activation or Pass when
that is the strategic mistake; a later target prompt may already be forced.

The queue builder rechecked **42** source replays and **29,540** decisions
against the pinned native engine and player-visibility audit. The JSON SHA-256
is `0238b3da547938a21493ee6c41ea447ef286ddc9370ed5c48806a96598b78d04`.
None of these prompts is a training label. The three source queues had no
saved server labels when combined, and labels in another queue are never
silently treated as approvals here. Start its save-enabled local review page:

```bash
./start_review_viewer.sh .cache/goat-ai/own_removal_combined_queue_20261029.json
```

Rebuild from the three source queues with `scripts/combine_review_queues.py`,
passing `ring_guard_blind_104400_104407/own_card_review_queue.json`,
`own_card_parent_review_99900_99907/queue.json`, and
`mst_review_source_107600_107607/mst_opportunity_queue.json` under
`.cache/goat-ai/`, then `--output
.cache/goat-ai/own_removal_combined_queue_20261029.json`. The builder rejects
duplicate decisions and mismatched checkpoint hashes.

## MST use and non-use review queue (29 October 2026)

The [local opportunity queue](../.cache/goat-ai/mst_review_source_107600_107607/mst_opportunity_queue.html)
extends the activation-only queue below to include decisions where MST was
legal but the AI chose another action. It contains **28** native-replayed,
player-visible decisions from the same 32 source games: **20** chosen MST
activations and **eight** non-uses. The visible back-row contexts are nine
own-only (one activation, eight non-uses), 12 opposing-only activations, and
seven mixed activations. Repeated priority windows with the same turn, phase,
selected action kind, MST source, and visible back row are collapsed before
selection; at most two items come from one replay. These are review prompts,
not correctness labels or a measured action rate. The queue JSON SHA-256 is
`0304f0d42be59b4e4a6b828b15cbcad7e15ca45f931a293360f2ad82b329a285`.
All source duels, visible observations, and saved policy choices were verified
again while building the queue. The local review server loads all 28 items
with no saved choices; every item has a player-visible label view and a
separate full-information inspection view. Open the save-enabled queue with:

```bash
./start_review_viewer.sh .cache/goat-ai/mst_review_source_107600_107607/mst_opportunity_queue.json
```

Rebuild it with the command below after recording the source games. The
`--include-opportunities` flag adds the unused-MST decisions; without it,
the script reproduces the activation-only queue below.

```bash
PYTHONPATH=src:. .venv/bin/python scripts/create_mst_review_queue.py \
  .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  .cache/goat-ai/mst_review_source_107600_107607/*_seed*_seat*.json \
  --include-opportunities --limit 32 --per-replay 2 \
  --output .cache/goat-ai/mst_review_source_107600_107607/mst_opportunity_queue.json
```

## MST activation review queue (29 October 2026)

The [local MST queue](../.cache/goat-ai/mst_review_source_107600_107607/mst_review_queue.html)
contains **23** selected MST activations from **32** complete greedy v23
policy games against Tactical-v14: one own-only, 12 opposing-only, and ten
mixed visible back-row contexts. It includes both policy seats, seeds
107600–107607, and the Max Suffridge/Jonathan Labounty and Max
Suffridge/Theeresak Poonsombat deck pairs. All **21,619** source decisions
replay-verified; the builder also verified the saved policy's choices and
rendered separate player-visible and full-information viewers. The queue
contains **no recommended action or training label**. Each entry shows the
selected activation and all legal alternatives, so review the MST activation
itself before judging a later forced target. Its JSON SHA-256 is
`91f714832b8966da9d342aa6193d62e85daa58d144deabf5e694908086aed8d0`.

Open the save-enabled queue with:

```bash
./start_review_viewer.sh .cache/goat-ai/mst_review_source_107600_107607/mst_review_queue.json
```

To reproduce the queue after recording those greedy games with
`scripts/record_policy_match.py` and `--own-loss-guard --own-loss-guard-version
1`, run:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/create_mst_review_queue.py \
  .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  .cache/goat-ai/mst_review_source_107600_107607/*_seed*_seat*.json \
  --limit 24 --per-replay 2 \
  --output .cache/goat-ai/mst_review_source_107600_107607/mst_review_queue.json
```

The queue is ignored local research data; it does not add reviewed labels to
the repository or change the selected policy.

## Diverse-deck high-margin parent review (28 October 2026)

The [local queue](../.cache/goat-ai/diverse_parent_review_97000/queue.html)
offers **23** distinct v23-policy versus Tactical-v14 disagreements, selected
from **49** candidates with a raw policy-score margin of at least 1.0. It
contains 3–4 prompts from each of six complete duels, covering both policy
seats on Goat Control/Chaos Turbo (seed 97000), Warrior/Beastdown (97001),
and Phoenix Control/Flip Control (97002). All **3,295** recorded decisions
replay-verified and passed the player-visibility audit during selection.
The queue has no human labels initially; Tactical suggestions and high model
confidence are reasons to inspect a play, not evidence of a correct answer.
Its queue JSON SHA-256 is
`e9da4e91b6ae943b25d70063eef021ee450ce717665d41429c1411c7643324ee`.

Open the save-enabled queue with:

```bash
./start_review_viewer.sh .cache/goat-ai/diverse_parent_review_97000/queue.json
```

The six source replays were generated by `scripts/record_policy_match.py`
using checkpoint
`.cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt`,
`--opponent tactical`, `--native-root .cache/goat-ai`, and both
`--policy-seat 0` and `--policy-seat 1` for each named Deck pair and seed.
The queue was then built with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python \
  scripts/shortlist_policy_disagreements.py \
  .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  .cache/goat-ai/diverse_parent_review_97000/*_seat_*.json \
  --native-root .cache/goat-ai --rank-by logit --min-logit-margin 1 \
  --limit 24 --per-replay 4 --render-viewers \
  --output .cache/goat-ai/diverse_parent_review_97000/queue.json
```

## Effect-choice review queue (28 October 2026)

The scripted native Enemy Controller probe now records and replay-verifies a
complete duel for each effect mode. The control-mode trajectory selects the
second of two options; the position-mode trajectory selects the first. Both
pass the player-visibility audit. A feature-v30 alias audit of these two
trajectories measured 876 multi-action decisions, two effect-choice prompts
(one per ordinal), and zero aliased action pairs. These scripted probes test
representation coverage and are not human preference labels.

The [local option queue](../.cache/goat-ai/option_prompt_review_96200_96215/queue.html)
contains all **five** learner-seat multi-option effect decisions found in 32
policy-versus-Tactical-v14 games on Warrior/Beastdown decks, seeds 96200–96215.
All **11,563** decisions in those complete games replay-verified and passed
the visibility audit. Three queued choices are Enemy Controller and two are
Don Zaloog. Both agents selected the first mode in each case. Agreement is
not approval; each prompt still needs independent review in its visible board
state. The local save server currently reports **0 of 5 labeled**.

Open the queue with:

```bash
./start_review_viewer.sh \
  .cache/goat-ai/option_prompt_review_96200_96215/queue.json
```

The review cards name the public chain-source card and effect mode. To label
the second mode, choose **Open label view**, then **Choose a different action**
and select the other legal effect. Reviewer-only reveals remain diagnostic and
cannot be labeled. The queue JSON SHA-256 is
`e048e951ad8799a6f567ca88f2ac3c8994dc3abc4e7512d2316bc4015e71fd0e`.
Regenerate the ignored queue with `scripts/shortlist_policy_disagreements.py`
using the selected v23 checkpoint, all 32 `matchup_*.json` replays under
`.cache/goat-ai/option_train_policy_warrior_beast_96200_96215`, and
`--review-option-prompts --limit 32 --per-replay 10 --render-viewers` with
the queue path above as `--output`. This is a feedback queue, not a labeled
demonstration set or evidence that v30 improves competitive play.

## Refreshing older review queues (28 October 2026)

The player-visible pages for all 12 locally available review and recheck
queues were refreshed with the current viewer layout. Their queue JSON,
selected decisions, saved labels, and existing reviewer-only reveal files
were left unchanged. Some older reveals cannot be regenerated because their
trajectories record a different native-core fingerprint. To refresh a queue's
label views without re-deriving those hidden-card reveals, run:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/refresh_review_queue.py \
  .cache/goat-ai/PATH_TO_QUEUE/queue.json --skip-reviewer-reveal
```

Reviewer-only pages preserved this way retain their earlier visual layout;
label views use the current layout. Regenerating a reveal still requires
native assets matching its trajectory and full replay verification.

## New Jersey high-margin review queue (28 October 2026)

Review item **#22** is a conditional MST target prompt (viewer frame 75).
The policy had already chosen to chain MST at the immediately preceding
decision (frame 74, zero-based decision index 73). At that earlier decision,
`pass` was legal (action index 3); all four targets offered at frame 75 were
the acting player's own Set cards. The strategic error to label is the
activation decision, not a choice among those forced targets. Leave #22
unlabeled or bookmark it as a reminder. A least harmful target can be useful
as a separate conditional preference, but must not be treated as approval of
the MST activation. The current queue only saves choices for shortlisted
decisions, so navigating back to frame 74 in this queue cannot save `pass`.
A separate, verified one-item [upstream review](../.cache/goat-ai/new_jersey_high_margin_review_96000_96001/upstream_22.html)
offers frame 74 and preserves the original queue and its labels:

```bash
./start_review_viewer.sh \
  .cache/goat-ai/new_jersey_high_margin_review_96000_96001/upstream_22.json
```

At that earlier frame, inspect the legal actions and choose **Pass** if you
agree. This records a preference for the activation decision only; it does
not imply any of frame 75's target choices were good. To rebuild this focused
queue from the verified source replay, run:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/create_upstream_review.py \
  .cache/goat-ai/new_jersey_high_margin_review_96000_96001/queue.json 22 73 \
  --native-root .cache/goat-ai
```

The local review server now also offers **Review earlier activation** in the
queue's replay bar. It finds the nearest optional activation matching the
visible chain source, replay-verifies the duel, creates the separate upstream
queue, and opens its save-enabled page. The automatic path recovered item
#22's MST activation at decision index 73. If the reviewed prompt has no
visible chain source or matching optional activation, it reports that it
cannot identify one; use the manual command above when the earlier decision
is known. The saved source queue and its labels are left intact.

After an upstream choice is saved, both queues' labels for the same replay can
be validated and converted into **one** preference file with
`scripts/convert_multi_queue_reviews.py --case ORIGINAL_QUEUE ORIGINAL_LABEL
--case UPSTREAM_QUEUE UPSTREAM_LABEL --native-root .cache/goat-ai --output-dir
OUTPUT_DIR`. The converter rejects contradictory choices for one decision,
deduplicates matching choices, and emits a preference only where a reviewer
selected a legal action different from the replayed AI action. The original
queue's labels and the upstream queue's labels remain separate on disk.

The [local queue](../.cache/goat-ai/new_jersey_high_margin_review_96000_96001/queue.html)
uses the same eight independently sourced 2005 New Jersey duels described
below. It retains **22** distinct policy/Tactical-v14 disagreements from
**74** candidates where the selected policy's raw score gap over the Tactical
suggestion is at least 2. Selected gaps range from **2.223 to 7.971**.
Each source duel was replay-verified and visibility-audited again during
selection. A large gap means the policy strongly scores its recorded action;
Tactical's alternative is only a prompt for human review. The queue contains
no human labels. `./start_review_viewer.sh` opens this newest local queue and
saves review choices on the local server. The ignored queue JSON SHA-256 is
`cfcc6ce174b3908167c2a5e96cf22442e5d82d1fccb089f14570e92270cbdfee`.

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python \
  scripts/shortlist_policy_disagreements.py \
  .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  .cache/goat-ai/new_jersey_parent_review_96000_96001/matchup_*.json \
  --native-root .cache/goat-ai --rank-by logit --min-logit-margin 2 \
  --limit 24 --per-replay 3 --render-viewers \
  --output .cache/goat-ai/new_jersey_high_margin_review_96000_96001/queue.json
```

## Seattle and Rhymus parent-policy review queue (28 October 2026)

The [save-enabled local queue](../.cache/goat-ai/seattle_parent_review_99200_99201/queue.html)
contains **22** high-margin review prompts from eight complete selected-v23
versus Tactical-v14 duels. The pairings are the published 2005 SJC Seattle
Theeresak Poonsombat/Christian Martinez lists and Rhymus Lizo Goat Control
versus the GoatFormat Guide Dimension Fusion list. Seeds 99200–99201 cover
both policy seats for each pairing. All **4,042** decisions replay-verified and
passed the player-visibility audit. Selection considered 164 disagreements,
kept at most three per duel, and required a raw policy-to-Tactical logit gap
of at least 2. The selected gaps range from 2.2980 to 9.4486; none carries an
automated audit flag. Tactical's alternatives are review prompts, not labels.
The four source Main Decks in the two pairings are distinct compositions
absent from the selected checkpoint's recorded training history, but these
families have been used for model selection and are not an untouched strength
holdout. The ignored source manifest and queue JSON SHA-256 values are
`9f9690677e3962e52912eb8c8984b00688464c2dcb048af9e887cd4f2e355b6a`
and `5626fbaab1467ef3f8169dcac1df44454bccd3fc1c8a98a889ceec634ee4c181`.
The live queue server reported **0/22** saved choices when this queue was
created; later progress should be read from the server rather than this note.

Open or reopen its own save-enabled server with:

```bash
./start_review_viewer.sh \
  .cache/goat-ai/seattle_parent_review_99200_99201/queue.json
```

Reproduce the ignored source collection with `scripts/collect_policy_matches.py`
using the selected `fv23_current_tactical_broader_33000_33031.pt`, the two
named pairings, `--opponent tactical --seed 99200 --seeds 2 --workers 4
--max-decisions 3000`, and an empty output directory. Then run
`scripts/shortlist_policy_disagreements.py` on its eight `matchup_*.json`
replays with that checkpoint and `--rank-by logit --min-logit-margin 2
--limit 24 --per-replay 3 --render-viewers`. Do not treat selected prompts as
authorized preferences before a reviewer saves a different legal action.

## Broader-deck parent-policy review queue (28 October 2026)

The [optional local review queue](../.cache/goat-ai/broad_parent_review_97200_97201/queue.html)
offers 14 high-margin disagreements from eight complete selected-v23 versus
Tactical-v14 duels on Mary Triatafilidi Warrior/Bryan Coronel Chaos and Jae
Kim Zombie/WikiFormat Dimension Fusion. Seeds 97200–97201 cover both policy
seats for each pairing. All **2,873** decisions replay-verified and passed the
player-visibility audit. The selection compared 53 disagreements, kept at
most three per replay, and required a raw policy-to-Tactical logit gap of at
least 2; the selected gaps range from 2.0105 to 8.7505. Tactical's action is
only a review candidate, not an expert label. The source Main Decks are absent
from the selected checkpoint's training compositions, but the project has
used these families in previous evaluation, so they are not an untouched
strength holdout. The ignored manifest and queue JSON SHA-256 values are
`f5b6fd985af3066bb170d61235cb3c06e08f66b51da8fe5a884d542afb1bea6d`
and `f75390640bb75bb0719bb1449b483d6bc93e09224258edd74af425a9d5936515`.
The queue's live server progress is authoritative for any later human labels;
none is inferred from the Tactical comparison.

To open its own save-enabled server without replacing the New Jersey parent
queue's saved progress:

```bash
./start_review_viewer.sh \
  .cache/goat-ai/broad_parent_review_97200_97201/queue.json
```

Reproduce the ignored source collection with `scripts/collect_policy_matches.py`
using the selected `fv23_current_tactical_broader_33000_33031.pt`, the two
named deck pairings, `--opponent tactical --seed 97200 --seeds 2 --workers 4
--max-decisions 3000`, and a fresh output directory. Run
`scripts/shortlist_policy_disagreements.py` on its eight `matchup_*.json`
replays with the same checkpoint and `--rank-by logit --min-logit-margin 2
--limit 24 --per-replay 3 --render-viewers`.

## Selected policy on new 2005 New Jersey decks (28 October 2026)

The [local review queue](../.cache/goat-ai/new_jersey_parent_review_96000_96001/queue.html)
contains 24 prompts from eight complete selected-policy versus Tactical-v14
duels on the new Ryan Hayakawa and Theeresak Poonsombat 2005 lists. Both
deck assignments, both policy seats, and seeds 96000–96001 are represented.
As of the 28 October overlap audit, its 14 saved choices were already among
the high-margin queue's 21 choices; the remaining 10 parent-queue prompts
were unlabeled and distinct from those saved high-margin decisions. The
queue's own progress indicator remains the live source for later reviews.
All 4,365 decisions replay-verified and passed the visibility audit. The
provenance audit reproduced 2,158 selected-policy choices and 2,207 Tactical
opponent choices. Tactical won seven of the eight duels; the sample is too
small to estimate a match win rate. There were 176 policy/Tactical
disagreements, and one conservative own-only Nobleman audit flag. The queue
keeps at most three prompts per replay. None is a human label, and Tactical's
suggestions are not assumed correct. The queue JSON SHA-256 is
`89d8abbe9abe313ed8426cb2d7adaef6ffd696c59c5b60f60bbdacf0a09fcfdb`.

`./start_review_viewer.sh` opens this queue through the save-enabled local
server. For a specific queue path:

```bash
./start_review_viewer.sh \
  .cache/goat-ai/new_jersey_parent_review_96000_96001/queue.json
```

The address should start with `http://127.0.0.1`, not `file://`.
Choosing an alternative saves automatically; the queue now waits for an
in-progress save before opening another item or returning to the list. The
viewer shows **Saved on this computer** when the server confirms the choice.
If it shows **Save failed**, keep the current tab open and use **Download
labels** as a backup before reloading.

When this same queue JSON is rebuilt, the local server carries saved choices
from its most recent tagged revision only if the source replay hash and offered
decision still match. Earlier files remain in their original ignored folder.
Clearing a choice in the current revision stays cleared after the next rebuild;
untagged folders and different queue paths are not imported automatically.

For a prompt caused by an earlier mistake, such as an avoidable MST activation
followed by a forced target, select **The earlier action was the mistake** under
**Review finding** and save an explanation. This creates a replay-bound local
note without approving any current legal action. Notes live under the ignored
`_review_state/notes/` folder, remain separate from training annotations, and
carry forward only when the exact replay and decision remain in a rebuilt
queue. The queue marks these items **Noted** separately from **Labeled** and
keeps note-only items visible for further review.

For a target prompt with a visible chain source, click **Review earlier
activation** in the local server's queue bar to create and open a one-item
upstream review. It uses the same reviewer alias and never treats the note as
an action label. The server refuses an item outside its current queue.

After saving one or more **earlier action was the mistake** notes, build a
separate queue of nearby earlier activations from the same replay, turn, and
acting player:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/create_noted_upstream_queue.py \
  .cache/goat-ai/new_jersey_parent_review_96000_96001/queue.json
./start_review_viewer.sh \
  .cache/goat-ai/new_jersey_parent_review_96000_96001/noted_upstream.json
```

The script verifies each source replay against the native engine and checks
visibility before offering up to three earlier optional activations per note.
Its suggested pass is only a candidate; choose the best legal action in the
new queue after inspecting the earlier state. Source labels and notes remain
unchanged. If no such activation exists in the same turn, the script reports
that it could not connect the note rather than inventing a label. Rebuilding
with different notes requires a new output filename to preserve old reviews.

Record the eight `matchup_*.json` duels from the repository root with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python - <<'PY'
import subprocess
import sys
from pathlib import Path

folder = Path('.cache/goat-ai/new_jersey_parent_review_96000_96001')
folder.mkdir(parents=True, exist_ok=True)
decks = (
    'examples/decks/goat_control_ryan_hayakawa_new_jersey_2005.ydk',
    'examples/decks/goat_control_theeresak_poonsombat_new_jersey_2005.ydk',
)
for assignment, pair in enumerate((decks, decks[::-1])):
    for seed in (96000, 96001):
        for seat in (0, 1):
            subprocess.run([
                sys.executable, 'scripts/record_policy_match.py',
                '.cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt',
                '--deck1', pair[0], '--deck2', pair[1],
                '--opponent', 'tactical', '--seed', str(seed),
                '--policy-seat', str(seat), '--native-root', '.cache/goat-ai',
                '--output', str(folder / f'matchup_{assignment}_seed_{seed}_seat_{seat}.json'),
            ], check=True)
PY
```

Rebuild the audit and shortlist with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/audit_policy_replays.py \
  .cache/goat-ai/new_jersey_parent_review_96000_96001/matchup_*.json \
  --checkpoint .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  --native-root .cache/goat-ai --include-opponent \
  --output .cache/goat-ai/new_jersey_parent_review_96000_96001/audit.json

OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/shortlist_policy_disagreements.py \
  .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  .cache/goat-ai/new_jersey_parent_review_96000_96001/matchup_*.json \
  --native-root .cache/goat-ai --limit 24 --per-replay 3 --render-viewers \
  --output .cache/goat-ai/new_jersey_parent_review_96000_96001/queue.json
```

## Child-versus-parent replay diagnostic (28 October 2026)

The held-out Beastdown versus Dimension Fusion result in
[the evaluation log](evaluation.md#stronger-local-review-preference-fit-on-a-new-beastdown-holdout-28-october-2026)
can now be inspected as a complete child-versus-parent duel. The recorder
accepts `--opponent-checkpoint` and fingerprints both policies. The audit
replays the native duel, checks player-visible observations, and reproduces
both policies' greedy choices against the recorded legal actions. For example:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/record_policy_match.py \
  .cache/goat-ai/human11_pref_200step_kl05_seed174.pt \
  --deck1 examples/decks/dimension_fusion_turbo_wikiformat_reference.ydk \
  --deck2 examples/decks/beastdown_ramon_ciriano_new_jersey_2005.ydk \
  --opponent-checkpoint .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  --seed 94000 --policy-seat 0 --native-root .cache/goat-ai \
  --output .cache/goat-ai/human11_pref200_diagnostic/child_vs_parent_seed94000.json

OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/audit_policy_replays.py \
  .cache/goat-ai/human11_pref200_diagnostic/child_vs_parent_seed94000.json \
  --checkpoint .cache/goat-ai/human11_pref_200step_kl05_seed174.pt \
  --opponent-checkpoint .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  --native-root .cache/goat-ai --include-opponent \
  --output .cache/goat-ai/human11_pref200_diagnostic/audit.json
```

The seed-94000 replay has SHA-256
`bdcd706c8f8ff767e1bfe0e939a35390f968179117f6229831fde6550dc3a6af`.
A fresh recording produced the same bytes. It contains 304 verified decisions:
149 child choices and 155 parent choices. The child lost. At viewer frames 24
and 37, the child ended Thunder Dragon's search with zero cards despite a
legal `select_card` action for a Thunder Dragon in its deck. The native engine
uses a staged `select_card` prompt here; the earlier review audit only checked
complete `select_cards` alternatives, so it missed both choices. The audit
now flags both and the preference derivation points to the legal deck-card
selection. These are player-visible review prompts, not proof that one
isolated choice caused the duel loss or that the child checkpoint is stronger.

The comparison queue for seeds 94000–94001 uses the parent checkpoint as a
second policy suggestion instead of Tactical. Both complete duels and all 562
decisions replay-verify; the queue also reproduces 280 child and 282 parent
greedy choices. It contains ten selected prompts from twelve candidates,
including the shared empty-search mistake at frame 24 of seed 94000. Its
suggestions are not human labels or optimal-action claims. Open it with:

```bash
./start_review_viewer.sh \
  .cache/goat-ai/human11_pref200_diagnostic/parent_comparison_queue.json
```

Rebuild the ignored queue and viewer files with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/shortlist_policy_disagreements.py \
  .cache/goat-ai/human11_pref_200step_kl05_seed174.pt \
  .cache/goat-ai/human11_pref200_diagnostic/child_vs_parent_seed94000.json \
  .cache/goat-ai/human11_pref200_diagnostic/child_vs_parent_seed94001.json \
  --comparison-checkpoint .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  --native-root .cache/goat-ai --limit 20 --per-replay 10 --render-viewers \
  --output .cache/goat-ai/human11_pref200_diagnostic/parent_comparison_queue.json
```

## High-margin policy disagreements for human review (28 October 2026)

The [local high-margin queue](../.cache/goat-ai/high_margin_review_90500_90501/queue.html)
contains **22** distinct decisions from eight previously recorded, replay-
verified and visibility-audited parent-policy/Tactical-v14 duels on seeds
90500–90501. The duels contain **3,819** verified decisions. The selector
reproduced each recorded greedy policy choice, then retained disagreements
where the raw model logit for its chosen action exceeded Tactical's suggested
legal action by at least **2**. There were 121 qualifying candidates before
prompt deduplication and the three-per-replay cap; all 22 selected items are
disagreements, and two also have visible-state audit flags. Selected raw gaps
range from **2.029** to **8.853**. Large gaps indicate a strong *model score*
preference on these states, not calibrated confidence or proof that Tactical
is correct. None of these prompts is a human label, and these replays have
already been used for diagnostics, so use new seeds and deck families for
any later competitive evaluation of a policy trained on their reviews.

`./start_review_viewer.sh` opens this newest queue through the save-enabled
local server. The current queue JSON SHA-256 is
`a8d835639b6ea59a097760fe40bcdaab2de716c01cd3b46280ede46a473e4197`.
Rebuild it with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/shortlist_policy_disagreements.py \
  .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  .cache/goat-ai/public_age_policy_90500_90501/matchup_*.json \
  --rank-by logit --min-logit-margin 2 \
  --limit 24 --per-replay 3 --render-viewers \
  --output .cache/goat-ai/high_margin_review_90500_90501/queue.json
```

The older Swords-age queue remains available by passing its `queue.json`
path to `./start_review_viewer.sh`.

## Swords public-age timing review (28 October 2026)

The [local Swords queue](../.cache/goat-ai/swords_age_review_90500_90501/queue.html)
selects **12 decisions** from four replay-verified policy duels where Swords
of Revealing Light had been face-up for one to four public turn boundaries.
The eight source duels contain 3,819 verified, visibility-audited decisions;
92 policy-seat choices met the public-age filter, and the queue caps each
replay at three prompts. The Tactical-v14 baseline disagreed on eight of the
selected choices; four are included despite agreement so timing can be
reviewed independently. The card hover shows its public age. These are
review prompts, not human labels or proven superior plays. No choices from
this queue have been used for training.

`./start_review_viewer.sh` now opens this newest queue. The queue JSON SHA-256
is `53711eb3e4a6d43287ee88e4f82869196d80f39c50d4fb1cf439da90f66d13e0`.
Rebuild it from the ignored source replays with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/shortlist_policy_disagreements.py \
  .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  .cache/goat-ai/public_age_policy_90500_90501/matchup_*.json \
  --visible-faceup-card 72302403 --min-faceup-turns 1 \
  --limit 16 --per-replay 3 --render-viewers \
  --output .cache/goat-ai/swords_age_review_90500_90501/queue.json
```

## On-policy tournament-card review queue (28 October 2026)

The [local queue](../.cache/goat-ai/on_policy_mix_review_65000_65001/queue.html)
selects **24 distinct prompts** from eight of the new tournament-card-mix
policy-versus-Tactical duels. The source trajectories contain **3,566**
replay-verified, visibility-audited decisions. The queue builder reproduced
every greedy choice of the unchanged feature-v23 checkpoint and found 166
candidate disagreements or visible-state flags. Four selected prompts carry
conservative audit flags: own-set-monster Nobleman, Heavy Storm against only
friendly backrow, a weak Flip monster Normal Summon with a Set available, and
Pot of Greed before an available Thunder Dragon. These are review prompts,
not proven optimal alternatives or human labels. No choices from this queue
have been used for training.

Run `./start_review_viewer.sh` to open the newest queue through the local
save-enabled server. To return to the earlier ambiguous-choice recheck, run
`./start_review_viewer.sh .cache/goat-ai/ambiguous_review_recheck/recheck.json`.
The new queue JSON SHA-256 is
`7ea372cef3b71f08636d68e7b1cb4a7c8b8e25bb5387f64b7e7933f8eb0073d5`.
Rebuild it from the ignored source replays and selected parent checkpoint with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/shortlist_policy_disagreements.py \
  .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  .cache/goat-ai/on_policy_mix_11030_11069_65000_65001/matchup_0[0-3]_seed_6500[01]_seat_0.json \
  --native-root .cache/goat-ai --limit 24 --per-replay 3 --render-viewers \
  --output .cache/goat-ai/on_policy_mix_review_65000_65001/queue.json
```

## Current 2005-deck development queue (27 October 2026)

The [new local queue](../.cache/goat-ai/current_2005_development_review_49600_49601/queue.html)
targets Phoenix Control/Charlotte Zombie and Rhymus Goat Control/Charlotte
Zombie, the independent 2005 deck pairings in the
[latest strength diagnostic](evaluation.md#current-core-policy-on-independent-2005-decks-27-october-2026).
Eight fresh, complete policy-versus-Tactical duels on development seeds
49600–49601 yielded 3,565 native replay-verified and visibility-audited
decisions. The queue selects 24 of 122 candidates, 12 from each policy seat
and three per duel. Own-only Nobleman and negative Heavy Storm are flagged
once each; one of those flagged plays was also chosen by Tactical. Every
other card is a disagreement prompt. At collection time, none was a human label.

On 28 October 2026, the local reviewer saved 24 choices across the eight
replays: 11 alternatives to the recorded policy play and 13 approvals of it.
All 24 passed `validate_review_queue_labels.py`, including exact native replay,
visibility, queue membership, and legal-action checks. The replays fingerprint
the native library as SHA-256
`df1774ae5d2f23e52ec2290bcd23e20713d908404539dfffc8f34e1c853e9a00`.
That earlier binary was reproduced from the first GOAT processor patch in the
original Meson build location and copied into the ignored
`.cache/goat-ai/legacy_review_native` root for verification. The current
native source and binary were restored afterward. The validation manifest is
`.cache/goat-ai/current_2005_development_review_49600_49601/validated_local_labels.json`.
The repeatable [first-patch rebuild command](native_setup.md) subsequently
reproduced the same binary in `.cache/goat-ai/reproduced_first_patch_native`;
all eight exports and 24 choices validated again against that root.
The selected feature-v23 checkpoint's top action agrees with 13 of the 24
saved choices. None of the eight exact replays or their seeds appears in that
checkpoint's recorded training provenance. These 24 labels are feedback on
individual choices, not a competitive-strength estimate. A local exploratory
checkpoint has since been trained on them; it was not promoted after held-out
evaluation. See [the evaluation log](evaluation.md#local-human-review-label-update-28-october-2026).
Only the 11 changed choices were also converted into pairwise preferences
against the AI's recorded action. That separate update likewise failed to
show a held-out gain; see the
[preference check](evaluation.md#pairwise-preference-check-on-changed-choices).

For automatic saving, run from the repository root:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/serve_review_queue.py \
  .cache/goat-ai/current_2005_development_review_49600_49601/queue.json
```

The server prints the localhost URL and the ignored folder receiving choices.
Use that URL for automatic saving. Opening the HTML directly as a `file://`
page cannot write labels; keep that tab open until you have exported any
unsaved choice or re-entered it through the server. Only decisions listed in
the active queue can be saved through its server, even though the full duel
remains navigable in the viewer.
The queue now shows **N of M review items labeled** above the cards. A saved
choice hides that item from the queue grid by default; **Show labeled items**
reveals it again with a **✓ Labeled** marker so you can revisit or change it.
Items are never deleted, and the replay stays open after you label it. The
queue updates after the local save completes and when you return to the queue.
The queue's Previous/Next buttons skip already labeled items while the
unlabeled filter is active.
The progress endpoint now verifies each source replay once per refresh while
still checking its hash, queue membership, saved action legality, reviewer
alias, and note structure. On the local 24-item New Jersey parent queue with
eight source replays and 14 saved choices, three warm requests to the older
running server took 3.669, 3.615, and 3.613 seconds; three requests to a
new server running the revised code took 1.931, 1.949, and 1.957 seconds.
These are local wall-clock
measurements, not a general throughput claim. The launcher checks the server
API version and starts a current process when an older one is still running;
save any choice in an older tab before switching to the new URL.
Bookmarks remain separate reminders and do not count as labels. Progress is
specific to the queue's source replays and saved labels; a newly generated
queue starts with its own count. If an older server is still running, launch
`./start_review_viewer.sh` again to open the updated server and queue page.
Use **☆ Bookmark** in the queue or replay bar to mark an item for follow-up;
it saves locally in `_review_state/bookmarks.json` and never becomes a
training label. Open **Open label view** and choose a legal action in the
sidebar only when you want to record the play you would make. The recorded
action has an **AI played** marker; clicking its row does not save a label.
The saved-choice line says whether your choice matches it.
**Approve AI-played action** explicitly labels the
recorded action. No reviewer name or file download is needed with the local
server; the default `local-reviewer` alias is provenance for the validator.
The **Choose a different action** button beside the recorded play opens the
legal list and focuses **Find an action**. Type a card or action name to filter
the list, then click the action you would play. **Show more** reveals additional
matches when needed. The saved-choice line shows the selected action and whether
it differs from the AI's play.
The
reviewer-only reveal is for diagnosis and cannot be labeled. Do not use this
queue's choices in training without validating them, and do not evaluate a
trained child on these three Main Deck compositions after using their labels.
The collection manifest SHA-256 is
`4da1601e45980b420b7dbcb914ebecb8a5a91312bf6181dbdbd77d09122eacba`;
the queue JSON SHA-256 is
`3abe11ebfb605c47c52630f3634bb79ce16d2b181124fc49ab60a2b205b434f5`.

Twelve earlier local choices in the fixed-policy full queue validated against
their source replays, but all twelve stored the recorded AI action. The
reviewer recalls choosing alternatives for some of them. The files are kept
locally and **excluded from training** pending re-review of the affected
frames; their present bytes do not establish the intended alternatives.
A temporary Chromium check on queue item #1 selected a different legal action
and the local server saved that different index (0 versus the recorded 1).
This confirms the current viewer/server path for that frame; it does not
explain how the earlier twelve selections became recorded-action labels.

Those twelve frames now have a [separate local recheck queue](../.cache/goat-ai/ambiguous_review_recheck/recheck.html).
Open it with:

```bash
./start_review_viewer.sh .cache/goat-ai/ambiguous_review_recheck/recheck.json
```

The old 11 label files select the frames only. The recheck queue has no
preselected actions and saves new choices under its own queue hash. Use
**Approve AI-played action** if the recorded play was your intended choice;
otherwise choose the legal alternative you intended. **Reveal all cards** is
available for diagnosis, but action labels belong in **Open label view**.
The ignored recheck queue can be rebuilt from the exact old replay bytes and
labels with `scripts/create_review_recheck_queue.py`. Its source replays,
queue metadata, and old legal choices are validated before it is written.
Neither old nor new selections enter training automatically.

## Book of Moon under Torrential Tribute (27 October 2026)

The player-visible audit now flags a Book of Moon target choice made while
Torrential Tribute is already on the chain. It requires the public Book and
Torrential links and a target still visible in a Monster Zone. This is a
review prompt, never an automatic correction: another chain link or effect
may create a reason to use Book. The [paired native fixture](goat_rules.md)
confirms that Book chained directly to Torrential does not save the targeted
monster in the tested Summon response.

The new prompt finds the user's older Tactical-v12 self-play example at
`replays/tactical_v12_self_6803/seed_6803_seat_0.json`, frame 165, where the
other Tactical seat targets its opponent's Dekoichi with Book after its own
Torrential. That old replay was read for retrospective triage and was not
replay-verified against current assets. A fresh audit of 16 previously saved
current-core policy-versus-Tactical games on seeds 44000–44003 verified all
7,830 decisions, reproduced the policy seat's choices, passed the visibility
audit, and found **zero** instances of this category. Its ignored report is
`.cache/goat-ai/fixed_policy_value_44000_44015/book_torrential_review_audit_44000_44003.json`
(SHA-256 `34b56a9f57c8943a654754c7b920b2917f1c84755d94e4816b26b74b14fbbd70`).
This absence is specific to those 16 duels.

## Breaker targeting only friendly backrow (27 October 2026)

The visible-state audit now prompts review when Breaker the Magical Warrior
selects its controller's Spell/Trap card while the opponent has no backrow.
The prompt checks the public Breaker chain link and an actual friendly field
slot, so a hidden card identity is not needed to raise it. Destroying one's
own card can sometimes be purposeful; this is a review prompt, not a
correct-play label.

Scanning the 16 stored Tactical-v8 through v14 seed-6803 trajectories finds
two examples: v8 seat-0 frame 104 targets its own Set Heavy Storm, and v9
seat-0 frame 112 targets a friendly Spell/Trap slot. These older trajectories
were not native replay-verified against the current pinned assets in this
scan. The same scanner found **zero** such prompts among 31,729 decisions in
the 64-duel current-core fixed-policy corpus, which had separately passed
native replay verification and visibility auditing. This is an absence in
that particular corpus, not evidence that the policy never makes the play.

## Resolving one-shot Spell/Trap removal prompt (27 October 2026)

The player-visible audit now flags Mystical Space Typhoon or Raigeki Break
targeting an already activated Normal Spell, Quick-Play Spell, or Normal Trap
on the public chain. These removal effects destroy their target; they do not
negate an activated one-shot effect. This follows the [period MST explanation](https://www.pojo.com/yu-gi-oh/CCGTips/2004/Sept2004/Yugi-17/Pojo%20Tip%20-%20Yu-Gi-Oh%20etiquette.htm)
and the [GOAT ruling distinction for Continuous and Normal Spell cards](https://www.goatformat.com/rulings7.html).
The prompt requires a matching face-up field slot and public chain link, and
uses the pinned card database's printed Type. It excludes Continuous cards
and the lingering Normal Spells Swords of Revealing Light and Different
Dimension Capsule. It remains a review prompt, since the play could have
another purpose and the audit does not simulate the alternative.

In the older Tactical-v13 seed-6803 seat-0 trajectory, the opponent seat's
frame 86 is the reported Raigeki Break target on an activated Metamorphosis;
the new detector identifies it. That old trajectory's native asset hashes
no longer match the current pinned core, so it is **retrospective context,
not a current replay-verified result**. On the current-core fixed-policy
64-duel corpus, all 31,729 decisions were independently replay-verified and
visibility-audited again, and the new category occurred **zero** times. The
56 previously recorded review prompts and their audit SHA-256 remained
unchanged. Six positive unit cases cover MST/Raigeki Break against Pot, Book,
and Torrential; negative cases cover Continuous Decree, lingering Swords,
and a card absent from the pending chain.

## Full fixed-policy review audit (27 October 2026)

The unchanged current-core feature-v23 checkpoint was audited on all 64
fixed-policy Tactical-v14 duels from seeds 44000–44015, covering 31,729
native-replay-verified and visibility-audited decisions. Its greedy choices
were reproduced on all 15,704 policy-seat decisions. The conservative
visible-state audit returned 56 prompts, not 56 proven mistakes:

| Prompt | Occurrences | Distinct duels |
| --- | ---: | ---: |
| End turn with Thunder Dragon activatable while a copy may remain in Deck | 32 | 11 |
| Nobleman with only an own Set monster | 9 | 7 |
| Metamorphosis spends a weak Flip monster on an empty opposing field | 3 | 3 |
| Heavy Storm with a negative visible backrow trade | 3 | 3 |
| Pot of Greed before an available Thunder Dragon activation | 3 | 3 |
| Sakuretsu Armor while Royal Decree is face-up | 2 | 2 |
| Four other categories | 4 | 4 |

The Thunder Dragon prompts all came from the same matchup and policy seat,
so they should be reviewed as a repeated local choice rather than 32
independent deck-family failures. Two additional passes with all three copies
visibly outside the Deck were removed from this category: the [historical GOAT
ruling](https://www.goatformat.com/basics.html) still permits activation to
find zero, but passing there is not itself suspicious. The Nobleman prompts
span both matchups and
both seats. The [full-corpus review queue](../replays/review_fixed_policy_44000_full/queue.html)
links 32 varied frames from 22 complete duel viewers, including eight
distinct flagged categories. It is an ignored local review artifact; no
suggestion is a training label until a person authorizes and validates it.

The queue index groups flagged decisions and other model/Tactical comparisons
into searchable cards. A flagged card can show **Both agents played** when the
policy and Tactical agent made the same choice; the flag still asks for human
review, but it is not a model/Tactical disagreement. Open `queue.html` and
choose **Open label view** to see
the acting player's visible state at that decision. The bar above the duel has
**Previous item**, **Next item**, **Reveal all cards**, and **← Queue**. The
replay's own Previous/Next controls move between decisions *within that duel*.
The reveal view shows both hands but disables labeling because hidden-card
knowledge must not enter a player-visible training label. Use **Open in new
tab** if you want a separate full-size duel page. Older local queues under
`.cache/goat-ai` were refreshed with the current viewer layout; their original
queues did not include reviewer reveals.
Clicking a Deck in **Reveal all cards** now lists the cards still in that Deck
at the current decision, top card first, with position numbers. This order is
read from a verified native replay into the separate reviewer artifact. The
label view continues to show the starting Main Deck composition and the
current remaining count, since an acting player cannot know the draw order.
When two queue items refer to the same duel, the replay board now follows the
new `#decision` fragment after a saved label; the browser no longer leaves the
previous frame displayed. Reload an already open queue tab to get these viewer
changes. The current New Jersey and broader-deck local queue viewers were
regenerated without changing queue JSON or saved labels.
Generated queue viewers now find the shared ignored `replays/card_images/`
cache two directory levels above them. The 22 full-queue label views and 22
reviewer views were regenerated locally with 96 cached card image files;
art and reviewer sidecars remain outside Git.

For reviews that save as you go, start the local server from the repository
root:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/serve_review_queue.py \
  replays/review_fixed_policy_44000_full/queue.json
```

Open the `http://127.0.0.1:8765/.../queue.html` address printed by the
command. Choose a legal action in **Open label view**; the sidebar confirms
**Saved on this computer**. Choices are restored when the page is reopened,
and **Clear frame label** removes one. The server prints the ignored
`.cache/goat-ai/review_labels/...` folder where it saves standard label JSON
files. No name, signature, download, or file move is needed. The saved
`local-reviewer` value is a provenance alias, not identity verification; use
`--reviewer-alias` and a separate `--output-dir` if multiple people review the
same queue. The server binds to localhost. Stop it with Ctrl+C.

Before using those choices for training, run
`scripts/validate_review_queue_labels.py` on the saved JSON files. That
command performs the full native replay and visibility checks; saving in the
browser alone does not establish that a selected move is optimal. Opening
`queue.html` directly as a file still offers the older manual download path.

To refresh a saved queue after viewer changes, run
`PYTHONPATH=src:. .venv/bin/python scripts/refresh_review_queue.py
path/to/queue.json`. Use `--index-only` when its duel pages already use the
current layout. The script checks the recorded trajectory hashes before
rewriting local viewer pages and leaves queue selections unchanged.

The ignored audit JSON SHA-256 is
`3f5a9f6104d5bd9ecd73a1ee9fe8f301da78c71a010430edfa964849db235163`;
the full-corpus queue JSON SHA-256 is
`1b0045756863fa62dd1c5b391dda0b5f54caabb2975dfdbcff831736a9d485ca`.
Reproduce after [native setup](native_setup.md):

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/audit_policy_replays.py \
  .cache/goat-ai/fixed_policy_value_44000_44015/matchup_*.json \
  --checkpoint .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  --output .cache/goat-ai/fixed_policy_value_44000_44015/review_audit.json
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python \
  scripts/shortlist_policy_disagreements.py \
  .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  .cache/goat-ai/fixed_policy_value_44000_44015/matchup_*.json \
  --limit 32 --per-replay 2 --render-viewers \
  --output replays/review_fixed_policy_44000_full/queue.json
```

## Fixed-policy resource and timing review (27 October 2026)

The unchanged current-core feature-v23 checkpoint played Tactical-v14 on
Jesse Goat Control versus Warrior and Roberto Martinez Phoenix Control versus
WikiFormat Dimension Fusion, with both policy seats on seeds 44000–44003.
These 16 games are the review subset of a separately recorded 64-duel
fixed-policy corpus. Collection and shortlisting independently native-replayed
and visibility-audited all **7,830 decisions** in this subset; the shortlister
also reproduced every policy-seat choice from the saved checkpoint. The
[offline review index](../replays/review_fixed_policy_44000/queue.html) selects
**20 frames** from 409 candidates and links to 11 complete duel viewers.
All linked viewer files exist. None of these prompts has been used as a
training label.

Four selected decisions have conservative visible-state flags: passing an
activatable Thunder Dragon at End Phase, activating Nobleman of Crossout with
only a friendly Set monster available, moving an unobstructed attacker to
weaker Defense Position, and activating Heavy Storm with a negative visible
backrow trade. The last case is especially useful for review: Tactical-v14
also suggests Heavy Storm there. A baseline disagreement is neither required
for a flag nor evidence that an alternative is correct. Open the linked frame,
inspect the legal actions, and apply your own judgment before authorizing a
label. If these games enter training, reserve different Main Decks for the
child's future unseen-deck evaluation.

The ignored 64-game collection manifest SHA-256 is
`93c2f2f5f768b912b76d9033408f833a1eef972a6d1371021f6a3287b72fffa6`;
the 16-game review queue JSON SHA-256 is
`ec46f84606f9cfb2a158ee849e51e836929462979b74cf835cad6784903db3c5`.
The review index is an ignored local artifact. Reproduce the queue after the
[fixed-policy collection](evaluation.md#fixed-policy-visible-state-critic-check-27-october-2026)
with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python \
  scripts/shortlist_policy_disagreements.py \
  .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  .cache/goat-ai/fixed_policy_value_44000_44015/matchup_*_seed_4400[0-3]_seat_*.json \
  --limit 20 --per-replay 2 --render-viewers \
  --output replays/review_fixed_policy_44000/queue.json
```

## Current-core Jesse versus Warrior review (27 October 2026)

The current-core feature-v23 Tactical-imitation checkpoint played Jesse
Goat Control against Tactical-v14 on Warrior, seed 43100, with the neural
policy in each seat. Both duels reached terminal and the collector plus
shortlister independently replay-verified and visibility-audited all **963
decisions**. The policy won from seat 0 after 560 decisions and lost from
seat 1 after 403. The replay [for seat 0](../replays/review_current_ai_43100/matchup_00_seed_43100_seat_0.html)
has reviewer-only hidden-card reveals for inspection; those reveals are not
part of the agent's observations.

The [review index](../replays/review_current_ai_43100/queue.html) selected 14
varied policy/Tactical disagreements from 26 candidates, at most eight per
replay. No selected decision triggered a conservative visible-state audit
flag. The Tactical alternatives are prompts for expert review, not verified
better actions or training labels. The ignored collection manifest SHA-256 is
`7ea1467e60186717636cc7cdd997704c0811247fe61609be362724f260bfef45`;
the review queue SHA-256 is
`c7505bd10d6189027d7795e35d58f3260fc0ed73063bf2c1f8955c99dbf37cdf`.
Using labels from these games for training would remove their Main Decks
from future unseen-deck evaluations of that child.

## Charlotte Zombie holdout review (27 October 2026)

The current-core feature-v23 imitation child played Tactical-v14 on Jae Kim's
2005 Charlotte Zombie Main Deck versus 2005 Phoenix Control, with both deck
assignments and policy seats on seed 36200. The collector recorded **four
terminal duels and 1,371 decisions**; both collection and shortlisting
independently native-replayed the trajectories and audited player visibility.
The saved checkpoint's greedy actions reproduced at each policy decision.

The [local review queue](../.cache/goat-ai/current_clone_zombie_review_36200/queue.html)
selected **15 frames** from 60 candidates. At decision 6 in
`matchup_00_seed_36200_seat_0.json`, the policy activates Nobleman of
Crossout while only its own Set monster is available. At decision 17 in the
same duel, it activates Heavy Storm with other own backrow and no opposing
backrow. The optional Tactical baseline avoids both activations. The source
positions support the user's earlier resource-loss reports, but Tactical's
other suggestions are review candidates rather than expert labels.

A later 32-duel Tactical imitation continuation on different Main Decks
still chose **both flagged activations** when rescored on these exact visible
positions. Neither Charlotte duel nor any queue frame trained that child;
Charlotte remains a holdout. The collection manifest SHA-256 is
`270972b9da9feee13397ce3cbdbd8aa608e86b09f4319dc38ea07ab9291b80c7`;
the queue JSON SHA-256 is
`f2b1fa9fb72d9a677834202a6b39ffcfbd2ca00fdf26febd3b37801dafb311a8`.
See [evaluation](evaluation.md#additional-tactical-imitation-and-cross-family-holdout-27-october-2026)
for the outcome check. Labeling frames from this queue would move Charlotte
out of future unseen-deck evaluations.

## Current-core imitation review queue (27 October 2026)

The fresh current-core feature-v23 Tactical imitation child played
Tactical-v14 on Phoenix Control versus each of the WikiFormat and GoatFormat
Dimension Fusion Main Decks. All three Main Deck compositions are absent
from the child's training provenance. Seeds 35000–35001 with both policy seats
produced **eight terminal duels and 5,332 decisions**. The collector and
shortlister independently native-replayed the games and audited player
visibility. The saved checkpoint's greedy actions reproduced at each frame.

The [local review queue](../.cache/goat-ai/current_clone_review_35000_35001/queue.html)
has **24 linked frames** from 247 candidates, exactly three per replay, 12
per matchup, and 12 per policy seat. Every viewer link exists. All 24 are
policy/Tactical disagreements. Three also have conservative visible-state
flags: ending a turn with an activatable Thunder Dragon, Normal Summoning a
weak Flip monster when Set is legal, and using Ring of Destruction on an own
monster while a safe opposing target is offered. These flags are review
prompts, not proofs of the best play. Tactical suggestions are not human
labels; no frame in this queue has been used for training.

The ignored collection manifest SHA-256 is
`e61cc5e3364cc27ff4820e08a540c7168c1236d7087c28ea1aadb4397785944e`;
the queue JSON SHA-256 is
`9143599e18d879ae2836f628063d3544f82eb6faf06f0120cc18f987b4ded199`.
To label a frame, open its linked replay in player-visible mode, choose a
legal action, enter a reviewer name, authorize research use, and download
the label file. Validate downloaded labels with
`scripts/validate_review_queue_labels.py` against this queue before fitting.
If labels from these Phoenix or Dimension Fusion games are used for training,
those Main Decks must be excluded from future held-out strength evaluations.

Reproduce after [native setup](native_setup.md) with a new output directory:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/collect_policy_matches.py \
  .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  --matchup examples/decks/phoenix_control_roberto_martinez_new_jersey_2005.ydk \
            examples/decks/dimension_fusion_turbo_wikiformat_reference.ydk \
  --matchup examples/decks/phoenix_control_roberto_martinez_new_jersey_2005.ydk \
            examples/decks/dimension_fusion_turbo_goatformat_guide.ydk \
  --opponent tactical --seed 35000 --seeds 2 --workers 4 \
  --max-decisions 3000 --output-dir .cache/goat-ai/current_clone_review_reproduction
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python \
  scripts/shortlist_policy_disagreements.py \
  .cache/goat-ai/fv23_current_tactical_broader_33000_33031.pt \
  .cache/goat-ai/current_clone_review_reproduction/matchup_*.json \
  --limit 24 --per-replay 3 --render-viewers \
  --output .cache/goat-ai/current_clone_review_reproduction/queue.json
```

## Broader-clone unseen-deck review queue (27 October 2026)

The feature-v23 broader Tactical imitation checkpoint played Tactical-v14 on
Roberto Martinez Phoenix Control versus each of the WikiFormat and GoatFormat
Dimension Fusion Main Decks. All three exact Main Deck compositions are absent
from that checkpoint's training provenance. Seeds 27002–27003 with both policy
seats produced **eight terminal duels and 4,728 decisions**. The collection
and shortlister each native-replayed the games and audited player visibility.
The saved checkpoint's greedy actions reproduced on the visible decisions.

The reviewer queue selected **24 frames** from 241 candidates, with three or
fewer per replay, 12 per matchup, and 12 per policy seat. It contains **23
policy/Tactical disagreements** and four conservative audit flags: ending a
turn with an activatable Thunder Dragon, activating Nobleman with only an own
Set monster visible, Normal Summoning a weak Flip monster when Set is legal,
and a negative visible Heavy Storm trade. Tactical made the same Heavy Storm
choice in that last flagged frame. Thus neither the audit flag nor Tactical's
choice is an expert label. No queue item has been used for training.

Open the ignored local [review index](../.cache/goat-ai/broader_unseen_review_27002_27003/queue.html)
to inspect the 24 exact viewer frames. All index links resolve to locally
rendered replay HTML with a decision anchor. The collection manifest SHA-256
is `5c07bb7b0fde7620d918c742bdb43549968173312aeff4e127f18037b821fa1a`;
the queue JSON SHA-256 is
`d4772e1e5256df15810c63fb390fba4eb7043c6f874fc7140009ca4a4e68eb8f`.
The output is a development review set, not a held-out strength result.
Any reviewed labels trained from these decks require separate evaluation
decks and seeds.

Reproduce after [native setup](native_setup.md) with a new output directory:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/collect_policy_matches.py \
  .cache/goat-ai/fv23_tactical_v14_broader_18500_18531.pt \
  --matchup examples/decks/phoenix_control_roberto_martinez_new_jersey_2005.ydk \
            examples/decks/dimension_fusion_turbo_wikiformat_reference.ydk \
  --matchup examples/decks/phoenix_control_roberto_martinez_new_jersey_2005.ydk \
            examples/decks/dimension_fusion_turbo_goatformat_guide.ydk \
  --opponent tactical --seed 27002 --seeds 2 --workers 4 \
  --max-decisions 3000 --output-dir .cache/goat-ai/broader_unseen_review_27002_27003
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python \
  scripts/shortlist_policy_disagreements.py \
  .cache/goat-ai/fv23_tactical_v14_broader_18500_18531.pt \
  .cache/goat-ai/broader_unseen_review_27002_27003/matchup_*.json \
  --limit 24 --per-replay 3 --render-viewers \
  --output .cache/goat-ai/broader_unseen_review_27002_27003/queue.json
```

An earlier exploratory eight-duel batch at seeds 27000–27001 included Daryl
Gravekeepers and Cas Flip Control, both present in the checkpoint's training
provenance. It remains local exploratory data and is excluded from this
unseen-deck queue.

The offline viewer lets a reviewer select a legal action at a linked frame,
enter a name, authorize research use, and download a JSON label file. Validate
each downloaded file before fitting a policy. Label controls are available
only in the player-visible viewer mode; reviewer-only hidden-card reveals
disable them.

```bash
PYTHONPATH=src:. .venv/bin/python scripts/validate_review_queue_labels.py \
  .cache/goat-ai/broader_unseen_review_27002_27003/queue.json \
  /path/to/downloaded_labels.json \
  --native-root .cache/goat-ai \
  --output .cache/goat-ai/broader_unseen_review_27002_27003/validated_labels.json
```

The validator checks the exact replay SHA-256, native replay, player-visible
audit, policy-seat authorization, legal action index, shortlist membership,
checkpoint identity, and each shortlisted frame's displayed action and decision
metadata against the replay. Its report records the policy checkpoint SHA-256.

When several people review the same duel, use the separate merge command to
combine their downloaded exports. It validates every input against the native
duel and original queue, accepts a decision only when all distinct reviewer
names choose the same legal action, and writes one annotation per replay for
the cloning trainer. Conflicts and decisions below the chosen reviewer count
stay in `manifest.json` without becoming training labels. Reviewer names are
self-reported; the merge does not authenticate independent people.

```bash
PYTHONPATH=src:. .venv/bin/python scripts/merge_review_queue_labels.py \
  replays/review_fixed_policy_44000_full/queue.json \
  /path/to/reviewer_one.json /path/to/reviewer_two.json \
  --native-root .cache/goat-ai --min-reviewers 2 \
  --output-dir .cache/goat-ai/merged_human_review_example
```

The output manifest records the queue and input label hashes, source replay
paths, merged annotation paths, and unresolved votes. Supply each merged
replay/annotation pair to `train_behavioral_clone.py` with its existing
`--annotation-for TRAJECTORY=LABELS` option; keep these human-reviewed labels
distinct from synthetic Tactical suggestions in checkpoint provenance.
It reports the changed-choice count and the replay/label pairs needed by
`train_behavioral_clone.py --annotation-for`. It does not infer that the
reviewer's action is strategically optimal. A synthetic recorded-action
export exercised this path on one 725-decision duel; it passed verification
and was then deleted without training.

## Four-matchup development review queue (27 October 2026)

The unchanged feature-v23 reference played Tactical-v14 across four distinct
development matchups: Jesse Goat Control/Warrior, Matt Goat Control/Chaos Turbo,
Michael Goat Control/Cas Flip Control, and Daryl Gravekeepers/Bazoo Return.
Seeds 24100–24101 with both policy seats produced **16 terminal duels** and
**11,617 native-verified decisions**. The collector audited player visibility
and bound every replay to its deck and checkpoint hashes. The shortlist then
reverified each replay, reproduced the checkpoint's greedy choices, and found
**695** policy/Tactical disagreements or conservative audit prompts.

The bounded queue selected **24** distinct prompts from **14** replays. Their
matchup counts were 4, 7, 6, and 7; ten selected prompts carried a visible
audit flag, including own-only Nobleman, an empty Thunder Dragon search, BLS
targeting itself, and missed opponent-End-Phase Scapegoat timing. All 24
linked offline viewer frames exist. Tactical's suggested action is a review
candidate, not a correctness label: at one flagged weak-Flip Summon it chose
to activate Thunder Dragon first, which does not by itself answer whether to
Set the Flip monster later. No selected prompt has been used for training.

The local index is
`.cache/goat-ai/review_broad_24100_24101/queue.html`; the corresponding
JSON is `queue.json`. The collection manifest SHA-256 is
`e6494c6cb5104bbfec8d98120370a9fda35a3151f18986cb2e7c8e2ec062d602`;
the queue JSON SHA-256 is
`ac8ad61a4704f520b0ece8a761f96a81f193d98f35392c70740e0f6505177f16`.
These are ignored local artifacts. The four pairings are development review
data; using reviewed choices later would require a separate held-out deck and
seed schedule for competitive evaluation. Reproduce the collector with the
four `--matchup` pairs above, `--seed 24100 --seeds 2 --workers 4`, then run:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python \
  scripts/shortlist_policy_disagreements.py \
  .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  .cache/goat-ai/review_broad_24100_24101/matchup_*.json \
  --limit 24 --per-replay 2 --render-viewers \
  --output .cache/goat-ai/review_broad_24100_24101/queue.json
```

## Frozen-parent check of sampled self-play flags (27 October 2026)

Sixteen fresh PPO training replays from two Jesse Goat Control versus Warrior
seed groups (23600–23607 and 23610–23617) completed and replay-verified all
**8,972 decisions**. The player-visibility audit passed. Their sampled learner
choices triggered eight conservative review flags. The new
`audit_policy_replays.py --compare-parent-greedy` mode loads the exact frozen
parent checkpoint identified by each replay's SHA-256 and asks what that
checkpoint would choose greedily at each flagged **player-visible** decision.
It checks that the choice belongs to the recorded legal set. It does not
recreate the policy weights after subsequent PPO updates or simulate the
alternative game's outcome.

The parent made the same flagged choice in **five of eight** cases: two
own-only Nobleman activations, one MST target on its own card despite an
opposing option, one Heavy Storm with a negative visible backrow trade, and
one Metamorphosis material choice spending a weak Flip monster against an
empty opposing field. It selected a different, unflagged action on one
additional Nobleman prompt, one Breaker target prompt, and one 0-ATK
position-change prompt. Thus several resource flags persist under greedy
reference inference; sampled self-play alone does not explain them. The
shortlist is a diagnostic, not certified expert labels or proof that every
flagged move loses the duel.

The ignored report is
`.cache/goat-ai/card_view_parent_greedy_23600_23610.json` (SHA-256
`0f8c2042c7c46733a454a0d274eed3298aad28508e2389ba70aef6dfa112c58`).
Reproduce after native setup with the unchanged reference checkpoint:

```bash
PYTHONPATH=src:. OMP_NUM_THREADS=1 .venv/bin/python scripts/audit_policy_replays.py \
  .cache/goat-ai/card_view_cached_23600_replays/*.json \
  .cache/goat-ai/card_view_cached_23610_replays/*.json \
  --checkpoint .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --compare-parent-greedy \
  --output .cache/goat-ai/card_view_parent_greedy_23600_23610.json
```

The next feedback experiment should prioritize confirmed greedy resource
errors across independent Deck families and hold out separate seeds and
Decks for match outcomes. These five examples are too few to establish a
general training signal by themselves.

## Held-out neural losses: unused Thunder Dragon (27 October 2026)

The feature-v25 resource-trade head lost a Dimension Fusion/Phoenix duel to
Tactical v14 at seed 17008. At viewer frame **11**, it ended turn one while a
Thunder Dragon activation was legal, one copy was visible in its hand, and
its initial Main Deck contained three copies. Tactical v14 preferred the
activation at that same player-visible state. The replay reviewer now flags
this as `end_turn_with_activatable_thunder_dragon`; it is a candidate for
review, not a claim that every delayed Thunder Dragon activation is wrong.
The recorded policy never activated that copy before it left the hand.
The 482-decision source duel and all 227 policy choices verified against the
native engine and saved checkpoint. The ignored v25 audit is
`.cache/goat-ai/fv25_df_vs_phoenix_tactical_17008_audit_v2.json` (SHA-256
`3966cf9b073c4327e22a7d23c4f92a95941ccb5b343ec543317dd01e04a3df84`).

To check whether this was isolated, the unchanged feature-v23 parent played
Tactical v14 on previously unseen Dimension Fusion/Phoenix and Bazoo/Michael
Main Deck pairings, both policy seats, seeds 17110–17111. All **eight** duels
completed, all **3,495** decisions replay-verified, and visibility and greedy
choice audits passed. The policy lost all eight; this small selected schedule
is diagnostic and does not estimate its general win rate. The review shortlist
returned **nine** candidates: three separate turn endings with an activatable
Thunder Dragon, two weak Flip monsters Normal Summoned with a Set available,
and one each for Nobleman targeting only an own Set monster, Chaos Sorcerer
targeting itself with an enemy option, an empty Thunder Dragon search with
copies available, and Tribe-Infecting Virus naming a race that hit only its
own monster. These are observable choices to inspect, not automatic labels
for neural training. In particular, the current model's omission of Thunder
Dragon occurred across multiple turns of one game, while the other two
pairings did not show this exact end-turn pattern.

The ignored collection manifest is
`.cache/goat-ai/fv23_heldout_loss_audit_17110_17111/manifest.json` (SHA-256
`0c7f6c13e28adc72f9b69b0721b10354873b75349b0601ba6cfece39ad354ebd`),
and its audit is in the same directory (SHA-256
`638c46730cada910d51847f6c7643bb9a43eca52389f39bfa9eb1bec7d2d50d8`).
Reproduce the source games and audit from the repository root with:

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/collect_policy_matches.py \
  .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --matchup examples/decks/dimension_fusion_turbo_wikiformat_reference.ydk examples/decks/phoenix_control_roberto_martinez_new_jersey_2005.ydk \
  --matchup examples/decks/bazoo_return_weirdchamp_worlds.ydk examples/decks/goat_control_michael_fukuyama_indianapolis_2005.ydk \
  --seed 17110 --seeds 2 --workers 4 --opponent tactical \
  --output-dir .cache/goat-ai/fv23_heldout_loss_audit_17110_17111
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python scripts/audit_policy_replays.py \
  .cache/goat-ai/fv23_heldout_loss_audit_17110_17111/matchup_*.json \
  --checkpoint .cache/goat-ai/fv23_tactical_v14_unseen_fourdeck_continuation.pt \
  --output .cache/goat-ai/fv23_heldout_loss_audit_17110_17111/audit.json
```

Use a fresh output directory when rerunning; the collector rejects a
nonempty directory to protect the original trajectories. A useful next
policy experiment should include
verified examples from several deck families, separate development from
held-out decks and seeds, and test whether correcting these choices changes
actual match outcomes against Tactical.

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

### Position changes and public summon context (schema v25)

In the original feature-21 seed-3901, seat-0 replay, the learned policy moved a
face-up, defending, 0-ATK Sheep Token to attack at **12** decisions (viewer
frames 78, 92, 99, 227, 237, 240, 358, 365, 368, 495, 769, and 772).
This is an observed bad pattern, especially when Pass and other legal actions
are available. It is narrower than all position changes: a monster may
reasonably change position to attack, avoid destruction, or use an effect.
The review scanner now reports `zero_attack_defender_changed_to_attack` as a
candidate. TacticalHeuristicAgent v6 filters this specific Sheep Token move
when another legal choice exists. The learned policy can use the same filter
with `--position-guard`; its default greedy inference is unchanged. At the
old frame 78 state, the unguarded policy selected the token position change
while the guarded policy selected a Normal Summon.

A new seed-3901 policy-versus-Tactical-v6 duel using that flag completed and
all **721** decisions replay-verified. Its audit found **zero** position
candidates. The ignored trajectory and audit are
`replays/fv21_position_guard_3901_p0.json` and
`artifacts/fv21_position_guard_3901_audit.json`. This only establishes that
the guard prevents the identified token move; it does not establish improved
competitive play or solve repeated position changes by other monsters.

The adapter now records a native public summon announcement during its
negation response window. It also queries the original owner of face-up field
monsters. These visible facts let Tactical v6 decline Solemn Judgment on an
opponent's announced Sinister Serpent Summon when Pass is legal, and distinguish
an originally opposing Black Luster Soldier currently controlled by the agent
from its own BLS. The original seed-3900 frame 99 exposed the announced
Sinister Serpent and the updated tactical agent passed at that decision. A
new schema-v25 policy-versus-tactical duel completed and all **149** decisions
replay-verified. A legacy schema-v24 duel still replay-verified at **152**
decisions; the verifier compares only fields available in that schema.

The experimental feature-v23 policy binds `change_position` to the selected
monster's visible stats and orientation. It reduced, but did not eliminate,
the original seed-3901 Sheep Token choices: **9 of 12** remain when rescoring
those recorded states. Position changes by Magician of Faith, Gravekeeper's
Spy, and other non-token monsters still need board-context review. See the
[held-out feature-v23 experiment](evaluation.md) before treating this as a
strength improvement.

The shortlist also flags `empty_field_attacker_changed_to_weaker_defense`
when a face-up attacker moves to a lower DEF while the opponent has no
monsters. It records the visible ATK and DEF and leaves switches against any
opposing monster for human review. This mirrors the narrow position guard v2;
it is a review candidate rather than proof that every such switch loses value.

On the current pinned native assets, a fresh seed-3901 duel with the same
feature-v21 checkpoint and Tactical v7 opponent produced 658 verified
decisions without the guard and 683 with it. The audit reproduced all 339
unguarded and 345 guarded policy choices. It flagged ten defending Sheep
Token switches and one empty-field attack-to-weaker-defense switch in the
unguarded duel, versus zero of either in the guarded duel. Both were won by
seat 1. The ignored replay SHA-256 values are
`95b10f034cee7e88a34c4f2b201ba4357379e41ea30f9cc6722c36938cbe09f0`
and `47f01fe6d19c806839d1860f01bbc34697c65613b977aceba2268fa1e51e5503`,
respectively; they are local recordings under `.cache/goat-ai/`. This is a
single-seed behavior check, not a strength estimate. Earlier tracked replays
use older native asset hashes and remain tied to those assets.

Reproduce either recording with `scripts/record_policy_match.py` using
`.cache/goat-ai/fv21_casdaryl_schema24_experiment.pt`, `--seed 3901`,
`--policy-seat 0`, `--opponent tactical`, and the Main Decks
`examples/decks/goat_control_matt_peddle_indianapolis_2005.ydk` and
`examples/decks/chaos_turbo_riclar_2020.ydk` as `--deck1` and `--deck2`.
Add `--position-guard` for the guarded branch. Run
`scripts/audit_policy_replays.py` on each output with `--checkpoint` set to
that same checkpoint.

### Retrospective Sheep Token preference labels

The seed-3901 feature-v21 replay contains 12 policy-seat decisions that move
face-up, defending, 0-ATK Sheep Tokens into attack. The reviewed annotation
`examples/preferences/feature21_sheep_token_defense_3901_p0.preference.json`
is bound to the complete replay's SHA-256
`13f4b3cb41c284bbfb5d87768e5f362a529444f0f9abefc9a2b5aa3b35092e73`.
At each decision, its disfavored set contains **all** legal changes of those
0-ATK defending Sheep Tokens; its preferred set contains the other legal
choices except `shuffle_hand`. This encodes the player's stated preference
to keep the tokens defending, not a claim that every alternative is equally
strong or an expert demonstration of a specific action. The replay and
annotation pass native replay verification, the visibility audit, and the
preference schema's legal-index and policy-seat checks before training. The
source replay is an ignored local artifact; the annotation is useful only
when the exact replay hash is available or reproduced.

The source replay was regenerated byte-for-byte from project revision
`f8600c9` with the pinned feature-21 checkpoint (SHA-256
`c6cc59780d665edf2c83b143d1b371e9aa05fcfff5ac988edfc48613ccd21011`),
Matt Peddle Goat Control versus Riclar Chaos Turbo, seed 3901, policy seat 0,
TacticalHeuristicAgent v4, and the pinned native assets. The regenerated
**945-decision** trajectory SHA-256 matched the annotation's source hash.
Reproducing the annotation requires this historical project revision:
current TacticalHeuristicAgent v6 deliberately makes different choices.

## Matt versus Chaos, seed 6803: Tactical v7 review

`replays/tactical_v7_matt_vs_chaos_seed6803.json` is a complete, native
replay-verified duel. Its metadata identifies **Player 2 as Tactical v7** and
**Player 1 as Combat Heuristic v3**. The viewer's perspective labels are not
agent identities. The retrospective audit reproduced the v7 teacher choices
from the recorded player-visible states. Decision indices below are zero-based;
add one for the viewer frame.

| Decision | Agent | Observed problem | Correction status |
| ---: | --- | --- | --- |
| 6 | Tactical v7, P2 | Discarded Snatch Steal to opposing Delinquent Duo with Sinister Serpent also in hand. | v8 chooses the recoverable Serpent. |
| 42 | Combat v3, P1 | Canceled Thunder Dragon's search when two copies were offered. | v8 selects the maximum offered copies; this does not change Combat v3. |
| 118 | Combat v3, P1 | Activated BLS's banish effect with no opposing monster, then had only its own BLS as a legal target. | Tactical v9 defers that activation; the earlier target-only guard did not prevent an own-only choice. |
| 140 | Tactical v7, P2 | Normal Summoned Sinister Serpent while other Normal Summons, including D.D. Assailant, were legal. | v8 defers Serpent's Normal Summon when another monster can be Normal Summoned. |
| 167–169 | Combat v3, P1 | Activated Raigeki Break, discarded Heavy Storm, and chose its own set card while an opposing monster was a legal target. | Still needs a general removal and discard value model. |
| 310 | Tactical v7, P2 | Chained Dust Tornado to Book of Moon. The offered Pass preserved Dust Tornado without stopping Book's one-shot effect. | v8 passes in this specific chain pattern. |
| 324 | Tactical v7, P2 | Activated Nobleman of Crossout with no opposing face-down monster; the later target prompt offered only its own monster. | v8 defers activation until an opposing face-down monster is visible. |

The reviewed replay also shows Combat v3 Normal Summoning weak Flip monsters,
using Book of Moon early, and discarding with Raigeki Break. Those are
remaining baseline errors, not evidence that Tactical v7 made those choices.
Setting every Spell/Trap is a broader commitment decision: a rule that always
holds backrow could miss necessary defenses. It needs a measured policy or
value model with Heavy Storm exposure, immediate threats, and hand size as
inputs. These fixes encode local, visible card-value checks; they do not yet
teach general card advantage.

The same-seed v8-versus-v8 trajectory is
`replays/tactical_v8_matt_vs_chaos_6803/seed_6803_seat_1.json`; its offline
viewer is `replays/tactical_v8_matt_vs_chaos_seed6803.html` beside the local
card-image cache. Both seats use Tactical v8, so this is
the cleaner replay for future human review. `scripts/collect_heuristic_demos.py`
now accepts `--opponent tactical` to regenerate this pairing. The teacher
version is recorded so a v7 replay remains reproducible after these changes.

### Reviewed preferences from the player's notes

The player's notes are also encoded as seven **retrospective preferences** in
`examples/preferences/tactical_v7_seed6803_player1_baseline.preference.json`
and `tactical_v7_seed6803_player2_baseline.preference.json`. They are bound to
the complete source replay SHA-256
`1417fa6a273a5f7b19ed3b96bcda333144c825a8f125c520d786dd0f210e915f`.
The first file reviews three Combat v3 decisions: Thunder Dragon taking both
copies, passing on BLS's own-only banish, and passing on a Raigeki Break that
would spend Heavy Storm to destroy an own Set card. The second reviews four
Tactical v7 decisions: discarding Sinister Serpent to Delinquent Duo, holding
Sinister's Normal Summon for another monster or setting it, passing on Dust
Tornado chained to Book of Moon, and setting Nobleman instead of targeting its
own monster. Other legal choices are deliberately left unranked where the
notes do not determine their value.

`baseline_review` requires an explicitly recorded player seat and the
replay's teacher/opponent metadata. The reader checks the source hash, legal
indices, disjoint preference sets, selected disfavored action, and acting
seat. Scoring and training first replay-verify the full duel and audit both
players' information boundaries. These reviews are **not human gameplay
demonstrations** and do not turn a baseline's other decisions into expert
labels. Both the score report and a small opt-in parent-KL experiment are
recorded in [evaluation](evaluation.md).

## Matt versus Chaos, seed 6803: both players Tactical v8

The user's later notes refer to
`replays/tactical_v8_matt_vs_chaos_6803/seed_6803_seat_0.json` (SHA-256
`a5612f3babbae005cb2506c767d38289df8dbbbee99f7aebf48a7570ac04ad5b`),
an **879-decision, 37-turn** game. Both seats used Tactical v8. This is a
different duel from the shorter seed-6803 seat-1 replay linked earlier.
Both trajectories replay-verify. Indices below are zero-based; viewer frames
are one greater. At effect-target prompts, the mistake may be the earlier
activation rather than the later forced choice.

| Decision | Reviewed v8 choice | v9 response on the identical visible state |
| ---: | --- | --- |
| 10 | Metamorphosis Tributes Newdoria for a Level 4 vanilla Fusion with only a 300-ATK gain. | Defer activation; the printed Fusion Type, Level and ATK show no useful upgrade. A Level 1 Sheep Token with Thousand-Eyes Restrict in the Extra Deck remains eligible. |
| 34, 37 | P2 discards both searched Thunder Dragons after all three original copies are in hand/Graveyard. | Pass on both activations when the player's own initial list and known zones account for all copies. The engine still permits zero searches under the historical TCG Netrep ruling. |
| 57, 671, 724, 780 | Chaos Sorcerer selects its controller's monsters despite opposing face-up monsters being offered. | Prefer an opposing target, including Darkfire Dragon, Magician of Faith, or Thousand-Eyes Restrict. |
| 100, 102 | P1 Sets Heavy Storm, then spends Breaker's counter to destroy it. | Hold the Storm when there is no opposing backrow; decline Breaker's effect if only own backrow exists. Decision 103 is forced once the counter was spent. |
| 132 | P2 uses Book of Moon on Breaker during P2's Draw Phase. | Pass in the own Draw/Standby Phase without a pending chain. This narrow timing guard does not judge later tactical Book uses. |
| 384 | P1 gives Jinzo to Creature Swap with three Sheep Tokens also offered. | Offer a Sheep Token. |
| 477 | P1 targets Tsukuyomi itself with its flip-down effect. | Target its equipped Thousand-Eyes Restrict to free its Equip Card and reset its effect. |
| 831, 833 | P2 activates Raigeki Break in its own Draw Phase, discards Trap Dustshoot, then targets its own Set Chaos Sorcerer. | Defer that early activation; if a removal effect is already committed and an opposing target is offered, prefer the opposing target. |

The full same-seed v9-versus-v9 game is
`replays/tactical_v9_matt_vs_chaos_6803/seed_6803_seat_0.json` (445 decisions,
SHA-256 `52120c51f5fc96b2beb90aa87f4d3b5daf7b3f6c2c7b11014e06bcce3d9ee1d1`).
Open `replays/tactical_v9_matt_vs_chaos_seed6803.html` for its card-image
viewer. It replay-verified, passed the decision visibility audit, and
reproduced the v9 teacher's recorded choices. Historical v8 choices also
reproduced with v9 behavior disabled. The new duel has a different branch
and ends on turn 11, so old frame numbers do not map into it. These are
visible-state heuristics for baseline data quality; a neural policy still
needs broader training and held-out validation.

The same review also produced 14 `baseline_review` preferences, split by
acting seat in `examples/preferences/tactical_v8_seed6803_player1_baseline.preference.json`
and `tactical_v8_seed6803_player2_baseline.preference.json`. Both files bind
to the v8 replay SHA-256 above and contain only comparisons supported by the
user's notes, such as holding Thunder Dragon or offering one of three Sheep
Tokens instead of Jinzo. At target prompts with several plausible opposing
monsters, unranked alternatives remain unranked. The preference reader,
replay verifier, and visibility audit accepted all 14 before scoring. The
earlier feature-v23 Tactical-v6 clone, trained on different seeds, greedily
chose a preferred action in 6 of 14 states; eight pairwise margins were
negative. This is fixed-state evidence of learnable gaps, not match strength.

### Tactical v10 follow-up: turn 2 and turn 6

In the v9 seed-6803 seat-0 replay, P2 activated Book of Moon from hand during
its own Main Phase at decision 35 while controlling no monsters and with no
chain pending. At decision 51 it activated Chaos Sorcerer's banish effect
while the opponent had no face-up monster, making the self-target at decision
52 unavoidable. At decision 217 it spent Breaker's counter with no opposing
Spell/Trap, making its own Set Ring of Destruction the only target. The v9
activation checks incorrectly required a `pass` action, which is absent from
open Main Phase prompts. Tactical v10 handles these prompts and defers Book
from hand on its own Main Phase without an active chain, except to unlock
attacks through an opposing face-up Thousand-Eyes Restrict. It also declines
to chain Book to its own Chaos Sorcerer, BLS, or Breaker effect. Applying v10 to the
same recorded observations yields pass at 35, Set Magician of Faith at 51,
and Battle Phase at 217; the resulting duel branches differently.

P2's Breaker could not attack P1's face-up Thousand-Eyes Restrict on turn 6:
the engine offered Battle Phase but no attack action. This matches Restrict's
historical lock on attacks by all other monsters, already covered by the
[paired native regression](goat_rules.md). v10 therefore changes the bad
Breaker activation. It also removes attack-to-defense switches when ATK is
at least DEF, and defers a defense-to-attack switch against fully visible
enemy monsters unless it can win a visible battle. The policy retains legal
position actions when their value is uncertain; it is still a heuristic.

The complete same-seed v10 replay is
`replays/tactical_v10_matt_vs_chaos_6803/seed_6803_seat_0.json` (487
decisions, 13 turns). Open
`replays/tactical_v10_matt_vs_chaos_seed6803.html` for its offline viewer.
Both v10 seats and the older v9 seat-0 replay replay-verified, passed the
visibility audit, and reproduced their versioned teacher choices. The v10
seat-0 game has no selected position changes; this describes one duel, not
a general performance claim.

### Tactical v11–v12 follow-up: BLS sequencing and reactive removal

In the v10 seat-0 replay at decision 439 (turn 13), P1 had a face-up BLS,
Tsukuyomi in hand, and an opposing Set monster. The legal actions included
both BLS's banish effect and a position change for BLS, showing it was
eligible for a same-turn Tsukuyomi reset and Flip Summon. Tactical v10
incorrectly required an opposing **face-up** monster for both BLS and Chaos
Sorcerer. BLS can target the Set monster; only Chaos Sorcerer requires a
face-up target. Tactical v11 activates BLS first on this recorded visible
state, and its full seed-6803 replay then Summons Tsukuyomi, sets BLS,
Flip Summons it, and attacks. Historical BLS rulings permit another use of
its effect after a face-down/face-up reset; see [GOAT rules](goat_rules.md).
The user's turn-13 comparison is stored as a one-decision `baseline_review`
preference in
`examples/preferences/tactical_v10_seed6803_player1_bls.preference.json`,
bound to the v10 replay SHA-256. The v11 offline viewer is
`replays/tactical_v11_matt_vs_chaos_seed6803.html` (474 decisions).

That v11 replay still spent two cards without visible payoff at decisions
78 and 81 on turn 3. P2 activated its Set Book of Moon during P1's Draw
Phase with no incoming chain, targeting its own Chaos Sorcerer. P2 then
chained Raigeki Break to that Book, discarded a card, and targeted one of
P1's four 0-ATK Sheep Tokens despite an opposing Set Spell/Trap also being
offered. Tactical v12 defers an idle Book or Raigeki Break in either player's
Draw/Standby Phase and defers Raigeki Break chained to its own Book. If
Raigeki Break is already committed, its target guard prefers an opposing
non-Token card over a Sheep Token when one is offered. On the **same v11
observations**, v12 passes at 78 and 81 and selects the opposing Set card
instead of a Token at the later target prompt. The two user-reviewed
resource choices are bound to the v11 replay in
`examples/preferences/tactical_v11_seed6803_player2_resource.preference.json`.

The first v12 replay exposed a further Book of Moon use on its own Chaos
Sorcerer during P1's Main Phase, while the opposing monsters were all Sheep
Tokens and no chain link targeted a friendly monster. The v12 guard now
passes in that situation; it still allows Book against a face-up non-Token
opponent or when a chain targets a friendly monster. The full v12-versus-v12
seed-6803 seat-0 replay is
`replays/tactical_v12_self_6803/seed_6803_seat_0.json` (648 decisions),
with offline viewer `replays/tactical_v12_self_seed6803.html`. Its Book
activations target opposing monsters, and its Raigeki Break selects an
opposing non-Token monster while Sheep Tokens are available. Both complete
v12-versus-v12 trajectories replay-verified, passed visibility checks,
and reproduced their versioned teacher choices. The changed branch and
one-duel outcome are not a strength result.

### Tactical v13 review of seed 6803

In the v12-versus-v12 replay, the user identified six resource and combat
mistakes. The source trajectory is
`replays/tactical_v12_self_6803/seed_6803_seat_0.json` (SHA-256
`85eb87112fd42033ffb386bed29195d8dde639807b0d36c993afaaa07503155b`).
Its player-1 decision 5 chained Mystical Space Typhoon to that player's own
Pot of Greed. Player 2 chained a second Book of Moon to the first Book at
decision 53, used Raigeki Break on a 100-ATK Dark Mimic LV1 at 90, chained
Book after Torrential Tribute at 163, banished a Sheep Token with BLS at
419 despite no opposing backrow, and offered BLS as Tribute for Thunder Dragon
at 627. The user-reviewed alternatives are bound to this replay in
`examples/preferences/tactical_v12_seed6803_player{1,2}_resource.preference.json`.
Both source seats, all six action alternatives, the full native replay, and
the player-visible trajectory passed validation.

Tactical v13 passes on the four reviewed chains, saves BLS's attack against
the Sheep Tokens when there is no opposing backrow, and enters Battle Phase
instead of Summoning Thunder Dragon over its BLS on the fixed v12 states.
[BLS's official text](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=5835&ope=2&request_locale=en)
allows a second consecutive attack after destroying an opposing monster by
battle, while activating its banish effect prevents it from attacking that
turn. The guard is a tactical preference, not a change to legal actions.
The new `replays/tactical_v13_self_seed6803.html` shows both players using
v13. Its two underlying complete duels, 530 and 953 decisions, replay-verified,
passed visibility checks, and reproduced teacher choices. Neither replay
reached one of the six exact bad-play patterns, but the different game paths
do not prove that every Book, Raigeki, or tribute decision is sound.

### Tactical v14 review of seed 6803

In `replays/tactical_v13_self_6803/seed_6803_seat_0.json` (SHA-256
`cfdca8fede4d51d42f662b653470297d26fde5650270d7958ba74bab4e95caae`),
player 2 chained Raigeki Break to a resolving Metamorphosis at decision 83,
discarded Mystic Tomato although Thunder Dragon had zero known remaining
Deck copies at 84, and later Snatch Stole a Sheep Token rather than the
opposing Breaker at 324. The reviewed alternatives are stored in
`examples/preferences/tactical_v13_seed6803_player2_resource.preference.json`.
The full source replay, visibility boundary, and all three alternative actions
were validated before changing the teacher.

Tactical v14 passes on the unrelated Metamorphosis chain, chooses the spent
Thunder Dragon when a discard is already required, and targets Breaker with
Snatch on those same source observations. It also defers idle Raigeki Break
against a field of only Sheep Tokens and defers Snatch when only Sheep are
available unless Metamorphosis is in hand. An incoming attack or a chain
visibly targeting its own Set card can still justify a Raigeki response.
The new complete v14-versus-v14 seed-6803 seat-0 replay has 871 decisions
and can be opened at `replays/tactical_v14_self_seed6803.html`. Seat 1 has
953 decisions. Both v13 source trajectories and both new v14 trajectories
replay-verified, passed visibility checks, and reproduced their versioned
teacher actions. See [evaluation](evaluation.md) for the paired tournament;
these exact-state corrections do not establish overall playing strength.

### Spirit Reaper position review

In the repository's Tactical-v14 seed-6803 seat-0 replay, decision 520
(viewer frame 521, turn 19) Normal Summons GOAT Spirit Reaper in Attack Position
while the opponent controls a face-up 1000 ATK Sangan. Setting that same
Reaper is legal. Reaper cannot attack directly or defeat Sangan in battle.
The user reviewed this as a general preference to Set Reaper when it has no
profitable attack, while allowing rare tactical exceptions. An opt-in
`reaper_set_guard` now filters that Attack Position Summon if a Set is legal,
no direct attack is available, and no visible opponent monster has a battle
stat below 300. It changes the recorded decision to Set and still permits an
Attack Position Summon against a visible 0 DEF Sheep Token or an open direct
attack. This is a visible-state strategic preference, not a legality rule.
The controlled tournament is in [evaluation](evaluation.md); the guard is
not part of default Tactical v14 or the neural policy.

### Nobleman and Heavy Storm resource review

The player-reviewed neural-v14 versus Tactical-v14 Return/Flip seed-9901
trajectory (SHA-256 `a8158006692a3f7e68aaff18a5c910cc1bb1344ebebf6aec50f90f398f4df3a6`)
has two clear resource losses by the neural seat. At decision 10 (viewer frame
11), it activates Nobleman of Crossout while its own Set Gravekeeper's Spy is
the only face-down monster; selection of that Spy is then forced. At decision
25 (viewer frame 26), it activates a Set Heavy Storm against two *other* own
Set Spell/Traps and no opposing back row. Both complete choices replay-verify.
Tactical v14 declines these exact activations, but an audit of 32 other
policy-visited duels found that teacher still chose a negative visible Heavy
Storm trade in 27 of 56 opportunities. Do not treat it as an expert label for
this decision class.

The replay reviewer now shortlists Nobleman activation with only an own Set
monster, Heavy Storm with no targets, and Heavy Storm where the visible
opposing back-row count cannot pay for the Spell plus the controller's other
back-row cards. A Set Heavy Storm is counted as the Spell being spent, not as
an additional card destroyed by its effect. These are player-visible review
prompts, not claims about hidden opponent cards or about optimal play after
possible chain responses. The opt-in Tactical resource guard and neural
feature experiments are measured in [evaluation](evaluation.md).

The two explicit user corrections are now versioned in
[`neural_v14_return_flip_9901_resource.preference.json`](../examples/preferences/neural_v14_return_flip_9901_resource.preference.json).
The source JSON can be restored from the committed standalone viewer without
changing its SHA-256:

```bash
PYTHONPATH=src python scripts/extract_embedded_replay.py \
  replays/neural_v14_vs_tactical_return_flip_seed9901.html \
  .cache/goat-ai/neural_v14_return_flip_9901.json
```

With the pinned native assets, all 329 restored decisions replay-verify and
pass the player-visibility audit. At decision 10, setting a Spell/Trap or
ending the turn is marked preferable to activating Nobleman on the only Set
monster, its own Spy. At decision 25, ending the turn is marked preferable to
activating Heavy Storm against only its own two other Set cards. The exact
alternative indices are engineering interpretations of the user's rejection,
not additional human demonstrations. The same v23 policy that generated the
replay still ranks both rejected actions first; the preferred-minus-rejected
logit margins are −1.119 and −1.229. Previous two-preference fitting corrected
these exact frames but suppressed useful activations elsewhere, so this file
is a durable evaluation/training case, not evidence for promoting that child.

## Frozen-parent check after selection-progress masking

The 32 complete lower-temperature PPO training replays from seeds 21200–21231
were native replay-verified and visibility-audited before comparing their
62 conservative mistake flags with the unchanged imitation parent's greedy
choice on each exact player-visible state. The parent chose the same flagged
action in **49/62** cases. This includes **14/14** end-turn choices with an
activatable Thunder Dragon, **11/11** own-only Nobleman activations, **7/10**
weak Flip Normal Summons, and **3/4** Ring self-targets. Other categories
include three empty Thunder searches, three premature weak-Flip Metamorphoses,
and one self-banish each with Black Luster Soldier and Chaos Sorcerer. In
contrast, the parent avoided both negative visible Heavy Storm trades and
the single own-target Raigeki Break and MST cases seen in this sample.
The ignored report is
`.cache/goat-ai/fv23_ppo_temp05_masked_parent_diagnostic_21200_21231.json`
(SHA-256 `21e85919ba9ade40b4576a92d38c50f77952b73d2a062e3f08e4593dcafb9587`).
These flags are conservative review prompts, not proof of optimal alternatives
or human labels. The comparison does not reproduce the changing PPO policy's
sampled action distribution; it shows that many bad candidates already rank
first under the frozen parent on those visible states.

New self-play trajectories explicitly mark `selection_progress_mask: 1`.
The replay provenance audit rejects an `unselect_card` choice while a legal
`select_card` or `finish_selection` exists under that marker, and preserves
legacy unmarked trajectories as the earlier sampling mode. An eight-duel
rerun of seeds 21200–21207 recorded the marker; all **5,918** decisions
replay-verified and passed the visibility audit. Its decisions exactly match
the previously recorded masked run's eight corresponding duels. The ignored
audit is `.cache/goat-ai/fv23_ppo_masked_provenance_21200_21207_audit.json`
(SHA-256 `ef8365d11a409d6f8649fb52c2b1abb38c12f97187ea6d7574ccd2f688c687d4`).
The earlier 32-duel experiment predates this per-trajectory marker; its
checkpoint configuration and pinned source identify the mask, but its replay
files should not be silently relabeled. Future collections use the explicit
marker. The persistent Thunder and Nobleman cases are priorities for
independent player review and broader action-value learning.

## New Jersey seed 96000, seat 1: player timing notes

The reviewed replay is
`.cache/goat-ai/new_jersey_parent_review_96000_96001/matchup_0_seed_96000_seat_1.json`
(SHA-256 `5be5038039a2db68cb27f3e29cc9d745d1f713b3213d6f5f711f9916ec7ce68e`).
P2 is the feature-v23 neural policy; P1 is Tactical-v14. These player
identities matter when attributing a mistake or building policy labels.

At viewer frame **3**, P1 Set Magician of Faith while both Graveyards were
empty. Set Sangan was a legal alternative in the same hand. The reviewer
prefers Sangan because there was no Spell to recover and Magician of Faith
could be attacked. This is a tactical-baseline issue and a contextual
preference, not an automatic rule for every empty-Graveyard position.

On P2's turn 2, it Set Mirror Force (frame **18**), Call of the Haunted
(**22**), Smashing Ground (**26**), and Metamorphosis (**30**). The last two
are Normal Spells, leaving four back-row cards exposed before ending the
turn. Advancing to the Battle Phase was legal at both frames 26 and 30.
The reviewer notes that setting all available Spells and Traps can produce
large losses to Heavy Storm; keep both frames as review candidates because
some cards and positions justify setting them.

At frame **152**, on P1's turn 5 Main Phase 1, P2 activated Set Call of the
Haunted to revive Don Zaloog immediately after Don entered the Graveyard.
Passing was legal. The reviewer prefers keeping Call available until an
attack, threatened removal, or the opponent's End Phase creates a reason to
act. The visible record does not establish that passing would win the duel;
the choice is a timing preference for review, not a proven optimal label.

Historical [Call of the Haunted rulings](https://www.goatformat.com/rulings1.html)
allow activation during either player's Battle Phase in response to an attack.
The same archive's Bottomless Trap Hole ruling says that, when Call at Chain
Link 2 Summons a monster before Monster Reborn at Chain Link 1 Summons
another, Bottomless after resolution can remove only the latter. Thus a
Summon *during* a resolving chain cannot receive an immediate new response,
but a Summon that is the last event of chain resolution can still open a
Summon-response window. The timing benefit is conditional; it must not
be encoded as blanket immunity to Torrential Tribute or Bottomless Trap Hole.

The three P2 decisions are offered, without preset labels, in the ignored
`new_jersey_parent_review_96000_96001/user_notes_96000.html` queue. Its
recorded action and legal alternatives come from the native-verified,
visibility-audited replay. The queue does not change the original replay or
previous review choices.

## Focused own-card removal review queue (29 October 2026)

Sixteen fresh greedy v23-versus-Tactical duels on seeds 99900–99907,
alternating policy seats across Theeresak/Phoenix and Ryan Hayakawa/Bryan
Coronel New Jersey pairings, completed and passed exact native replay and
player-visibility checks (**8,275** decisions). The policy's **4,068**
reproduced choices included five own-only Nobleman of Crossout activations
and one Breaker target on its own back row. The audit saw 12 distinct
turn/phase opportunities for own-only Nobleman and the agent activated it in
five. These are visible review flags, not claims about every line's optimal
play. The ignored audit is
`.cache/goat-ai/own_card_parent_review_99900_99907/audit.json` (SHA-256
`e6963138e2cafc4dc61cf00c26b5323b2c58e944ff4a13211bde406b58cdcc58`).

The focused queue contains **all six** flagged contexts. Its Breaker target
prompt had only one legal target, so that item instead opens the earlier
optional Breaker activation where **Pass** was legal. This allows the reviewer
to label the avoidable activation rather than choose another forced target.
The queue gives no preset training labels; Tactical and Pass are suggestions
for inspection. All six queue items and their four exact source replays passed
the queue provenance and legal-action validator. The ignored queue is
`.cache/goat-ai/own_card_parent_review_99900_99907/queue.json` (SHA-256
`f8da8c20b22052b31d4606e4b3b8c10f1e16edb6c81bbf98b922b90eec16a9a1`).
Open it with:

```bash
./start_review_viewer.sh .cache/goat-ai/own_card_parent_review_99900_99907/queue.json
```

The review server saves selected legal actions locally. A reviewer can also
mark an item as an upstream mistake or leave it unlabeled; neither action is
silently converted into a training preference.

For an optional activation that is clearly bad but has no obvious best legal
replacement, choose **Reject the AI's recorded action** under Review finding
and save the note. This is a negative-only review: it does not assert that Pass,
Battle Phase, or any other action is optimal. Clear any saved action choice for
that frame first. After reviewing, convert explicit rejections with:

```bash
.venv/bin/python -m scripts.convert_rejected_review_notes \
  .cache/goat-ai/own_card_parent_review_99900_99907/queue.json \
  REVIEW_LABEL_FOLDER OUTPUT_PREFERENCE_FOLDER --native-root .cache/goat-ai
```

The converter checks the queue, exact replay bytes, native replay, and
player-visible observations. Its preferences exclude only the rejected
action. Train with `scripts.train_review_preferences --objective masked_parent`
using each printed replay/preference pair; this preserves the parent's ranking
among all other legal actions. Training rechecks the saved queue and note
hashes, so rerun the converter after editing a note. These labels can support
an experiment, but they do not establish better playing strength. Compare a
trained child on
fresh decks and seeds before promotion. Existing upstream/context notes remain
separate from training.

## Idle own-Ring coverage and outcome-blind review (29 October 2026)

A scan of the existing v7 guard-distillation training (32 duels), preservation
(8 duels), and prior own-card held-out review (16 duels) replays found **zero**
decisions where the proposed idle own-Ring v3 filter applies. Relabeling those
replays cannot teach that behavior. A five-duel diagnostic selected from games
whose outcomes differed between v1 and v3 found one such Ring activation in
each replay. That selection is conditioned on outcome, so it is useful for
debugging but unsuitable for estimating the behavior's frequency or building a
representative training set.

To measure coverage without selecting on the winner, we recorded **128**
complete v23-policy (v1 inference guard) versus Tactical-v14 duels on seeds
104400–104407. The fixed schedule used four Main Deck pairings in both deck
assignments and both policy seats. All **74,685** decisions passed exact native
replay verification and player-visibility auditing. Among **37,132** policy
decisions, the v3 Ring filter would apply at **47** prompts; the v1 policy
activated Ring at **14** of those prompts. These are prompt counts, potentially
including repeated opportunities in one game, and do not measure optimality.
The ignored replay manifest is
`.cache/goat-ai/ring_guard_blind_104400_104407/manifest.json`.

All 14 chosen activations are in the ignored
`.cache/goat-ai/ring_guard_blind_104400_104407/queue.json` queue. Its 14 source
replays were independently replay-verified while shortlisting; their queue
hashes and legal actions also passed the queue validator. The suggested
alternative is the highest-scoring move *after* the visible v3 guard, not a
human-approved play. The reviewer should mark whether Ring itself was a
mistake, whether the proposed alternative was preferable, or whether the
position needs a different choice. Open the queue with:

```bash
./start_review_viewer.sh .cache/goat-ai/ring_guard_blind_104400_104407/queue.json
```

Reviewer reveals remain separate from the policy's player-visible observation.
No new preference labels or neural checkpoint were promoted from this audit.

The same outcome-blind batch also contained **two** Heavy Storm activations
with a negative visible back-row trade and **one** Ring target choice on the
policy's own monster while a visibly safer opposing monster was selectable.
Those three decisions are in
`.cache/goat-ai/ring_guard_blind_104400_104407/other_own_card_queue.json`.
The three source replays passed exact native verification during shortlisting;
all three queue items passed the legal-action and provenance validator. The
suggested move comes from Tactical-v14 and may itself be poor: in both Heavy
Storm positions it also preferred activating Heavy Storm. The reviewer should
use the queue to evaluate the *activation* and may reject it without endorsing
a replacement action. Open it with:

```bash
./start_review_viewer.sh .cache/goat-ai/ring_guard_blind_104400_104407/other_own_card_queue.json
```

The own-card audit now includes these categories and Ring's idle activation
opportunities. Deduplicating repeated prompts by category, turn, and phase
gives **22** Ring contexts in this batch; the raw count above is 47 prompts.
The same deduplicated scan counted 96 own-only Heavy Storm, 158 own-only
Nobleman, and 26 idle own-only MST opportunities, with no chosen activations
in those three categories. These are narrow visible-state measurements; they
do not establish a general card-advantage understanding or improved match
strength.

For a single review pass, the ignored
`.cache/goat-ai/ring_guard_blind_104400_104407/own_card_review_queue.json`
combines the **14** idle own-Ring choices, **two** negative visible Heavy Storm
trades, and **one** own-monster Ring target. All **17** source duels and
**10,659** total decisions were exact-replay-verified and visibility-audited
during queue generation. The 17 queue items then passed the independent
source-hash and legal-action validator. No item is pre-labeled as correct or
incorrect; the suggestions mix the visible v3 guard and Tactical-v14 and
must not be treated as an expert teacher. Open the combined queue with:

```bash
./start_review_viewer.sh .cache/goat-ai/ring_guard_blind_104400_104407/own_card_review_queue.json
```

### Resolving one-shot Spell/Trap response review (29 October 2026)

The ignored queue
`.cache/goat-ai/one_shot_review_104400_104407/queue.json` contains 11
selected-policy decisions where removal targeted an activated one-shot Spell
or Trap that was already resolving. The 11 source duels and 7,083 decisions
were exact-replay-verified and visibility-audited during queue construction;
the queue file has SHA-256
`760fd1989217a4bfb933ff62478b76e0e32b17e68bd3fe0474b6b180dc06318e`.
One forced target was moved to its preceding optional activation, allowing a
reviewer to choose Pass. The other ten items retain their target-choice
prompts. The offered Tactical alternative is a comparison, not a correctness
label. An activated one-shot effect usually still resolves when its card is
destroyed, but the removal may matter for another field card or a chained
effect; inspect the complete position before labeling. Open the queue with:

```bash
./start_review_viewer.sh .cache/goat-ai/one_shot_review_104400_104407/queue.json
```

Seven later saved **context** notes in this queue describe MST activation as
the earlier mistake while the displayed frame offered target choices. The
upstream queue builder now accepts `--include-context-notes` for this case.
It preserves the note text and its `context` kind, locates the matching
earlier optional activation from the public chain source, and offers Pass
there as a **review candidate**, not as an inferred human label. All seven
source duels passed exact native replay and visibility checks; every note
mapped to a distinct earlier MST activation with Pass legal. The ignored
queue `context_upstream_20261029.json` has SHA-256
`49dc86e53a48988377abecf2db515977878f3dc2baf1182cbeaffcf16d19c862`.
Open the save-enabled activation review with:

```bash
./start_review_viewer.sh .cache/goat-ai/one_shot_review_104400_104407/context_upstream_20261029.json
```

These seven choices remain unlabeled until the reviewer selects an action on
the new queue. The earlier target approvals in the source queue do not imply
approval of MST activation. The new queue is a reproducible transformation of
the saved notes: run `scripts/create_noted_upstream_queue.py` on the source
queue with `--include-context-notes` and `--output` set to the path above.

### Combined own-card activation review (29 October 2026)

The 17-item own-card queue and seven earlier MST activation prompts now have
one save-enabled review session. The combined queue contains **24 distinct
decisions** from **23 source duels**. Its builder rechecked the exact source
bytes, queue metadata and legal actions, native replay, and visibility for
all **14,028** decisions before writing the queue. It requires one checkpoint
and rejects duplicate decision identities. Existing labels in either source
queue are not transferred or interpreted as approvals; the seven context
notes remain explanatory text, not preference labels.

Open the combined queue with:

```bash
./start_review_viewer.sh .cache/goat-ai/own_card_activation_review_20261029.json
```

The ignored queue SHA-256 is
`759559e604d8b87b1bfd707fe467d3a2dd3328f86df8815a77f33f715a6ec737`.
To rebuild it, run:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/combine_review_queues.py \
  .cache/goat-ai/ring_guard_blind_104400_104407/own_card_review_queue.json \
  .cache/goat-ai/one_shot_review_104400_104407/context_upstream_20261029.json \
  --output .cache/goat-ai/own_card_activation_review_20261029.json \
  --native-root .cache/goat-ai
```

For a clearly poor activation with several plausible replacements, the
reviewer can use **Reject the AI's recorded action**. The existing
`convert_rejected_review_notes.py` checks the saved finding against the
combined queue and exact replay before producing a negative-only training
preference. The queue's suggested alternatives are not human judgments.
