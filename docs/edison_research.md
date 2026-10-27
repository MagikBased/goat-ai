# Edison format feasibility and historical inputs

Edison is a future, separate rules profile. The current GOAT adapter must reject
an Edison request; a March 2010 list cannot make its 2005 card scripts and rules
historically correct for 2010.

## Verified format boundary

[Konami's Time Travel FAQ](https://www.yugioh-card.com/en/play/alternate_format_tournaments/time-travel/)
defines Edison using the [March 1, 2010 TCG Forbidden & Limited List](https://www.yugioh-card.com/en/downloads/alt_format/2010-03-01.pdf)
and the card pool through *Duelist Pack: Kaiba*. These are separate constraints:
the restriction list gives copy caps, while the release cutoff determines which
otherwise unrestricted cards can be played. Neither defines all 2010 rulings.

The factual Advanced Format restrictions from that PDF are transcribed in
[`configs/historical/edison_2010_03_01_advanced_limits.tsv`](../configs/historical/edison_2010_03_01_advanced_limits.tsv).
It contains 45 Forbidden, 70 Limited, and 20 Semi-Limited names. Names were
matched case-insensitively to the pinned Project Ignis `cards.cdb`; duplicate
artwork/print IDs were reduced to their database `alias` root. Every one of
the 135 names resolved to exactly one canonical card. The downloaded PDF had
SHA-256 `a4eb75169aea3148b1fa10b9fe8b9fe9116a6c321df9a4fd176d7024dfb5c71f`.
The PDF is kept only in ignored local cache. The TSV is an input to future deck
validation, **not** a complete Edison whitelist or playable engine profile.
For example, Stardust Dragon is absent from the restriction list, which says
nothing by itself about release eligibility or simulator correctness.

One explicit trap in the official restriction list is Dewloren, Tiger King of
the Ice Barrier (`70583986`): it is Semi-Limited there, but [Konami's Hidden
Arsenal 2 product page](https://www.yugioh-card.com/en/products/past_products/ha02/)
says that set contained Dewloren and became tournament legal July 20, 2010,
after the Edison cutoff. Its list entry must **not** make it Edison-legal.

As a candidate-pool cross-check, `scripts/audit_edison_pool.py` compared the
unbundled [edisonrul.ing card-pool CSV at commit `1c43eb1`](https://github.com/vivaria/edisonrul.ing/blob/1c43eb150db4043ecf80456f2e3d46d87707de44/edison_cardpool.csv)
against the pinned database and official restrictions. The cached CSV SHA-256
was `be47a612299dcdd683561979d5b8bc31d302887a24ca1f146e6a23fe79b55ee3`.
Of its 3,631 candidate IDs, nine lacked pinned metadata; no represented
card's stated copy cap disagreed with the official list after alias resolution;
and Dewloren was the sole non-Forbidden restriction absent from the candidate.
This is **not** an independent audit of every release date or proof that all
eligible cards appear in the candidate. The external CSV has no identified
redistribution license, so it remains in ignored cache and is not vendored.
Reproduce the comparison after placing that CSV locally:

```sh
PYTHONPATH=. .venv/bin/python scripts/audit_edison_pool.py \
  path/to/edison_cardpool.csv .cache/goat-ai/database/cards.cdb \
  configs/historical/edison_2010_03_01_advanced_limits.tsv
```

## Native engine assessment

The [contemporary Yu-Gi-Oh! 5D's official rulebook](https://www.edisonformat.com/uploads/1/3/4/1/134149181/yugioh5dsofficialrulebook.pdf)
sets 40–60 Main Deck cards, at most 15 Extra Deck cards containing only Fusion
and Synchro Monsters, at most 15 Side Deck cards, and three copies of a card
across all three zones before Forbidden/Limited restrictions. The new
`validate_edison_deck` function enforces those construction limits and the
March 2010 canonical copy caps against pinned card metadata. It requires an
explicit caller-supplied set of eligible card IDs; the project has not yet
established the complete dated TCG release pool, so this function cannot by
itself certify a real deck as Edison-legal. It also rejects later Xyz, Pendulum,
and Link types even if a bad candidate pool includes them. Synthetic database
tests cover size, zone, alias, restriction, release-pool, and future-type
boundaries. The GOAT validator and native adapter are separate and unchanged.

Konami's [current Time Travel FAQ](https://www.yugioh-card.com/en/play/alternate_format_tournaments/time-travel/)
uses the historical card pool and list but *current mechanics and current card
text* (with historical first-turn draw and field layout). This differs from
reconstructing the 2010 tournament's original rulings. The project's Edison
research target is the latter; a Time Travel profile would need separate
validation and versioning if added.

The pinned Project Ignis database has metadata for representative Edison
Synchros including Stardust Dragon, Black Rose Dragon, Brionac, Goyo Guardian,
and Dark Strike Fighter. Metadata presence does not validate 2010 scripts,
errata, release dates, or rulings. The present GOAT deck validator allows only
Fusion monsters in the Extra Deck and must not be reused for Edison.

The pinned core exposes `DUEL_MODE_MR1`, `DUEL_MODE_MR2`, and `DUEL_MODE_GOAT`
in `ocgapi_constants.h`, but no Edison mode. `DUEL_MODE_MR1` includes obsolete
Ignition timing and first-turn draw; `DUEL_MODE_GOAT` adds old TCG-specific
flags. Choosing an Edison flag combination requires sourced ruling tests. The
current native bridge also contains GOAT-specific card and script corrections.
It must be separated or revalidated before Edison play is enabled.

An isolated `mr1_startup` probe now starts the pinned core with its exact
`DUEL_MODE_MR1` bit mask (`853760`) and the unmodified upstream `utility.lua`.
It accepts only 40-card-or-larger Normal Monster Main Decks and empty Extra
Decks. On seed 42, the 40-card vanilla fixture reached the first native
decision with hand counts `(6, 5)`, Deck counts `(34, 35)`, and draw events
`(0, 5)`, `(1, 5)`, `(0, 1)`. The GOAT mode produced the same startup counts
with its separate flag mask. This checks that the native mode can start and
that first-turn draw is active; it does **not** test 2010 card effects, Synchro
Summoning, legal actions, or a complete Edison duel. The MR1 probe refuses
gameplay responses and player observations to prevent accidental use as an
Edison environment. Reproduce it after [native setup](native_setup.md):

```sh
PYTHONPATH=src:. .venv/bin/python scripts/probe_native.py --mode mr1_startup --seed 42
GOAT_AI_NATIVE_ROOT=.cache/goat-ai PYTHONPATH=src:. .venv/bin/pytest -q tests/test_mr1_startup.py
```

## Validation gates before an Edison duel can be claimed

1. Establish a dated card-pool ID set through *Duelist Pack: Kaiba*, including
   TCG release eligibility and alias variants. Apply the transcribed copy caps
   to that pool, with shared limits across Main, Extra, and Side Deck.
2. Add an explicit Edison profile and deck validator that accepts Fusion and
   Synchro Extra Deck monsters under the historical deck-size rules.
3. Source and test 2010 first-turn draw, Ignition priority, Synchro Summoning,
   chain timing, field spells, and representative pre-errata card effects.
   [Edison Format's rules-differences guide](https://www.edisonformat.com/edison-rule-differences.html)
   is a useful community index; primary contemporary rulebooks and rulings
   should settle individual cases.
4. Audit player-visible observations and legal actions in Edison fixtures, then
   complete seeded duels and replay verification before benchmarking throughput.

No Edison simulator, deck-legality claim, or Edison training data is available
yet. Keep GOAT and Edison trajectory ruleset versions distinct.
