# Edison format feasibility and historical inputs

Edison is a future, separate rules profile. The current GOAT adapter must reject
an Edison request; a March 2010 list cannot make its 2005 card scripts and rules
historically correct for 2010.

## Regional scope of the historical target

The intended historical Edison profile is **North American TCG play in April
2010**. This is a project scope decision; it does not turn a general TCG card
database into a North American tournament whitelist. The [North America Time
Travel FAQ](https://www.yugioh-card.com/en/play/alternate_format_tournaments/time-travel/)
uses April 20, 2010 and *Duelist Pack: Kaiba* as one period example, but that
modern event format uses current card text and mechanics. The historical
profile pursued here remains separate.

[Konami's February 2010 European tournament policy](https://www.etcg.de/uploads/pdf/KDE_YuGiOh_Policy.pdf)
says set and promotional-card legality depends on the territory of official
release, including magazine promos. This is contemporary policy evidence for
the regional distinction, although its governing organization and events are
European. The [current Konami Europe card-legality page](https://www.yugioh-card.com/eu/play/card-legality/)
still lists Yu-Jo Friendship (`81332143`, `JUMP-EN007`) as unavailable for
European tournament play. Its [official card record](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=5754&ope=2)
shows a 2006 promotional printing. A bare first-print date cannot adjudicate
this card across TCG territories. The North American release evidence and
provisional decision are recorded below; Europe remains a separate case.

Another API-only candidate, Restructer Revolution (`99518961`), has a
[documented 2005 English TCG printing](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=4871&ope=2&request_locale=en)
in the [ordinary *Dark Beginning 2* booster](https://www.db.yugioh-card.com/yugiohdb/card_search.action?ope=1&pid=11104003&request_locale=en&rp=99999)
and no March 2010 restriction in the official list. We include it in the
partial historical release pool; this is an inference from the dated booster
record, not a certification of every North American event edge case or the
complete Edison whitelist. These examples make regional
provenance a required release-pool gate, alongside first-print date, set
distribution, copy limits, and historical rulings.

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
MR1 Synchro probe trajectories now fingerprint that exact TSV as
`historical/edison_2010_03_01_advanced_limits.tsv` alongside the core,
database, and loaded scripts. The replay verifier rejects a different table
digest, so a recorded probe cannot silently be replayed under changed copy
limits. This records one deck-admission input; it does not expand the partial
release pool or certify Edison legality.
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
report. Its `jurisdiction_status` explicitly remains
`not_established_by_candidate_sources`. The cached comparison found 3,702
canonical IDs in the date-filtered response and 3,624 in the community CSV,
with 3,622 shared. Of 80 API-only
canonical IDs, 43 are Forbidden, two are tokens, one lacks pinned metadata,
and **34 still need individual release and eligibility checks**. The
missing-metadata ID `149694341` is an API "???" placeholder rather than an
identified card. Of the 34 named disagreements, **28 have a Duel Terminal 1
printing** in the API response. That report category means only that the card
appears in that product; it does not assert the product was its first printing
or decide legality. Two community-only canonical
IDs are Exodius (`13893596`) and Genesis Dragon (`31038159`); [Konami's
Exodius card record](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=7392&ope=2)
and [Genesis Dragon card record](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=7978&ope=2&request_locale=en)
show older promotional printings. This illustrates that the API date filter
can omit a historically printed card. Conversely, the date filter can include
cards without establishing their tournament eligibility: the community
[Duel Terminal 1 analysis](https://www.edisonformat.com/home/why-arent-they-legal-duel-terminal-1)
describes the distribution issue, and the archived Konami notice below
establishes the period policy. Each card still needs a release check. The
pinned database also lacks metadata
for ten raw API IDs and nine raw community IDs. No complete Edison whitelist
has been selected.

[Konami's archived 19 March 2010 Duel Terminal legality notice](https://web.archive.org/web/20231002070814/https://yugiohblog.konami.com/articles/?p=1622)
supplies the primary policy source: new Duel Terminal cards did not become
tournament legal merely by appearing in the machine; they required release
through another product. The notice distinguishes reprints of already legal
cards, names X-Saber Wayne's future Starter Deck release, and says the DT01
cards reprinted in *The Shining Darkness* become legal when that set releases.
The live Konami article currently redirects, so the linked archived capture
is the reproducible source. The official card records show three concrete
examples: [Genex
Undine](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=7808&ope=2&request_locale=en)
first appears in Duel Terminal 1 on 29 January 2010 and then in *The Shining
Darkness* on 11 May; [X-Saber Wayne](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=7835&ope=2&request_locale=en)
has its next listed print in the 1 June 2010 Starter Deck; and [Mist Valley
Watcher](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=7815&ope=2&request_locale=en)
has its next listed print in *Gold Series 3* on 23 June. All three dates are
after the April 20 cutoff. These three are excluded under the contemporary
North American tournament policy.

The [28-card DT01 exclusion evidence table](../configs/historical/edison_dt01_new_card_exclusions_2010_04_20.tsv)
records every identified API-only card with a DT01 printing, its official
Konami card-page link, that printing's date and code, and its earliest listed
non-DT01 print. All 28 exact-name card pages loaded successfully in the
English TCG database; every earliest listed non-DT01 date is **later than
20 April 2010** (the earliest is 11 May). Under Konami's March 2010 notice,
these 28 newly introduced cards are excluded from the historical North
American Edison pool. The table's SHA-256 is
`ef2b63abe3fcf911e78065202f68b98dc88a6566cbfb96066d7e3ade980d0499`.
The parsed official-page audit remains in ignored local cache at
`.cache/goat-ai/edison_dt1_official_cards_20261027.json` (SHA-256
`b8400272621ddcf9f3340f92cb3f991fef992ef3990a23a2f957a0ee1f0e1fbd`).
The raw HTML is not redistributed. This is a bounded source check of 28
cards, not proof that the entire Edison release pool is complete or that a
current card record cannot omit an old regional printing. The other six
named API-only discrepancies and the two community-only promotional cards
need separate adjudication; the Genesis Dragon decision below resolves one
of the latter.

The [six-card non-DT01 discrepancy ledger](../configs/historical/edison_non_dt01_candidate_discrepancies_2010_04_20.tsv)
now records independent North American evidence and remaining questions.
[Konami's *Gold Series 3* page](https://www.yugioh-card.com/en/products/past_products/gs2010/)
calls it the first product to offer Vice Dragon and gives 23 June 2010 as its
tournament-legal date, after the cutoff. The current [official card record](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=7991&ope=2&request_locale=en)
also starts with that print. Restructer Revolution has a
[dated 2005 English booster printing](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=4871&ope=2&request_locale=en)
in [*Dark Beginning 2*](https://www.db.yugioh-card.com/yugiohdb/card_search.action?ope=1&pid=11104003&request_locale=en&rp=99999),
which supports including it in the partial historical release pool. This is
an inference from the booster record and the [March 2010 restriction list](https://www.yugioh-card.com/en/downloads/alt_format/2010-03-01.pdf),
not a period North American event ruling. The
[2010 European Konami policy](https://www.etcg.de/uploads/pdf/KDE_YuGiOh_Policy.pdf)
allows some video-game promos from games released in a different territory.
The [English TCG game-bundle print](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=7983&ope=2&request_locale=en)
for Darkness Destroyer is dated November 2008, but
[Konami says](https://www.yugioh-card.com/en/products/past_products/legendary_coll2/)
its first North American release was October 2011. The archived North American
policy below requires a video-game promo's game to go on sale *within that
continent*. We therefore exclude the card at the April 2010 North American
cutoff. This applies policy wording documented in November 2010 to the earlier
cutoff, so the historical interpretation is an inference; a pre-cutoff North
American event ruling would strengthen it. The
[Wicked Dreadroot](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=6405&ope=2&request_locale=en)
and [Wicked Eraser](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=7092&ope=2&request_locale=en)
have older promotional records, but their exact period North American legal
dates remain unproved. The [February 2010 Konami tournament policy](https://www.etcg.de/uploads/pdf/KDE_YuGiOh_Policy.pdf)
specifically says a SHONEN JUMP magazine promo becomes legal on the magazine's
official **newsstand date**, not when an early subscriber receives it. That
policy is issued by Konami's European office and warns that legality dates
vary by territory. Konami's card records identify Dreadroot with the January
2008 magazine promotion and Eraser with September 2007, but list neither
newsstand day. Since both issue months end more than two years before the
cutoff, the unknown day cannot cross the cutoff if these are North American
magazine releases. The ledger now includes both **provisionally** on that
bounded-date inference. The [period Konami Mexico FAQ](https://web.archive.org/web/20101101213813id_/http://www.yugioh-card.com/en/events/ycs/YCS-MX_FAQ.html)
distinguishes SHONEN JUMP promos unavailable in Latin America; the North
American release conclusion remains an inference, not a located April 2010
event ruling. A period North American card-legality appendix or dated event
ruling would strengthen it. Thus 30 of the 34 named API-only discrepancies
have a source-backed exclusion, and four have provisional pre-cutoff inclusions.
One community-only
promotion remains open, as does the wider release pool.

A later [official Konami Central America WCQ FAQ](https://www.yugioh-card.com/en/events-item/2025-ca-wcq/)
lists Yu-Jo Friendship among promos unavailable in Latin America and says
SHONEN JUMP subscription promos were available to US or Canadian residents,
with legal dates applying to sanctioned North American events. The FAQ calls
it `JUMP-EN007`, while the [official card record](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=5754&ope=2&request_locale=en)
calls its 1 August 2006 graphic-novel printing `JMP-EN007`; the identifier
disagrees. [VIZ's publisher page](https://www.viz.com/manga-books/manga/yu-gi-oh-duelist-volume-16-0/product/1009)
dates the paperback *Yu-Gi-Oh!: Duelist*, volume 16, to 1 August 2006,
states that an exclusive trading card was included, and lists US and Canadian
retailers. The official card record identifies that book's card as Yu-Jo
Friendship. The [February 2010 KDE tournament policy](https://www.etcg.de/uploads/pdf/KDE_YuGiOh_Policy.pdf)
says a promotional card becomes legal on official release in territories
where it was released. Combining those primary records supports a
**provisional North American inclusion** by the April 2010 cutoff. The
territory conclusion is an inference from VIZ's North American retailer
listing, not a located April 2010 event card-legality ruling. The 2025 FAQ
alone does not establish the historical date; the `JMP`/`JUMP` prefix
discrepancy remains recorded.

An [archived official card-legality page captured 6 November
2010](https://web.archive.org/web/20101106023610id_/http://www.yugioh-card.com/en/gameplay/cardlegality.html)
identifies itself as updated 4 November 2010. It lists SHONEN JUMP promos
through `JUMP-EN044` as legal, subject to a regional footnote excluding them
outside North America unless reprinted. This is later corroboration for the
older Wicked promos (`JUMP-EN016` and `JUMP-EN018`), but does not by itself
establish their April 2010 status. Its separate video-game footnote says legality begins on the
game's sale date *within that continent*, which differs from the February
2010 European policy's allowance for certain games not scheduled locally.
Together with Konami's 2011 first-North-American-release statement, this
supports the provisional exclusion recorded above. The archived HTML SHA-256 is
`5889e081d7cbd794af64e94c514179cfab987ca03cb9b82059d78c3fd3f896bb`;
the capture was read without vendoring it.
The updated six-card ledger SHA-256 is
`77d35bb6c7556111042d3416c077f9bbb38b61019a609ad59fce441708eb2406`.

The ignored report is
`.cache/goat-ai/edison_pool_candidate_comparison_20261027.json` (SHA-256
`cbfbb64c1dae363a67c97eb61762139e27594646b2f366d6d55e2963b59e8429`).
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

`scripts/adjudicate_edison_pool_disagreements.py` now checks that the 28-card
DT01 exclusion table and six-card non-DT01 ledger cover the **exact** 34
API-only named differences in the candidate comparison, and that the
[two-card community-only ledger](../configs/historical/edison_community_only_candidate_discrepancies_2010_04_20.tsv)
covers the opposite difference, with no duplicate or conflicting IDs. It
rejects a DT01 exclusion if its first listed ordinary
printing precedes the cutoff. Against the cached comparison above, it reports
30 excluded IDs, four provisionally included API-only IDs (Restructer
Revolution, Yu-Jo Friendship, and both Wicked magazine promos), no pending
API-only IDs, one included community-only
ID (Genesis Dragon), and one pending community-only subscription promotion. The
magazine assessment accepts a `YYYY-MM` issue only when its **last possible
day** precedes the cutoff and the recorded territory is North America; this
does not certify the inferred territory. The report also reconciles the
candidate counts and explicitly records that the **3,622 shared canonical
IDs have not received individual independent release checks**. Resolving the
two remaining one-sided candidates would still not make a complete pool. Its
`complete_release_pool` field is always false: neither candidate source nor
this reconciliation establishes every eligible North American card. The
ignored local output is
`.cache/goat-ai/edison_partial_adjudication_20261030.json` (SHA-256
`50e6a90e8262d10b9db7faa1dc940b857361dd565c08e00a9f757838816f0084`).

```sh
PYTHONPATH=src:. .venv/bin/python scripts/adjudicate_edison_pool_disagreements.py \
  .cache/goat-ai/edison_pool_candidate_comparison_20261027.json \
  configs/historical/edison_dt01_new_card_exclusions_2010_04_20.tsv \
  configs/historical/edison_non_dt01_candidate_discrepancies_2010_04_20.tsv \
  configs/historical/edison_community_only_candidate_discrepancies_2010_04_20.tsv \
  --output .cache/goat-ai/edison_partial_adjudication_20261030.json
```

[Konami's Exodius record](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=7392&ope=2&request_locale=en)
lists `JUMP-EN025` as a May 2008 subscription promotion and its first listed
ordinary product as a November 2010 tin. [Konami's Genesis Dragon
record](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=7978&ope=2&request_locale=en)
lists `JUMP-EN034` as a March 2010 subscription promotion and its first
listed ordinary product as *Gold Series 4* in July 2011. Neither card page
gives a North American legal date. However, [Konami's 10 January 2010 Los
Angeles SHONEN JUMP Championship feature
match](https://yugiohblog.konami.com/2010/sjc/round-7-feature-match-richard-clarke-vs-matt-highline/)
records Richard Clarke using Genesis Dragon during sanctioned play. This
period North American event evidence supports including that card by the
20 April Edison cutoff, regardless of the later March date shown for the
subscription record. The discrepancy between the event use and the card
page's listed print month has not been explained, so the ledger records
the event rather than inferring a precise distribution date. Exodius
remains pending. The retrieved Konami article is in ignored local cache at
`.cache/goat-ai/edison_genesis_dragon_sjc_2010_01_10.html` (SHA-256
`ae1ac4205061fb2f7d23cffd213c2532a7f49a0c6e0cdaa5b952c7478bd7706b`);
the article HTML is not redistributed. The adjudicator requires an ISO event
date on or before the cutoff and the `north_america` region for any
sanctioned-play inclusion. These checks guard the structured evidence fields;
they do not independently authenticate the linked event report.

**Exodius subscription-promo follow-up (28 October 2026):** [Konami's card
database](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=7392&ope=2&request_locale=en)
confirms `JUMP-EN025` in the May 2008 subscription promotion, and [Konami's
2024 event FAQ](https://www.yugioh-card.com/en/events-item/2024-ycs-colombia/)
states that SHONEN JUMP subscription promotions were available to US/Canadian
residents and that tournament-legal dates applied to sanctioned North American
events. The latter is retrospective regional context, **not** evidence of the
rule or exact legal date on 20 April 2010. The [6 November 2010 archive of
Konami's card-legality page](https://web.archive.org/web/20101106023610id_/http://www.yugioh-card.com/en/gameplay/cardlegality.html)
lists JUMP promotions through `JUMP-EN044` as legal, but also postdates the
cutoff. A Wayback CDX check found that archive as the only successful 2010
capture of this page, so it cannot prove the April status. The candidate
remains pending until a period North American legality page, policy, or
sanctioned-play record establishes it. Its 2010 tin reprint is too late.

[Konami's later Turbo Pack 5 coverage](https://yugiohblog.konami.com/2011/ycs/turbo-pack-5-unveiled/)
states that SHONEN JUMP magazine promotions were distributed in the United
States and Canada, and that two such cards became tournament-legal in Europe
and Latin America only after their regional Turbo Pack release. This is
official evidence that promo distribution and legality were regional. It is
from 2011, concerns different cards, and supplies no April 2010 legal date
for Exodius; it therefore does not change the pending assessment.

A [Konami Mexico YCS FAQ archived on 1 November 2010](https://web.archive.org/web/20101101213813id_/http://www.yugioh-card.com/en/events/ycs/YCS-MX_FAQ.html)
explicitly excludes SHONEN JUMP magazine promotions from Latin American
tournament play unless the card was released another way there. It also gives
Latin American restrictions on cards from North American Duel Terminal sets.
This period official FAQ confirms that an event's territorial rules matter;
it does **not** independently certify whether Exodius, the Wicked promotions,
or those Duel Terminal cards were legal in North America by 20 April. The retrieved HTML is
kept only in ignored local cache at
`.cache/goat-ai/edison_ycs_mexico_faq_2010_11_01.html` (SHA-256
`47c251ea7fa5c2a8e42cf68d4097878ebfc3dcf01134c8c9f1408025e84bf807`).

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
Dark Strike Fighter is explicitly **Forbidden** on the
[March 2010 Advanced list](https://www.yugioh-card.com/en/downloads/alt_format/2010-03-01.pdf),
so its original effect is not a playable Edison regression priority even
though the pinned database contains the card.

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

## Battle Fader direct-attack timing

[Konami's *Absolute Powerforce* card catalog](https://www.db.yugioh-card.com/yugiohdb/card_search.action?ope=1&pid=11109000&request_locale=en&rp=99999)
dates Battle Fader's TCG release to 16 February 2010, before the Edison
cutoff. [Konami's set-specific ruling sheet](https://img.yugioh-card.com/ygo_cms/ygo/all/uploads/RulesABPF_1_1.pdf)
says its hand effect Special Summons it on an opponent's direct attack, ends
the Battle Phase, and leaves no Torrential Tribute activation window after
resolution because ending the Battle Phase is the last event.

Paired seed-100 MR1 duels give the defender Battle Fader in hand and a Set
Torrential, then have an opposing Normal Monster attack directly on turn 3.
Passing Fader takes battle damage and leaves it in hand. Activating Fader
Special Summons it, prevents damage, and moves play to Main Phase 2 without
offering Torrential or another attack. Torrential remains Set. The defender's
Set Trap identity is absent from the attacker's observation. Both complete
duels serialize, replay-verify, and pass the player-visibility audit on the
pinned official Battle Fader script. The positive branch continues to turn 5:
the original attacker battles Fader, which goes to the face-up banished zone
rather than its owner's Graveyard, as the same ruling sheet specifies.
Reproduce with:

```sh
GOAT_AI_NATIVE_ROOT=.cache/goat-ai PYTHONPATH=src:. .venv/bin/pytest -q \
  tests/test_mr1_battle_fader.py
```

Removal by other effects and other attack responses remain untested. This
fixture does not certify Edison rules or the full card pool.

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

## Bottomless Trap Hole after a Synchro Summon

The [official Bottomless Trap Hole card record](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=5400&ope=2&request_locale=en)
specifies the 1500-ATK Summon response and banishment after destruction;
the [official Junk Warrior record](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=7696&ope=2&request_locale=en)
identifies its Synchro materials and 2300 original ATK. The pinned
[March 2010 list](https://www.yugioh-card.com/en/downloads/alt_format/2010-03-01.pdf)
caps Bottomless at two copies, which the new 40-card probe deck respects.
This current card text and period restriction support the narrow interaction,
not every historical Bottomless ruling.

In paired seed-52 MR1 duels, player 0 Sets Bokoichi, then Flip Summons it
alongside Junk Synchron to Synchro Summon Junk Warrior; player 1 previously
Set Bottomless. At decision 36 the 2300-ATK Warrior is on the field and player
1 is offered Bottomless as a chain response. Chaining it banishes Warrior;
passing leaves Warrior on the field and Bottomless Set. Before the response,
player 0's observation shows an unidentified opposing Set Trap. Both full
duels terminate (1,267 and 1,238 decisions), serialize, replay-verify, and
pass the player-visibility audit. The pinned official Bottomless script is
loaded without a patch for this test; its loaded SHA-256 is
`86ac205586401acd978132edcdca85455c221dc2ca70fee18ff8895a2fdb88de`.
This validates one Synchro Summon response in the isolated MR1 probe, not
the complete Edison profile. Reproduce with:

```sh
PYTHONPATH=src:. .venv/bin/python scripts/record_mr1_bottomless_synchro_probe.py \
  --output replays/mr1_bottomless_synchro_seed52.json
PYTHONPATH=src:. .venv/bin/python scripts/record_mr1_bottomless_synchro_probe.py \
  --pass-bottomless --output replays/mr1_bottomless_pass_seed52.json
GOAT_AI_NATIVE_ROOT=.cache/goat-ai PYTHONPATH=src:. .venv/bin/pytest -q \
  tests/test_mr1_bottomless_synchro.py
```

### Book of Moon chained to the Synchro response

A [Konami November 2010 feature match](https://yugiohblog.konami.com/2010/ycs/10-11-atlanta/round-10-feature-match-brian-jones-vs-james-quick/)
records Book of Moon being chained to Bottomless Trap Hole to protect a
Summoned monster. That official event record postdates the April cutoff and
shows a Normal Summon, so it does not independently establish the precise
April rule or every Synchro interaction. The MR1 probe uses the pinned
unmodified official Book and Bottomless scripts to test this additional
response path after Junk Warrior's successful Synchro Summon.

In paired seed-52 duels, Book is Set before Junk Warrior is Summoned. Bottomless
is chosen at decision 40 in both branches. The Synchro controller is then
offered Book as a chain response. Chaining Book and selecting Junk Warrior
leaves Warrior face-down on the field and unbanished; passing Book banishes
Warrior and leaves Book Set. Before activation, the opposing player sees an
unidentified Set Spell/Trap. The two duels terminate after 1,638 and 1,404
decisions respectively; both serialize, replay-verify, and pass the
player-visibility audit. This verifies the native MR1 chain and information
boundary for these cards, not a complete Edison rules profile.

```sh
PYTHONPATH=src:. .venv/bin/python scripts/record_mr1_bottomless_synchro_probe.py \
  --chain-book --output replays/mr1_bottomless_book_seed52.json
PYTHONPATH=src:. .venv/bin/python scripts/record_mr1_bottomless_synchro_probe.py \
  --pass-book --output replays/mr1_bottomless_pass_book_seed52.json
GOAT_AI_NATIVE_ROOT=.cache/goat-ai PYTHONPATH=src:. .venv/bin/pytest -q \
  tests/test_mr1_bottomless_book_synchro.py
```

## Royal Oppression against a Synchro Summon

The [official March 2010 Advanced list](https://www.yugioh-card.com/en/downloads/alt_format/2010-03-01.pdf)
Semi-Limits Royal Oppression. A new MR1 probe admits two copies and loads its
pinned official script; this remains a deliberately narrow eligible-card set,
not an Edison whitelist. In paired seed-52 duels, player 1 Sets Oppression on
turn two and activates it during the following Draw Phase. Player 0 then Flip
Summons Bokoichi, Normal Summons Junk Synchron, and Synchro Summons Junk Warrior.
The face-up Oppression offers player 1 a response. Paying 800 LP negates the
Summon, sends Junk Warrior to the Graveyard, and leaves Oppression face-up;
passing leaves Junk Warrior on the field with both players at 8000 LP. Before
Oppression is activated, player 0 sees only an unidentified Set Spell/Trap.
Both branches finish complete duels, serialize, replay-verify, and pass the
player-visible trajectory audit. This checks the native MR1 response and
cost for one Synchro Summon; the script's April 2010 text and other
Oppression interactions still require independent historical validation.

```sh
GOAT_AI_NATIVE_ROOT=.cache/goat-ai PYTHONPATH=src:. .venv/bin/pytest -q \
  tests/test_mr1_royal_oppression_synchro.py
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

## Brionac's 2010 effect versus the pinned current script

[Konami's 2010 Hidden Arsenal rulings](https://img.yugioh-card.com/ygo_cms/ygo/all/uploads/100304-HA_SDWS_ST09_Rules.pdf)
give Brionac's original effect as discarding any number of cards to return the
same number of cards *from the field*, and identify the discard as a cost and
the chosen cards as targets. The current pinned `official/c50321796.lua`
instead limits the effect to once per turn and to opposing cards. A
[Konami-recorded 2011 match](https://yugiohblog.konami.com/2011/ycs/round-10-alex-its-aliiive-vansant-vs-ken-mccarthy-of-the-future/)
shows two separate Brionac activations in one turn, corroborating the
absence of a once-per-turn restriction before the later errata. The 2010
rulings PDF is currently unavailable at its live URL; the indexed excerpt
supplies the original wording, while the 2011 match is directly accessible.
This supports a focused probe, not a broad claim about all Brionac rulings.

The `mr1-synchro-protocol` now applies a checksum-guarded, in-memory
correction to that one pinned script. Seed 5 Synchro Summons Brionac, activates
it twice during turn 3, returns the opponent's Dark Blade with the first
activation, and targets Brionac itself with the second. Brionac then returns
to its owner's Extra Deck. The 1,111-decision duel reaches terminal, verifies
from its trajectory, and passes the player-visibility audit. The source file
remains unchanged; the loaded corrected script SHA-256 is
`b895a1bd35aa7260e0604602961ba5b6b4880f24ce0eff19c9c4bb64300c5198`.
Reproduce after [native setup](native_setup.md):

```sh
OMP_NUM_THREADS=1 PYTHONPATH=src:. .venv/bin/python \
  scripts/record_mr1_brionac_probe.py \
  --output .cache/goat-ai/mr1_brionac_probe_seed5.json
GOAT_AI_NATIVE_ROOT=.cache/goat-ai OMP_NUM_THREADS=1 PYTHONPATH=src:. \
  .venv/bin/pytest -q tests/test_mr1_brionac_probe.py
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

## Ryko's historical targeting in the MR1 probe

An [April 2010 Konami feature match](https://yugiohblog.konami.com/2010/sjc/10-04-75thsjc/round-11-feature-match-nik-ristoski-vs-luis-zambrana/)
describes a player chaining Dust Tornado to the card targeted by a flipped
Ryko, Lightsworn Hunter. This is evidence that the destruction choice was
made when Ryko's effect was placed on the Chain. The pinned current
`official/c21502796.lua` instead selects a card during resolution. The pinned
`pre-errata/c511003007.lua` selects a target before resolution. The isolated
MR1 probe now loads that exact pinned pre-errata script for Ryko, with source
and replacement SHA-256 checks. In seed 0, a Set Ryko is Flip Summoned,
chooses the opponent's face-up monster while its Chain Link is pending,
destroys that monster on resolution, and sends three cards from its
controller's Deck to the Graveyard. A paired branch targets an opposing Set
monster; the acting player's observation and `select_card` action omit its
identity until destruction publicly reveals it. Both resulting duels reach
terminal, replay-verify, and pass the visibility audit. This checks the
targeted branch and native script compatibility; it does not establish every Ryko
interaction or a complete Edison ruleset. Reproduce with:

```sh
GOAT_AI_NATIVE_ROOT=.cache/goat-ai PYTHONPATH=src:. .venv/bin/pytest -q \
  tests/test_mr1_ryko_probe.py
```

## Sangan as Synchro Material in a period feature match

A [February 2010 Konami feature match](https://yugiohblog.konami.com/2010/sjc/201002-nashville/round-1-feature-match-kevin-moon-vs-carl-randolph/)
records Sangan being used with a Tuner for a Synchro Summon and then searching
the Deck. That contemporary game report supplies an outcome check without
relying on Sangan's current, later-errata text. A seed-3 MR1 fixture Normal
Summons Sangan, then Junk Synchron on the next own turn, and uses both to
Synchro Summon Brionac. The native decision stream places the two materials
in the Graveyard, puts Brionac on the field, and then opens Sangan's search
chain. Selecting a legal monster moves it from Deck to hand. Random-agent
continuation reaches a terminal duel; the complete trajectory serializes,
replay-verifies, and passes the player-visibility audit. This checks one
Synchro-material trigger, not a complete Edison rules profile or every
historical Sangan interaction. Reproduce with:

```sh
GOAT_AI_NATIVE_ROOT=.cache/goat-ai PYTHONPATH=src:. .venv/bin/pytest -q \
  tests/test_mr1_sangan_synchro.py
```

## Dark Armed Dragon's exact DARK count in the MR1 probe

[Konami's Dark Armed Dragon card record](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=7421&ope=2&request_locale=en)
dates its first TCG printing to February 2008 and requires **exactly three**
DARK monsters in the Graveyard to Special Summon it. Its destruction effect
banishes a DARK monster from that Graveyard and targets a field card. The
[official March 2010 restriction list](https://www.yugioh-card.com/en/downloads/alt_format/2010-03-01.pdf)
limits Dark Armed Dragon and Card Destruction to one copy each. The MR1 probe's
explicit eligible set now includes those two IDs; it remains a narrow test set,
not a full Edison release pool.

Three seed-52 MR1 duels use Card Destruction to put two, three, or four DARK
monsters in the first player's Graveyard while drawing Dark Armed Dragon.
Its Special Summon is absent from the legal actions with two or four DARK
monsters and present with exactly three. In the three-DARK branch the player
Summons it, banishes Sangan from the Graveyard as the destruction effect's
cost, targets the opponent's face-up monster, and destroys that monster. All
three complete duels serialize, replay-verify, and pass the player-visibility
audit using pinned official scripts. This validates the count boundary and
one effect cost and target; summon responses, alternate costs, and historical
text differences elsewhere remain open. Reproduce with:

```sh
GOAT_AI_NATIVE_ROOT=.cache/goat-ai PYTHONPATH=src:. .venv/bin/pytest -q \
  tests/test_mr1_dark_armed_dragon.py
```

## Cyber Dragon's inherent Summon and Bottomless response

[Konami's Cyber Dragon record](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=6390&ope=2&request_locale=en)
allows its hand Special Summon when only the opponent controls a monster;
its 2100 ATK exceeds the threshold in
[Bottomless Trap Hole's official text](https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=5400&ope=2).
The [March 2010 list](https://www.yugioh-card.com/en/downloads/alt_format/2010-03-01.pdf)
allows two Cyber Dragons. The narrow MR1 probe now admits that card ID.

A paired seed-52 native fixture starts with Cyber Dragon in player 0's hand,
checks that its Special Summon is unavailable on an empty opposing field,
then has player 1 Summon a monster and Set Bottomless. On player 0's next
turn, Cyber Dragon is offered as a Special Summon and Bottomless is offered in
the response window. Activating Bottomless banishes Cyber Dragon; passing
leaves it on the field. Both branches reach terminal, serialize, replay-verify,
and pass the player-visibility audit. This checks one inherent Summon and
response window, not full Edison legality or every Summon-negation interaction.
Reproduce with:

```sh
GOAT_AI_NATIVE_ROOT=.cache/goat-ai PYTHONPATH=src:. .venv/bin/pytest -q \
  tests/test_mr1_cyber_dragon_bottomless.py
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
