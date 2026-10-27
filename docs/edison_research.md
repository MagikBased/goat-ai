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

### Independent date-filtered candidate comparison (27 October 2026)

The [YGOPRODeck API guide](https://ygoprodeck.com/api-guide.php) documents a
TCG release-date filter. Its `format=tcg&enddate=2010-04-20&dateregion=tcg`
response supplies an independent *candidate*, using the date on [Konami's
*Duelist Pack: Kaiba* page](https://www.yugioh-card.com/en/products/past_products/dp_kaiba/).
The response is neither an official tournament-legality list nor a historical
rulings source. Both external inputs stay in ignored local cache; the response
had SHA-256 `962293dea8bfcd25ead0712d51b52515ac30efa28b2b6fb40f8c1dcc80d87482`.

`scripts/compare_edison_pool_candidates.py` compares the two candidate ID
sets, resolves alternate-print aliases through the pinned database, checks
the March 2010 Forbidden list, and writes a machine-readable disagreement
report. The cached comparison found 3,702 canonical IDs in the date-filtered
response and 3,624 in the community CSV, with 3,622 shared. Of 80 API-only
canonical IDs, 43 are Forbidden, two are tokens, one lacks pinned metadata,
and **34 still need individual release and eligibility checks**. The
missing-metadata ID `149694341` is an API "???" placeholder rather than an
identified card. Two community-only canonical
IDs are Exodius (`13893596`) and Genesis Dragon (`31038159`); [Konami's
Exodius card record](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=7392&ope=2)
and [Genesis Dragon card record](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=7978&ope=2&request_locale=en)
show older promotional printings. This illustrates that the API date filter
can omit a historically printed card. Conversely, the date filter can include
cards without establishing their tournament eligibility: the community
[Duel Terminal 1 analysis](https://www.edisonformat.com/home/why-arent-they-legal-duel-terminal-1)
raises a period distribution-policy question that still needs primary-source
verification for individual cards. The pinned database also lacks metadata
for ten raw API IDs and nine raw community IDs. No complete Edison whitelist
has been selected.

The ignored report is
`.cache/goat-ai/edison_pool_candidate_comparison_20261027.json` (SHA-256
`6fe8b46bcc46d873896be9916168f13f2288c9844542575d4d7b56a57efbf490`).
Reproduce it with locally cached sources:

```sh
mkdir -p .cache/goat-ai
curl --fail --location --silent --show-error \
  'https://db.ygoprodeck.com/api/v7/cardinfo.php?format=tcg&enddate=2010-04-20&dateregion=tcg' \
  -o .cache/goat-ai/ygoprodeck_tcg_through_2010_04_20.json
PYTHONPATH=src:. .venv/bin/python scripts/compare_edison_pool_candidates.py \
  .cache/goat-ai/ygoprodeck_tcg_through_2010_04_20.json \
  .cache/goat-ai/edison_community_cardpool.csv \
  .cache/goat-ai/database/cards.cdb \
  configs/historical/edison_2010_03_01_advanced_limits.tsv \
  --output .cache/goat-ai/edison_pool_candidate_comparison_20261027.json
```

The API may change after this cached comparison. Recheck all source hashes
before treating reproduced counts as the same evidence.

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

### Cross-controller trigger-order boundary

The [contemporary official rulebook, page 43](https://www.edisonformat.com/uploads/1/3/4/1/134149181/yugioh5dsofficialrulebook.pdf)
says simultaneous Spell Speed 1 effects enter a chain with the turn player's
effects first, followed by the opponent's. The community
[Time Wizard Edison ruling summary](https://timewizardrulings.com/) applies
that order specifically to Soul Exchange Tributing an opponent's Sangan for
Caius: Caius Link 1, opposing Sangan Link 2. The [GOAT source-backed
example](goat_rules.md) instead places Sangan before its
Monarch. These sources establish a concrete format-specific regression target;
the rulebook's general wording alone does not adjudicate every different-time
trigger case.

The `mr1-synchro-protocol` allowlist now includes Soul Exchange, the pinned
official Sangan, and Caius for a narrow native test. On seed 15, the unmodified
MR1 mode produces Caius Link 1 and opponent Sangan Link 2; the complete
1,334-decision duel replay-verifies and passes the player-visibility audit.
The corresponding GOAT-only patched fixture still expects Sangan Link 1 and
Thestalos Link 2. This confirms separation of this specific chain order, not
historical correctness of all 2010 effects, the current Sangan script, or
the complete Edison card pool.

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

The separate `Mr1VanillaEngine` now runs **complete Normal Monster duels**
under the same unmodified MR1 mode, using the common observation, action,
trajectory, replay-verification, and visibility-audit boundaries. Its ruleset
label is `mr1-vanilla-protocol`, separate from GOAT and Edison. It accepts only
40–60 pinned-database Normal Monsters in the Main Deck, with at most three
canonical copies and empty Extra/Side Decks. No card-specific scripts or GOAT
metadata overrides are loaded. The seed-42 fixture finished in 1,368 decisions with
winner seat 1; its complete trajectory replay-verified and passed the
player-visibility audit. An opening-decision differential also produced equal
observations and legal actions when only the hidden opponent Deck changed.
Run the example after native setup:

```sh
PYTHONPATH=src:. .venv/bin/python examples/play_mr1_vanilla.py \
  --seed 42 --trajectory replays/mr1_vanilla_42.json
GOAT_AI_NATIVE_ROOT=.cache/goat-ai PYTHONPATH=src:. .venv/bin/pytest -q \
  tests/test_mr1_startup.py tests/test_mr1_vanilla_duel.py
```

This establishes a second native mode's complete-duel protocol only. It does
not apply the March 2010 restriction list or release cutoff and does not test
effect cards, Synchro Summoning, 2010 rulings, or Edison deck legality. The
`mr1_startup` mode remains read-only and refuses gameplay responses.

## First Synchro protocol fixture

[Konami's 5D's Starter Deck 2008 catalog](https://www.db.yugioh-card.com/yugiohdb/card_search.action?ope=1&pid=13306000&request_locale=en&rp=99999)
lists Junk Synchron and Junk Warrior; the [official Junk Warrior card record](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=7696&ope=2&request_locale=en)
dates its first TCG printing to 5 August 2008 and specifies Junk Synchron
plus non-Tuner material. The separate `Mr1SynchroProbeEngine` admits only
the old vanilla fixture cards, Bokoichi, this named pair, and the separately
tested Black Rose Dragon and Stardust Dragon/Mirror Force cases below. It checks Main,
Extra, and copy limits using the March 2010 restriction table, but its tiny
eligible-ID set is a **probe subset**, not the full Edison release pool.

In a seeded native duel, one player Sets Level 2 Bokoichi, the opponent
destroys it by battle, and Junk Synchron later revives it. The engine offers
Level 5 Junk Warrior from the Extra Deck, accepts Junk Synchron and Bokoichi
as materials, and moves both to the Graveyard. The duel then terminates after
1,439 decisions. The complete trajectory replay-verifies and passes the
player-visibility audit. MR1 uses unmodified upstream `utility.lua` and the
pinned official scripts for the two named effect cards. Reproduce the
fixture and open the resulting trajectory in the existing replay viewer:

```sh
PYTHONPATH=src:. .venv/bin/python scripts/record_mr1_synchro_probe.py \
  --output replays/mr1_synchro_seed3.json
PYTHONPATH=src:. .venv/bin/python scripts/render_replay.py \
  replays/mr1_synchro_seed3.json --reviewer-reveal
GOAT_AI_NATIVE_ROOT=.cache/goat-ai PYTHONPATH=src:. .venv/bin/pytest -q \
  tests/test_mr1_synchro_probe.py
```

Junk Synchron's effect details, historical priority, and broader Synchro
timing have **not** been compared against 2010 source rulings.
This fixture proves the native decision protocol can represent one Synchro
line; it does not establish an Edison simulator or justify Edison training.
An additional seed-18 fixture leaves a second face-up Bokoichi (500 ATK,
Level 2) on the field after Junk Synchron and a revived Bokoichi become
Junk Warrior's materials. The native Warrior appears at 2300 ATK, then its
trigger resolves to 2800; the original seed-3 line has no remaining Level 2
monster and stays at 2300. The 1,202-decision seed-18 duel replay-verifies and
passes the visibility audit. A second, 1,592-decision seed-100 fixture leaves
only an **opposing** face-up Bokoichi after the Synchro Summon. Junk Warrior
stays at 2300; that complete duel also replay-verifies and passes the
visibility audit. These two branches distinguish whose Level 2 monsters the
native script counts.

The physical [first 2008 English printing (5DS1-EN041)](https://cdn.nubently.com.mx/2023/01/5DS1-EN041-510x680.jpg)
uses "on the field," while a photographed [Duelist Pack - Yusei printing
(DP08-EN012)](https://www.deckboosters.co.uk/cdn/shop/products/DP08-EN012.jpg?v=1671126847)
uses "you control." [Konami dates that reprint to 24 February 2009](https://www.yugioh-card.com/en/products/past_products/dp_yusei/),
before Edison, and its [current official card record](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=7696&ope=2&request_locale=en)
matches the later wording. The two photographed cards are primary printed-text
artifacts hosted by sellers; their images are linked, not redistributed here.
This validates the specific printed-text distinction and native outcome under
the 2009 wording. It does **not** establish every 2010 Junk Warrior ruling or
prove the general historical errata policy. Reproduce both branches with:

```sh
PYTHONPATH=src:. .venv/bin/python scripts/record_mr1_synchro_probe.py \
  --attack-probe --output replays/mr1_junk_warrior_atk_seed18.json
PYTHONPATH=src:. .venv/bin/python scripts/record_mr1_synchro_probe.py \
  --opposing-level-two --output replays/mr1_junk_warrior_opposing_level2_seed100.json
GOAT_AI_NATIVE_ROOT=.cache/goat-ai PYTHONPATH=src:. .venv/bin/pytest -q \
  tests/test_mr1_synchro_probe.py
```
The replay viewer now chooses the matching MR1 protocol engine to verify the
entire trajectory before exporting hidden reviewer cards. It rejects unknown
rulesets. Reviewer reveals stay in the generated HTML and SHA-bound sidecar,
outside the player-visible training trajectory.

## Black Rose Dragon optional trigger

[Konami's Black Rose Dragon card record](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=7898&ope=2&request_locale=en)
dates its first TCG printing to 3 November 2008 and gives a Level 7 Synchro
Summon an optional effect that destroys all cards on the field. The
[March 2010 TCG list](https://www.yugioh-card.com/en/downloads/alt_format/2010-03-01.pdf)
limits Black Rose Dragon to one copy. The MR1 probe now allows that one Extra
Deck card alongside its earlier Junk Warrior case, while still rejecting
unsourced Synchros and applying the restriction table.

Paired seed-3 native fixtures Normal Summon Level 4 Kabazauls, keep an opposing
Gemini Elf on the field, then Normal Summon Level 3 Junk Synchron. Both are
offered as material for Black Rose Dragon. At decision 36 the controller can
accept or decline its optional trigger. Accepting moves Black Rose Dragon and
Gemini Elf to their owners' Graveyards; declining leaves both face-up on the
field. The respective duels terminate in 1,258 and 1,376 decisions. Their
complete trajectories replay-verify and pass the player-visibility audit.
The positive and negative branches use the pinned official Black Rose script
and unmodified upstream MR1 `utility.lua`. Reproduce them after native setup:

```sh
PYTHONPATH=src:. .venv/bin/python scripts/record_mr1_black_rose_probe.py \
  --output replays/mr1_black_rose_yes_seed3.json
PYTHONPATH=src:. .venv/bin/python scripts/record_mr1_black_rose_probe.py \
  --decline --output replays/mr1_black_rose_no_seed3.json
GOAT_AI_NATIVE_ROOT=.cache/goat-ai PYTHONPATH=src:. .venv/bin/pytest -q \
  tests/test_mr1_synchro_probe.py
```

This adds a distinct Synchro trigger and choice to the protocol evidence. It
does not independently validate every 2010 Black Rose ruling, the script's
other effect, the full Edison card pool, or an Edison rules profile.

## Stardust Dragon versus Mirror Force

The [official Stardust Dragon card record](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=7734&ope=2&request_locale=en)
identifies it as a Level 8 Synchro requiring one Tuner and at least one
non-Tuner, and describes its response to an effect that would destroy cards on
the field and its later End Phase return. Its listed first TCG release was in
2008. The [official Mirror Force record](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=4887&ope=2&request_locale=en)
describes destruction of the attacker's Attack Position monsters when an
opponent attacks. These records support the narrow interaction selected for
the fixture; modern card text alone does not settle every March 2010 ruling.

In paired seed-536 native fixtures, a Level 4 Kabazauls is Tributed for Level
5 Curse of Dragon. Level 3 Junk Synchron and Curse of Dragon then become the
materials for Stardust Dragon. The opponent has Set Mirror Force. Stardust
attacks directly, Mirror Force activates, and Stardust's controller can either
chain its effect or pass. Chaining moves Stardust to the Graveyard, negates and
destroys Mirror Force, and offers Stardust's return at End Phase. Passing lets
Mirror Force destroy Stardust without an End Phase return. The two duels
terminate after 1,413 and 1,465 decisions respectively. Both complete
trajectories replay-verify against pinned native assets and pass the
player-visibility audit; Mirror Force's identity remains hidden before it is
activated. The fixture uses pinned official card scripts and the narrow MR1
protocol allowlist. Reproduce after native setup:

```sh
PYTHONPATH=src:. .venv/bin/python scripts/record_mr1_stardust_probe.py \
  --output replays/mr1_stardust_yes_seed536.json
PYTHONPATH=src:. .venv/bin/python scripts/record_mr1_stardust_probe.py \
  --decline --output replays/mr1_stardust_no_seed536.json
GOAT_AI_NATIVE_ROOT=.cache/goat-ai PYTHONPATH=src:. .venv/bin/pytest -q \
  tests/test_mr1_synchro_probe.py
```

This establishes one destruction-response protocol path. It does not validate
all historical Stardust timings, battle rulings, Synchro materials, or the
complete Edison release pool and rules profile.

## Stardust Dragon versus Black Rose Dragon

The official [Black Rose Dragon record](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=7898&ope=2&request_locale=en)
describes its optional Synchro Summon effect that destroys all cards on the
field. The official [Stardust Dragon record](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=7734&ope=2&request_locale=en)
describes Tributing itself to negate a card or effect that would destroy field
cards, and its possible End Phase return. These current primary card records
motivate a narrow MR1 interaction test; they do not independently establish
every 2010 ruling or printed-text detail.

In paired seed-955 fixtures, player 0 Synchro Summons Stardust from Junk
Synchron and Curse of Dragon. Player 1 retains a second Normal Monster,
then Synchro Summons Black Rose from Junk Synchron and Gemini Elf and chooses
its wipe. At decision 77, the Black Rose effect is the public Chain Link 1 and
Stardust's controller can either chain Stardust or pass. Chaining Tributes
Stardust, negates and destroys Black Rose, preserves the extra Normal Monster,
and returns Stardust at turn 6 End Phase. Passing lets the wipe destroy all
three field monsters, with no Stardust return. The terminal duels contained
**1,621** and **1,230** decisions respectively; both serialized, replay-verified
against the pinned native core, and passed the player-visibility audit. The
fixture exercises two interacting Synchro effects and their chain/return
windows, not an Edison deck or full historical rules profile.

```sh
PYTHONPATH=src:. .venv/bin/python scripts/record_mr1_stardust_black_rose_probe.py \
  --output replays/mr1_stardust_black_rose_chain_seed955.json
PYTHONPATH=src:. .venv/bin/python scripts/record_mr1_stardust_black_rose_probe.py \
  --decline --output replays/mr1_stardust_black_rose_pass_seed955.json
GOAT_AI_NATIVE_ROOT=.cache/goat-ai PYTHONPATH=src:. .venv/bin/pytest -q \
  tests/test_mr1_synchro_probe.py
```

## Summon priority and Torrential Tribute

The [contemporary 5D's official rulebook](https://www.edisonformat.com/uploads/1/3/4/1/134149181/yugioh5dsofficialrulebook.pdf)
states that the turn player starts with priority to activate a card or effect,
then passes priority after the activation. The official card records identify
[Exiled Force's self-Tribute destruction effect](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=5323&ope=2&request_locale=en)
and [Torrential Tribute's Summon response](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=5114&ope=2&request_locale=en).
The Exiled Force record lists a 2009 printing and both cards predate the
Edison cutoff. The March 2010 restriction table is applied to the MR1 decks.

The existing seed-52 GOAT fixture now also runs under the pinned MR1 flag set.
After Exiled Force is Normal Summoned, its controller can activate its effect
before the opponent takes a response. Exiled Force Tributes itself as a cost;
the opponent is then offered Torrential Tribute as a chain response. In the
chain branch, Torrential destroys the other monsters before Exiled Force's
targeted effect resolves. In the pass branch, the targeted opposing monster
is destroyed while Torrential stays Set. Both branches complete, replay-verify,
and pass the player-visibility audit under MR1 as well as GOAT. This confirms
one priority interaction in the native MR1 protocol. It does not certify all
2010 summon windows or card-specific rulings. Reproduce with:

```sh
GOAT_AI_NATIVE_ROOT=.cache/goat-ai PYTHONPATH=src:. .venv/bin/pytest -q \
  tests/test_historical_exiled_torrential.py
```

## Same-time trigger ordering

The [2009 official rulebook's simultaneous-effects section](https://www.edisonformat.com/uploads/1/3/4/1/134149181/yugioh5dsofficialrulebook.pdf)
states that the turn player builds a chain from their own simultaneous
Spell Speed 1 effects and chooses their order when they control more than one.
The existing GOAT Desert Sunlight fixture now has a separate MR1 branch using
ordinary Dekoichi and Gravekeeper's Spy IDs and pinned official scripts. Desert
Sunlight flips both Set monsters at once. In either branch the controller is
offered both mandatory Flip Effects as Chain Link 1, selects one, and the other
becomes Chain Link 2. Both selected orders draw with Dekoichi and recruit with
Spy, reach terminal, replay-verify, and pass the visibility audit. The MR1
branch uses unmodified upstream utility and ordinary card scripts; the GOAT
branch retains its separate historically patched scripts.

This verifies a concrete same-controller trigger choice, including the issue
of owner-selected chain order. Cross-controller triggers, optional effects,
and historical card-text changes still need independent Edison checks. Run:

```sh
GOAT_AI_NATIVE_ROOT=.cache/goat-ai PYTHONPATH=src:. .venv/bin/pytest -q \
  tests/test_historical_same_time_trigger_choice.py
```

## Goyo Guardian historical material correction

The [March 2010 official list](https://www.yugioh-card.com/en/downloads/alt_format/2010-03-01.pdf)
limits Goyo Guardian to one. Its [official card record](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=7736&ope=2&request_locale=en)
dates its TCG debut to September 2008, but displays the later requirement
for an EARTH Tuner. The [Edison historical errata record](https://www.edisonformat.com/rulings/relevant-errata)
preserves the period material text permitting any Tuner; a [September 2008
card review](https://www.pojo.com/yu-gi-oh/COTD/2008/Sept/25.shtml) independently
prints that earlier material line. This is a concrete example of why a modern
card script cannot be used unchanged for historical play.

The pinned official `c7391448.lua` has SHA-256
`b1f8f68c428302b537a1bf4b660ef33ae800afd4a1716cd962f3908b2f24302b`
and requires an EARTH Tuner. In `mr1-synchro-protocol` only, the script reader
checks that exact hash and replaces the material predicate in memory; the
resulting loaded script has SHA-256
`4c2dc55206a96699a270b1ad1ef74ae2760795b9e402026b9b22869704769f27`.
The upstream file remains untouched, and replay manifests bind the loaded
script hash. The MR1 probe applies the official one-copy restriction.

In a seed-5 native fixture, DARK Junk Synchron and EARTH Giant Soldier of Stone
become the Level 6 materials. Goyo destroys the opponent's Dark Blade in
battle. Accepting its optional effect brings Dark Blade to the controller's
field face-up in Defense Position; declining leaves it in its owner's
Graveyard. Both complete duels replay-verify and pass the player-visibility
audit, with 1,281 and 1,389 decisions respectively. This validates the
material and battle-trigger paths in this narrow probe, not a general Edison
engine or all Goyo rulings. Reproduce after native setup:

```sh
PYTHONPATH=src:. .venv/bin/python scripts/record_mr1_goyo_probe.py \
  --output replays/mr1_goyo_yes_seed5.json
PYTHONPATH=src:. .venv/bin/python scripts/record_mr1_goyo_probe.py \
  --decline --output replays/mr1_goyo_no_seed5.json
GOAT_AI_NATIVE_ROOT=.cache/goat-ai PYTHONPATH=src:. .venv/bin/pytest -q \
  tests/test_mr1_synchro_probe.py -k goyo
```

## One-active-Field-Spell MR1 check

The [2009 official rulebook, pages 8 and 24](https://www.edisonformat.com/uploads/1/3/4/1/134149181/yugioh5dsofficialrulebook.pdf)
states that only one Field Spell may be active across both players and that
activating a new one destroys the previous active Field Spell. [Yami](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=4341&ope=2&request_locale=en)
and [Umi](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=4340&ope=2&request_locale=en)
both predate the Edison cutoff. The narrow `mr1-synchro-protocol` allowlist
now includes their pinned official IDs and scripts. In a seed-52 fixture,
player 0 activates Yami and player 1 later activates Umi; Umi alone remains
in the Field Spell zone and Yami is in its owner's Graveyard. The duel then
reaches terminal, serializes, replay-verifies, and passes the visibility
audit. This confirms the pinned MR1 mode's field-replacement path for these
two cards. It does not certify every 2010 Field Spell interaction or an Edison
environment.

```sh
GOAT_AI_NATIVE_ROOT=.cache/goat-ai PYTHONPATH=src:. .venv/bin/pytest -q \
  tests/test_mr1_field_spells.py
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
   MR1 vanilla, Junk Warrior, Black Rose Dragon, and Stardust Dragon fixtures
   check protocol paths only.

No Edison simulator, deck-legality claim, or Edison training data is available
yet. Keep GOAT and Edison trajectory ruleset versions distinct.
