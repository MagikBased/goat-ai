# Competitive-deck action coverage probe

## Main Deck priority report

Run `PYTHONPATH=. .venv/bin/python scripts/report_competitive_card_priorities.py
--native-root .cache/goat-ai --top 30` from the repository root. The report
counts each card's presence and copies in the six sourced tournament Main
Decks linked in [the roadmap](roadmap.md), then lists historical test files
containing its exact numeric card ID. Use `--json` to inspect every row and the
individual fixture paths. Extra and Side Deck cards do not enter the ranking.

This is a planning index. A numeric reference can be only a test setup card,
and several references can exercise the same ruling; zero references does not
prove the engine lacks a card script. Review the cited fixture and a historical
ruling before treating any card or interaction as audited. The six sourced
lists are a small convenience sample, not a metagame play-rate estimate.
The sixth list is [Weirdchamp's sixth-place World Championship Bazoo Return](../examples/decks/bazoo_return_weirdchamp_worlds.ydk), transcribed from the
[published 40-card list](https://www.goatformat.com/bazoo-return.html). Earlier
measured action-coverage reports below still use their original six duel deck
schedule; adding a list to the priority report does not change those results.

For the current M2 audit, prefer interactions among cards appearing in at
least three of these six Main Decks. Start with the shared staples and then
cover frequent matchup cards such as Dekoichi, Trap Dustshoot, D.D. Warrior
Lady, Chaos Sorcerer, Thunder Dragon, and Kycoo. The paired
[Warrior Lady versus Kycoo regression](goat_rules.md) applies this rule to a
historically sourced Damage Step interaction. Keep a lower-presence card in
scope when it is needed to test a common card's ruling, but do not expand the
card audit solely because the engine has a script for it. Deck-list prevalence
is a prioritization proxy, not a measured 2005 metagame play rate.

This probe counts card-source actions in complete native duels played by seeded
`RandomAgent`s. It helps prioritize GOAT ruling fixtures. It does **not**
measure historical play rates, card correctness, or agent strength. A card code
in a `select_card` target choice is deliberately excluded; otherwise targeting
an opponent's card would falsely count as using that card.

## Reproduce the first sample

Install the [pinned native assets](native_setup.md), then run from the repository
root:

```bash
PYTHONPATH=. .venv/bin/python scripts/probe_competitive_card_actions.py \
  --native-root .cache/goat-ai --seed 9700 --seeds 1 \
  --max-decisions 3000 \
  --output .cache/goat-ai/competitive-actions-9700.json \
  > .cache/goat-ai/competitive-actions-9700.stdout
```

The default schedule pairs sourced Goat Control with Chaos Turbo, Warrior with
Chaos Control, and Chaos Return with the Flip Control guide deck, swapping seats
once for each pair. The guide deck is not a submitted tournament list. The
report records each deck hash, core/database hashes, the GOAT rules profile,
and hashes for all native assets loaded during the sample. Generated reports
stay under the ignored `.cache` directory.

On the pinned local assets, seed 9700 produced **6 terminal duels** and **5,095
decisions**, with 100 loaded asset hashes in the report. The six unique Main
Decks contained 56 card identities. At least one `activate` or `chain` action
was offered for 34 of those identities and selected for 33. These counts include
repeated offers at different decisions; they do not say whether each card's
historical ruling was correct. Repeating the command produced the same JSON
SHA-256, `a74bf5a326017c9c9afe40b88f0603f6f22b8af4e576b83122e49b10b5b471f9`.

| Card in all six deck files | Offered activate/chain decisions | Selected activate/chain decisions |
| --- | ---: | ---: |
| Nobleman of Crossout | 112 | 18 |
| Snatch Steal | 73 | 20 |
| Pot of Greed | 58 | 9 |
| Graceful Charity | 52 | 10 |
| Book of Moon | 47 | 25 |
| Black Luster Soldier | 32 | 11 |
| Ring of Destruction | 20 | 8 |
| Breaker the Magical Warrior | 8 | 3 |

The full JSON contains per-card action kinds, outcomes, and individual duel
lengths. A selected action count reflects the sampled random policy. Cards
unselected in this small sample may still be important; for example, Mirror
Force was offered as a response three times but never selected. For fixture
planning, combine this measured decision exposure with the sourced deck-list
prevalence in [the roadmap](roadmap.md), then verify each candidate against
[historical rulings](goat_rules.md).

## Expanded competitive-deck sample and chain responses

The probe now also counts a selected `chain` card against the latest card in
the player-visible chain. This is an observed response pair, not a claim that
every activation or ruling for either card is correct. Re-running the original
seed-9700 sample with this additional field left every earlier report field
unchanged.

On the same pinned assets and six deck files, seeds 9710–9719 produced **60
terminal duels** with **55,009 decisions**, under the 3,000-decision cap for
each duel. Of 64 card identities appearing in the deck files or legal source
actions, 40 had an `activate` or `chain` action offered and 39 had one selected.
The sample contained **171 selected card responses** across 95 distinct
ordered response pairs. The report JSON SHA-256 was
`32798a2ff89b9c4795bed19485518c05e48f1fa26b90ce278b04315aa6ae50fb`.

| Selected response to preceding chain link | Decisions |
| --- | ---: |
| Solemn Judgment → Book of Moon | 9 |
| Solemn Judgment → Mystical Space Typhoon | 7 |
| Solemn Judgment → Solemn Judgment | 6 |
| Solemn Judgment → Compulsory Evacuation Device | 6 |
| Solemn Judgment → Nobleman of Crossout | 6 |
| Solemn Judgment → Ring of Destruction | 5 |
| Solemn Judgment → Dust Tornado | 5 |
| Dust Tornado → Book of Moon | 5 |
| Raigeki Break → Book of Moon | 3 |
| Solemn Judgment → Raigeki Break | 3 |

The sample also observed four Torrential Tribute responses to Breaker the
Magical Warrior, which already have a [historical fixture](goat_rules.md).
A reverse-order fixture checks Dust Tornado targeting a Set Book of Moon,
then Book activating in response; the activated target still permits Dust’s
optional Set. This is separate from Dust responding to Book.
Solemn Judgment responding to Book of Moon now has a source-backed native
regression. Book of Moon responding to another Book also has a native
same-target chain and visibility regression; that response appeared four times
in the sample. Trap Dustshoot chained to another Trap Dustshoot appeared three
times and now has a native two-hand reveal and full-duel replay regression.
Solemn Judgment responding to Dustshoot appeared twice and now has a paired
negated-versus-resolved hand-visibility regression.
Raigeki Break responding to Book of Moon appeared three times and has a paired
target-removal fixture. The reverse Book response to Raigeki Break now has a
paired native fixture showing that changing the targeted monster face-down
does not prevent Break from destroying it.
These counts are from random-agent choices; they do
not estimate tournament play rates or policy quality.

Reproduce the expanded sample after [native setup](native_setup.md):

```bash
PYTHONPATH=. .venv/bin/python scripts/probe_competitive_card_actions.py \
  --native-root .cache/goat-ai --seed 9710 --seeds 10 \
  --max-decisions 3000 \
  --output .cache/goat-ai/competitive-actions-9710-9719.json \
  > .cache/goat-ai/competitive-actions-9710-9719.stdout
```

## Tournament-list-only sample for the next audit queue

Use `--tournament-corpus` to pair every two lists in the six-list sourced
tournament corpus, with both seat assignments. This produces 30 games per seed
and excludes the Flip Control guide deck used by the earlier default schedule.

```bash
PYTHONPATH=src:. .venv/bin/python scripts/probe_competitive_card_actions.py \
  --native-root .cache/goat-ai --tournament-corpus \
  --seed 9830 --seeds 2 --max-decisions 3000 \
  --output .cache/goat-ai/competitive-actions-tournament-9830-9831.json \
  > .cache/goat-ai/competitive-actions-tournament-9830-9831.stdout
```

On the pinned local assets, all **60 duels terminated** in **54,322
decisions** (maximum 1,325 per duel). The report includes six deck hashes
and 103 loaded native asset hashes. Its JSON SHA-256 is
`8bd4f449225ffbfc7851e28c2357ded741682b6f402449d4f47e9599d778d3f2`.
Of 68 card identities in the deck files or legal source actions, 41 had an
`activate` or `chain` action offered and 40 had one selected. The random
agents selected 164 card responses to a public chain link.

| Card present in all six Main Decks | Copies across lists | Activate/chain offered | Activate/chain selected |
| --- | ---: | ---: | ---: |
| Nobleman of Crossout | 12 | 838 | 155 |
| Heavy Storm | 6 | 564 | 88 |
| Delinquent Duo | 6 | 543 | 74 |
| Book of Moon | 14 | 517 | 237 |
| Pot of Greed | 6 | 510 | 83 |
| Graceful Charity | 6 | 503 | 90 |
| Black Luster Soldier | 6 | 287 | 91 |
| Ring of Destruction | 6 | 153 | 80 |
| Breaker the Magical Warrior | 6 | 93 | 32 |

The next card-specific audit work should start with these shared staples and
their interactions, then the cards present in five lists: Dekoichi, Trap
Dustshoot, D.D. Warrior Lady, Mirror Force, Snatch Steal, and Torrential
Tribute. Check existing fixtures before adding one: a fixture file count is
not a count of independently validated rulings. For example, the top response
pair Solemn Judgment to Trap Dustshoot (nine decisions) and Torrential Tribute
to Dekoichi (eight) already have native regressions. The four Mirror Force
responses to Sakuretsu Armor now have a two-order native chain regression
with full-duel replay verification. The random-policy action
counts express decision exposure in this small sample, not actual tournament
play frequency, historical correctness, or strategic value.

A paired native regression now checks Book of Moon chained to Dekoichi's
already activated Flip Effect. Book sets Dekoichi at Chain Link 2 and the
draw still occurs at Chain Link 1; the pass control leaves Dekoichi face-up.
Both complete duels replay-verify. This tests one interaction between a card
in all six Main Decks and one in five; see [GOAT rules](goat_rules.md).

Heavy Storm appears in all six tournament Main Decks and Trap Dustshoot in
five. A paired native regression now checks Dustshoot chained to Heavy against
passing, including the private hand reveal and destruction of another Set
Dustshoot. Both complete duels replay-verify; see [GOAT rules](goat_rules.md).
Another paired regression tests Set Dustshoot answering Delinquent Duo, which
also appears in every tournament Main Deck: Dustshoot's addressed hand reveal
and Deck return occur before Duo's two discards. The pass branch has no reveal.
Both full duels replay-verify; the combined timing is documented as an
inference from the card texts and chain order in [GOAT rules](goat_rules.md).

## Full-duel replay verification across the tournament corpus

The action probe now accepts `--verify-replays` and `--record-dir`. With both
options, it serializes each complete native duel, reads the JSON back, and
checks every player-visible observation, complete legal-action list, selected
action, terminal result, and recorded native-asset fingerprint against a fresh
engine. A capped or mismatching game fails the probe rather than entering the
report. Without `--record-dir`, verification uses the in-memory trajectory.
Generated trajectories and reports stay outside Git.

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python \
  scripts/probe_competitive_card_actions.py \
  --native-root .cache/goat-ai --tournament-corpus \
  --agent combat_heuristic --seed 18500 --seeds 1 \
  --max-decisions 3000 --verify-replays \
  --record-dir replays/tournament_verified_18500 \
  --output .cache/goat-ai/tournament_verified_18500.json
```

On the pinned local assets, all **30** both-seat duels across the 15 pairs of
six sourced tournament Main Decks terminated and replay-verified after JSON
round trip. The report records **16,979 decisions**, a maximum of **1,448**
in one duel, **103 loaded asset hashes**, and **64 selected card responses**
to a public chain link. The report SHA-256 is
`861dc028cb8b93f557c08ab6054150aa6b8d7e39bf044671fcefebbef1176ab2`.
The 30 ignored JSON trajectories occupy 118,957,204 bytes. These results
demonstrate deterministic reconstruction for this agent, decks, and seed;
they do not independently validate the historical correctness of every card
effect or estimate human card usage.

The verified sample selected Raigeki Break in response to another Raigeki
Break ten times, tied for the most frequent ordered card-response pair. A
paired native regression now checks a Break that destroys an activated Break
against passing: the first Break's already activated monster-destruction
effect still resolves, and both activated cards retain their discard costs.
Both complete duels replay-verify. See [GOAT rules](goat_rules.md) for the
source and historical-evidence limit.

### Same-seed RandomAgent coverage check

The same 30 tournament pairings and seed 18500 were also run with
`--agent random --verify-replays` and no `--record-dir`. All **30 complete
duels and 25,782 decisions** replay-verified from their in-memory
trajectories; the maximum duel had 1,241 decisions. The report SHA-256 is
`7021e8eb0952c92e62e796f7a48f0f5aea68a8f204688e4e478151b26ccd08b7`.
The earlier combat run verified after a JSON round trip; this random run did
not test trajectory serialization.

| Selected source action | Combat heuristic | Random |
| --- | ---: | ---: |
| Dekoichi Flip Summon | 0 | 21 |
| Nobleman activation | 13 | 63 |
| Trap Dustshoot chain activation | 3 | 39 |
| Book of Moon activation or chain | 34 | 110 |
| Black Luster Soldier Special Summon | 9 | 38 |

The random duels contained **8,803 more decisions** than the combat duels,
and the policies reached different states. The counts are coverage signals,
not normalized usage rates, historical play frequencies, or measures of agent
strength. For additional Flip, hidden-hand, and removal correctness audits,
use the random schedule; retain the combat schedule for behavior under the
stronger baseline. Compare both against source-backed fixtures before making
historical-ruling claims.

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python \
  scripts/probe_competitive_card_actions.py \
  --native-root .cache/goat-ai --tournament-corpus \
  --agent random --seed 18500 --seeds 1 \
  --max-decisions 3000 --verify-replays \
  --output .cache/goat-ai/tournament_random_verified_18500.json
```

## Randomized decks from the tournament card pool

The random-deck probe also accepts `--card-pool tournament`. It shuffles the
Main Deck card copies from the six sourced tournament lists, takes 40 cards
without exceeding the pinned GOAT copy limits, and uses one sourced Extra Deck
chosen by seed. Every generated list passes the normal deck validator. These
are synthetic mixtures of frequently represented cards, not submitted
tournament lists or realistic strategy models. The original full-whitelist
generator remains the default. `--verify-replays` checks each terminal duel
against a fresh engine and fails the command if any game hits the decision cap
or encounters an adapter or replay error.

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python \
  scripts/probe_random_decks.py --native-root .cache/goat-ai \
  --card-pool tournament --seed 18600 --seeds 50 \
  --max-decisions 3000 --verify-replays \
  --output .cache/goat-ai/tournament-mix-18600-18649
```

On the pinned local assets, **50/50 distinct generated decks** reached a
terminal native result and **46,875/46,875 decisions** replay-verified, with
no cap or recorded adapter error. The longest duel had **1,310 decisions**.
The decks used **59 distinct Main Deck card identities** from the six-list
corpus; the report records **27 legal action kinds**, six source-deck hashes,
six pinned asset hashes, and **103 loaded asset hashes**. Its SHA-256 is
`e79bbd9951dc7fa6a9f91822ea09b58210665c877d2e0080bbe408e742674cd5`.
The generated YDK files and report stay under ignored `.cache/goat-ai/`.
This checks deterministic execution of these newly combined cards, not
historical legality of every interaction or playing strength.

The probe also accepts `--distinct-opponents`, which gives each generated
deck an independent opponent mix using seed plus 1,000,000. It retains the
same seeded duel and verification protocol and writes both YDK files under
the ignored output directory. This tests cross-deck effects that mirror
matches may never present.

```bash
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python \
  scripts/probe_random_decks.py --native-root .cache/goat-ai \
  --card-pool tournament --distinct-opponents \
  --seed 18650 --seeds 50 --max-decisions 3000 \
  --verify-replays \
  --output .cache/goat-ai/tournament-cross-18650-18699
```

On the pinned local assets, **50/50 cross-deck duels** terminated and
**48,248 decisions** replay-verified. The 100 generated Main Deck
compositions were distinct, including within each pair. The longest duel
had **1,482 decisions**; no cap or adapter error was recorded. The report
contains both YDK hashes per game, the six source-deck hashes, the GOAT
rules profile, and **103 loaded native asset hashes**. Its SHA-256 is
`54d74a091a9dfa1d32526afab3697215ac6e28b0507149d92ca09800eb8738ee`.
This strengthens protocol coverage across common-card combinations without
proving every historical interaction correct.

### Card-source actions in the cross-deck sweep

Use `--count-card-actions` with the cross-deck command above to add
`card_actions` and `chain_responses` to its report. The counter uses the same
player-visible source-card rules as the fixed-deck probe: a target card's ID
does not count as playing that card. It reports both legal offers and actual
selections. Some `chain` actions are triggered or continuous card effects, so
the kind alone is not always a new card activation.

On seeds 18650–18699, adding counting left **all 50 winners, decision counts,
and both deck hashes per game unchanged**. All **48,248 decisions** again
replay-verified. The counted report has 264 card/kind rows, 67 card identities
with a selected source action, and 131 selected responses to a public chain
link. Its SHA-256 is
`c11c8e2c01101de23768f6e1a3f5490069bba86b87186735fe677a39fca4633a`.

| Selected action | Decisions |
| --- | ---: |
| Book of Moon chain | 175 |
| Nobleman of Crossout activation | 114 |
| Trap Dustshoot chain | 91 |
| Dekoichi Flip Summon | 61 |
| Heavy Storm activation | 60 |
| Graceful Charity activation | 51 |

The most frequent selected response pair was Solemn Judgment to Book of Moon
(six decisions), which has a [source-backed fixture](goat_rules.md). Several
other frequent pairs already have regressions. These generated decks and
RandomAgent choices are a mechanism-coverage tool, not tournament play-rate
evidence. Use the counts to prioritize independent historical rulings and
paired native tests.

## Same-schedule random and combat-baseline exposure

The probe also accepts `--agent combat_heuristic` (or `heuristic`). This
changes only the agent selecting from the same player-visible observations
and legal actions. Use matching seeds and tournament pairings to see how a
baseline's choices alter card exposure:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/probe_competitive_card_actions.py \
  --native-root .cache/goat-ai --tournament-corpus --agent combat_heuristic \
  --seed 9840 --seeds 1 --max-decisions 3000 \
  --output .cache/goat-ai/competitive-actions-combat-9840.json \
  > .cache/goat-ai/competitive-actions-combat-9840.stdout
PYTHONPATH=src:. .venv/bin/python scripts/probe_competitive_card_actions.py \
  --native-root .cache/goat-ai --tournament-corpus --agent random \
  --seed 9840 --seeds 1 --max-decisions 3000 \
  --output .cache/goat-ai/competitive-actions-random-9840.json \
  > .cache/goat-ai/competitive-actions-random-9840.stdout
```

Both runs completed 30/30 terminal games, including one draw under the
combat baseline and three under random selection. The combat run recorded
15,904 decisions and 56 selected card responses; its report SHA-256 is
`1617e0f1a212344fa3b4f1627468746aa28e9b71252427d324a0c126185949cb`.
The random run recorded 28,222 decisions and 79 selected card responses;
its report SHA-256 is
`f0bda7b365718155a99c37b95a8c7e5bca23fb0608a1d712853297d4b48e53ad`.
Repeating the random run produced that same SHA-256.
The two agents induce different game lengths, so raw action counts are not
comparable play rates. Book of Moon was the most selected activate/chain
staple in both samples (58 combat, 117 random). The combat sample also
selected Torrential Tribute 38 times and chose it in response to Tsukuyomi
four times. A paired native regression now tests that response against a
pass control, then replay-verifies both complete duels; see
[GOAT rules](goat_rules.md).
Trap Dustshoot responded to Mystical Space Typhoon twice in this sample.
Another paired native regression now compares that response with passing on
the Trap, checks the recipient-scoped hand reveal, and replay-verifies both
duels. These are fixture priorities from a deterministic baseline sample,
not estimates of human usage.

The random run first uncovered a valid zero-card `MSG_CONFIRM_DECKTOP` frame
that the adapter incorrectly rejected. The pinned core permits this frame
when no cards are available to reveal. The adapter now accepts it without
adding an empty card-reveal event, and the run completes. This is a protocol
fix, not a card-specific historical ruling.
