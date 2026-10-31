# Search under hidden information

GOAT AI has an offline branch diagnostic that reconstructs a recorded duel from
its actual seed and Deck order. That is useful for debugging a past decision,
but it is **not** an online search agent: a player could not have known that
hidden deal. The [architecture](architecture.md) and
[M5 roadmap](roadmap.md#m5--search-and-other-formats) keep search behind the
historical-rules and competitive-policy gates. This document records the
algorithm choice and the minimum experiment needed to revisit it.

## Candidate methods

| Method | What it offers | Main GOAT risk or cost |
| --- | --- | --- |
| Independent perfect-information searches on sampled deals | Simple first diagnostic once legal hidden deals and state reconstruction exist | The search can choose different later actions in states the player cannot distinguish. This **strategy fusion** can make the root action look better than it is; separate trees also duplicate work. [Cowling et al., 2012](https://eprints.whiterose.ac.uk/id/eprint/75048/1/CowlingPowleyWhitehouse2012.pdf) |
| Root-sampled policy rollouts with one shared root action | A small controlled test of whether extra native simulation helps the present policy | Still depends on a valid belief distribution, opponent policy and terminal/value estimate. It cannot justify acting on the actual hidden deal. This is the recommended **first experiment**, not a production search design. |
| Information Set MCTS | Shares statistics among states treated as the same information set and addresses some determinization waste and strategy fusion | Needs a correct information-set key, legal-action handling across differing sampled states, opponent modeling, and enough simulations per decision. The original paper tested other games; its GOAT benefit is unmeasured. [Cowling et al., 2012](https://eprints.whiterose.ac.uk/id/eprint/75048/1/CowlingPowleyWhitehouse2012.pdf) |
| Online outcome-sampling CFR | Searches an imperfect-information game without giving the acting policy the real deal | Requires a tractable continuation game, information-set representation, and opponent reach probabilities. A bounded GOAT subgame and useful value function have not been established. [Lisý et al., 2015](https://ifaamas.org/Proceedings/aamas2015/aamas/p27.pdf) |
| Deep CFR | Approximates regret minimization with neural networks in large imperfect-information games | Training cost and regret targets would be substantial for GOAT's card effects, variable actions, and long duels. Poker results do not establish transfer to GOAT. [Brown et al., 2019](https://proceedings.mlr.press/v97/brown19b.html) |
| ReBeL-style public-belief search | Connects self-play learning and search in a public-belief state | Needs a validated belief update, public-state representation, and repeated subgame solving. Those pieces are absent. Its theoretical result assumes a correct two-player zero-sum game model; it does not validate our historical simulator. [Brown et al., 2020](https://papers.neurips.cc/paper_files/paper/2020/hash/c61f571dbd2fb949d3fe5ae1608dd48b-Abstract.html) |

The root-sampled rollout is the smallest experiment that can answer a useful
question now: whether spending simulator calls on a decision improves
held-out play. It is not a commitment to determinization as the final method.
If it helps but shows strategy fusion or opponent-model sensitivity, test an
information-set tree next. CFR and public-belief learning need a separate
feasibility study after a reliable short-horizon subgame representation exists.

## Information boundary and prerequisites

1. Define a **player-consistent belief** from the acting player's observation,
   public history, and an explicitly declared deck prior. Preserve each known
   opponent hand or field identity and all public card movements. Sample only
   unknown identities and order. The evaluator may know a tournament Deck
   for an offline audit; the online agent may use it only if that knowledge
   was actually supplied to the player. An opponent Deck file being present
   on disk is not player knowledge.
2. Reconstruct or clone native states from sampled deals with exact GOAT
   scripts and seed handling. Current replay-prefix reconstruction reproduces
   a **known** deal, and the viewer's private reveal sidecar intentionally
   contains hidden Deck order. Neither is an online belief sampler. Never
   pass reviewer sidecars, actual seed words, or private native queries to
   action selection. A [measured prefix benchmark](benchmarks.md#exact-replay-prefix-reconstruction-for-search-feasibility-31-october-2026)
   took 0.210 seconds for 302 decisions and 0.567 seconds for 964 decisions
   on two recorded deals; those timings exclude sampling and rollouts.
3. At the root, enumerate actions from the real player-visible legal-action
   API. Before executing a sampled continuation, reject a sample whose
   public observation or root legal-action set differs. Use one common
   sampled-deal schedule for every root action; record rejected samples and
   the reason. Rollout policies at later decisions receive only their own
   observations, including the simulated opponent's view.
4. Freeze the opponent pool and value/rollout policies for the comparison.
   Record native asset hashes, checkpoint hashes, belief-prior version,
   sample seeds, rollout budget, and action-selection latency. Cap work per
   decision and fail explicitly on unsupported native prompts.

## Promotion experiment

First use synthetic hidden-state differential fixtures: two native states
with identical acting-player observations and legal actions but different
opponent hands or Deck order. With the same declared belief and search seed,
the search must return identical root scores and action in both. This is a
stronger check than verifying that a single sampled trajectory contains no
hidden field.

Then compare **policy alone** and **policy plus root-sampled rollouts** on
new historical Main Deck compositions, paired seeds, both Deck assignments,
and both seats. Verify every duel from native replay and audit the saved
player-visible trajectory. Report score and paired confidence interval,
decisions per second, median and tail decision latency, simulator calls,
memory, and unsupported-request rate. Include a different opponent family
from the search rollout opponent. A gain on the same Decks or one fixed hidden
deal is insufficient. Search remains experimental unless it improves
held-out competitive results within an acceptable latency budget and passes
the hidden-state differential tests.

No GOAT search agent or belief sampler is implemented yet. The selected v23
policy has not passed M4's held-out strength or self-play gain gates, and M2's
arbitrary-card correctness audit remains open; these are substantive reasons
to defer online search deployment.
