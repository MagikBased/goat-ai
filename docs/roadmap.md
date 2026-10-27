# Project plan

GOAT AI's first goal is a **verified, headless GOAT duel that two random agents can finish**. Playing strength comes after rule correctness and information isolation. This plan uses evidence gates rather than calendar dates: a milestone is complete only when its exit criteria pass on a clean checkout.

## Current baseline

The repository has a Python environment contract, observation and action types, three baseline agents, and JSON trajectory serialization. Tests run locally; GitHub Actions is disabled for this project. The default engine raises `SimulatorUnavailable`. A restricted native adapter now completes normal-monster fixture duels; this is not a historical correctness claim. The selected engine is modern ocgcore with `DUEL_MODE_GOAT`, subject to ruling validation. See [native setup](native_setup.md).

## M0 — Prove the native engine path

**Status: complete for the first-decision prototype.** Reproduction and exact pins are in [native setup](native_setup.md). The implementation uses a direct `ctypes` binding; M1 must still decode responses and enforce player-visible observations.

**Work**

1. Pin exact ocgcore, card database, and script revisions with URLs, hashes, licenses, and reproducible setup instructions. Keep third-party artifacts out of Git.
2. Build and call the native core from a minimal Python harness. Use an explicit GOAT rules flag, 8000 LP, five opening cards, first-turn draw, and a fixed seed.
3. Inspect native decision messages, query APIs, and card/script loading. Record which message types and state queries are needed for full duels.
4. Decide between a direct C API binding and a patched ygoenv fork using a small measured prototype. The choice must preserve unrestricted legal option counts and player-scoped views.

**Exit:** A reproducible command starts a real GOAT-mode duel, reaches its first decision, and records the exact native versions and seed. A test checks the opening draw. Any unsupported message fails explicitly.

## M1 — Complete a duel safely

**Status: in progress.** A direct native binding completes restricted fixture duels with selected scripted cards. It handles optional chain choices, exposes structured public chain links and their field-target slots, monster battle positions, and Battle/Damage Step timing from public core events, and redacts the ID of a set opponent monster targeted by Nobleman. Observations include a bounded history of public turn, phase, attack, Damage Step, and chain events, the player's sorted initial Main Deck and own Fusion Deck identities, narrow memory of opponent field cards publicly seen before turning facedown with their field slots, public Deck-top reveals, recipient-scoped card reveals, the active disabled-zone mask, and a public Scapegoat summon restriction. Unrevealed opponent identities remain hidden. `.ydk` parsing, pinned whitelist checks, deterministic deck shuffling, and a complete metadata/script-path inventory for the 1,685 allowed whitelist IDs are implemented. Deck validation admits more than 60 Main Deck cards and selects historical or community Side Deck sizing. A separate experimental adapter completes 50 seeded synthetic control-deck duels and 20 cross-deck duels against a Chaos-style probe, including effect yes/no prompts. It now decodes bounded multiple-zone selection, Attribute announcement, and number announcement prompts; native fixtures exercise Ground Collapse, Homunculus the Alchemic Being, and Wall of Revealing Light respectively. Question fixtures reach a 1,039-name Monster announcement, redact the activating player's Graveyard during the chain, and confirm both ordinary and GOAT-variant printed-name branches. The historical announcement catalog still needs independent validation. A Fruits of Kozaky's Studies fixture covers a three-card private Deck-top ordering prompt. An Exchange fixture verifies that privately revealed opponent hand cards become selectable only for the addressed player, without exposing native hand slots. A Nobleman Flip-monster fixture verifies that full Deck reveals are delivered only to their addressed recipients. A Gravekeeper's Spy fixture verifies Deck-search recruitment and a paired native Deck-order differential; search actions omit private Deck slot numbers and are ordered by visible values. A reproducible random-deck probe generated ten whitelist-legal 40-card decks and completed all ten seeded 3,000-decision-limit duels in 12,382 decisions on the pinned assets; the report hash reproduced. Differential tests cover hidden opening-hand, set-monster, set-Trap, targeted set-Trap, and opponent Extra Deck identities, but broader decisions and visibility remain unaudited. General effect and decision coverage, independently audited historical legality, and complete player-visible observations are still required. Face-up monster ATK, DEF, counters, and public Equip Card target slots, including face-down cards equipped to Thousand-Eyes Restrict, are now included, but other dynamic public card state remains unaudited.

A paired Pot of Greed fixture swaps the two privately drawn cards while preserving the Deck multiset and public play. The opponent's complete observation and legal actions are identical at the next Main Phase decision; the acting player's drawn hand differs. A Book of Moon / Compulsory native fixture found and fixed lost opponent-hand knowledge when a previously public, now face-down monster returns to hand. A never-revealed Set monster remains unknown in the paired control fixture; the known-card duel serializes and replay-verifies. See [GOAT rules](goat_rules.md).

A paired Trap Dustshoot/Mystical Space Typhoon fixture now changes one
unrevealed opposing hand card and confirms that the Trap controller's
observation and legal responses are identical before Dustshoot activates.
Only its addressed reveal and known-hand memory differ afterward. Both
respond/pass full duels replay-verify; see [GOAT rules](goat_rules.md).

A documented [2020 championship Chaos Turbo Main Deck](../examples/decks/chaos_turbo_riclar_2020.ydk) now exercises a real archetype rather than only synthetic probes. With the experimental adapter and random agents, seeds 1–20 all reached terminal against `control_probe.ydk` within 3,000 decisions. Two seat-swapped, full-deck fixtures also serialize and replay-verify complete trajectories. These are protocol-coverage results; the random plays and current scripts do not establish historical correctness or playing strength.

A [2020 championship Goat Control Main Deck](../examples/decks/goat_control_lolmarcus_2020.ydk), paired with three test-copy Thousand-Eyes Restricts, also completed seeds 1–20 against that Chaos Turbo list within 3,000 decisions. Two seat-swapped matchup fixtures serialize and replay-verify full trajectories. The source omits the Extra Deck, so its contents are a disclosed test choice.

A documented [competitive Warrior Main Deck](../examples/decks/warrior_montague_clash.ydk) adds an aggressive archetype and Reinforcement of the Army to the corpus. It passes the pinned whitelist/deck-size gate. Random-agent Warrior versus Chaos Turbo duels completed all 20 games on seeds 1–10 in both seats within 3,000 decisions; two seat-swapped full-duel trajectories serialize and replay-verify. This extends protocol coverage, not card-by-card ruling validation or a playing-strength claim.

A further 60-duel random-agent sweep on seeds 21–30 covered all three pairings among the sourced Goat Control, Chaos Turbo, and Warrior lists in both seats. All reached terminal under a 3,000-decision cap, with 60,374 decisions total. Goat Control versus Warrior additionally has two complete seat-swapped trajectories that replay-verify. The measured two-worker runtime and limits are in [the evaluation log](evaluation.md). This widens M1 protocol coverage; M2 historical card correctness remains open.

The evaluator also runs all ten pairings of five executable Indianapolis 2005
Top 8 Main Decks through `--indianapolis-2005`. On two seeds with both agent
seats, all 40 RandomAgent duels reached terminal under the 3,000-decision
limit; ordered results and 39,057 total decisions matched between one and
four workers. This extends protocol coverage across contemporary submitted
decks, while the separate historical ruling and hidden-information audits
remain open. See [evaluation](evaluation.md).

A [GoatFormat guide Flip Control Main Deck](../examples/decks/flip_control_goatformat_guide.ydk) adds a fourth archetype centered on Tsukuyomi, Dekoichi, Magician of Faith, Mask of Darkness, and Time Seal. The guide does not name a tournament pilot or list an Extra Deck, so the fixture records neither. Forty random-agent duels against Chaos Turbo and Goat Control, paired across seats on seeds 31–40, all reached terminal under the 3,000-decision cap. Four full-duel fixtures serialize and replay-verify trajectories. A targeted native M2 fixture now checks two Mask of Darkness / Time Seal recoveries and skipped Draw Phases; interruptions and other timing branches remain open. Measured runtime and exact reproduction are in [the evaluation log](evaluation.md).

A [GoatFormat guide Dimension Fusion Turbo Main Deck](../examples/decks/dimension_fusion_turbo_goatformat_guide.ydk) adds a combo archetype centered on Thunder Dragon, Bazoo, and Dimension Fusion. The guide lists no Extra or Side Deck, and this is not a submitted tournament list. Twenty paired random-agent duels against sourced Chaos Turbo reached terminal under 3,000 decisions; two seat-swapped full-duel trajectories replay-verify. Targeted native fixtures verify Dimension Fusion's 2,000 LP cost, empty-banished-zone activation gate, revival of both Chaos Summon costs, both-player revival after D.D. Warrior Lady's battle banish, persistence through the End Phase, and matched Torrential Tribute and Solemn Judgment response windows. See [the evaluation log](evaluation.md) and [GOAT rules](goat_rules.md).

A second, independently published [Dimension Fusion reference composition](../examples/decks/dimension_fusion_turbo_wikiformat_reference.ydk)
has a saved source YDKE and all three 40/15/15 sections. Both seat-swapped
native duels pass replay and player-visibility audits. On its unseen Main Deck
in a 32-game mirror versus Tactical v14, the current feature-v23 policy scored
5–27. This identifies an archetype transfer failure for M4; the [evaluation
log](evaluation.md#independent-dimension-fusion-reference-list-27-october-2026)
records the schedule and limits.

An eight-duel on-policy Tactical-v14 labeling experiment trained 501
multi-option decisions on that reference composition. The warm-start child
scored 30–34 directly against its unchanged parent over 64 games on the
separate guide Dimension Fusion composition; its paired interval spans 50%.
The child is not promoted. M4 still needs a broader, independently labeled
signal and cross-archetype competitive gains.

A [2022 Worlds third-place Chaos Control list](../examples/decks/chaos_control_insids_worlds_2022.ydk) adds a fourth sourced tournament archetype with the published 40-card Main, 15-card Extra, and 15-card Side Deck. The public Format Library YDK was converted only where its modern IDs differ from pinned GOAT/pre-errata IDs; the conversion and source hash are in the deck header. The converted list passes the pinned whitelist gate. Four paired random-agent games against the sourced Chaos Turbo list all reached terminal under 3,000 decisions, and two seat-swapped full-duel trajectories replay-verify. This widens M1 protocol coverage; it does not validate every card interaction or estimate archetype strength. The measured result is in [the evaluation log](evaluation.md).

A [2022 Worlds first-place Chaos Return list](../examples/decks/chaos_return_dingosig_worlds_2022.ydk) adds a fifth sourced tournament archetype with the published 40-card Main, 15-card Extra, and 15-card Side Deck. The public Format Library YDK was converted to pinned GOAT/pre-errata IDs, with the source hash and conversion listed in the deck header. It passes the pinned whitelist gate. Twenty random-agent games against Warrior reached terminal under 3,000 decisions; two seat-swapped full-duel trajectories replay-verify. This adds Return from the Different Dimension, Bazoo, Shining Angel, and Zaborg to the protocol corpus. Separate native fixtures now verify Return’s basic Chaos-cost revival, its historical Book of Moon End Phase exception, one-open and full-Monster-Zone legality branches, including End Phase cleanup for the revived monster, matched Mystical Space Typhoon/Solemn Judgment/Royal Decree responses, plus Decree already face-up, that distinguish destruction, activation negation, and effect negation, Bazoo’s two-monster banish cost into a Return revival, Bazoo’s three-monster banish cost with its boost persisting through the opponent’s turn, Skill Drain chained after Bazoo's cost to negate its ATK increase, and Kycoo already face-up versus revived after Bazoo's cost. Other Return and Bazoo interactions still need card-specific audits. Shining Angel now has basic battle-recruitment, same-turn attack, empty-search opponent-only Deck verification, and Snatch Steal control-change fixtures; other interruptions remain untested. Zaborg now has mandatory-target fixtures for self-destruction and an opponent’s hidden monster, a Tribute Set fixture showing no trigger, and a Solemn Judgment fixture negating its Tribute Summon before the effect; responses to its activated effect remain untested. See [the evaluation log](evaluation.md).

A [sixth sourced tournament Main Deck](../examples/decks/bazoo_return_weirdchamp_worlds.ydk) transcribes Weirdchamp's published sixth-place World Championship Bazoo Return list. It passes the pinned whitelist gate. Two seeded random-agent duels against Goat Control, with Bazoo Return in each seat, reached terminal below 3,000 decisions and their complete trajectories serialized and replay-verified. The source did not provide Extra or Side Deck contents, so both sections remain empty. These are protocol-coverage results; they do not prove that every card effect in the list is historically correct.

**Work**

1. Implement `.ydk` parsing and April 2005 deck/card-pool validation. Begin with two small legal fixture decks and expand coverage.
2. Convert each native decision request into a variable-length list of structured actions. Map selected actions to exact native responses, including multi-step targets, effect choices, chains, and phase changes.
3. Build observations solely from player-visible native queries and observed public events. Maintain known-card memory without reading hidden identities from internal state.
4. Connect the adapter to `GoatEnvironment`; run two `RandomAgent` instances through terminal states. Record decision trajectories and replay seeds.
5. Add an interactive CLI duel and a real benchmark command. Record crashes, unsupported requests, and infinite loops as failures.

**Exit:** A clean setup completes seeded random-agent duels with valid outcomes and no unhandled native messages in the fixture decks. Illegal actions are rejected. Repeated seeds reproduce action/observation/outcome traces. Changing a hidden opponent hand or deck order while holding the visible state fixed cannot change the observation supplied to the agent.

A previous six-deck pairwise random-agent sweep covered all 15 distinct pairings among the then-current deck corpus, both seats, and seeds 9500–9501. All 60 games reached native terminal outcomes below 3,000 decisions; the ordered game results and decision counts reproduced exactly. The later Bazoo Return list was not part of that sweep. A seeded Ring/BLS mutual-lethal draw exposed a stale terminal `step()` observation, which now refreshes the native public state and shows 0/0 LP. The draw trajectory replay-verifies. This is protocol coverage, not a full-deck historical-ruling audit; see [the evaluation log](evaluation.md).

A tournament-pool random-deck mode now mixes only Main Deck cards from the
six sourced tournament lists within pinned copy limits, with a sourced Extra
Deck. Seeds 18600–18649 produced 50 distinct legal decks and 50 terminal
duels; all 46,875 decisions replay-verified against fresh pinned engines.

A separate broad-whitelist sweep on seeds 30000–30019 paired each generated
40-card deck with an independently generated opponent. All 20 duels reached
terminal within 3,000 decisions; all 21,078 decisions replay-verified and
passed the visibility audit. The 40 decks covered 1,036 distinct Main Deck
IDs. This extends M1 protocol evidence beyond tournament-list mixtures, but
does not certify the effects or 2005 rulings of every sampled card; see
[evaluation](evaluation.md#distinct-opponent-whitelist-protocol-sweep-27-october-2026).
An opt-in fresh-environment repeat of the same 20 games reproduced every
player-visible decision, selected action, terminal observation, and outcome;
the earlier sweep's deck hashes and game lengths also matched. This strengthens
the seeded-determinism part of M1 for the sampled corpus, without proving all
legal cards or historical interactions correct.
The report fingerprints source decks and 103 loaded native assets. This
expands common-card protocol coverage while leaving broader whitelist and
individual historical-ruling coverage open; see
[competitive action coverage](competitive_action_coverage.md).
An independent-opponent mode then paired 100 distinct legal tournament-card
Main Deck compositions across 50 duels; all 48,248 decisions replay-verified
without a cap or adapter error. This probes interactions between different
generated decks while preserving the same source-card and asset provenance.
An opt-in card-source counter reused the fixed-deck probe's target-safe
counting rules on those exact 50 cross-deck games. Outcomes and decision
counts reproduced; the run observed 61 Dekoichi Flip Summons and 131 selected
card responses to public chain links. This gives the next historical-ruling
audit a measured queue without claiming human play rates.
The older full-whitelist seeds-0–9 report cited above reproduces with project
source at `6611e1b` and the same pinned native assets. At the `7d05ea2` to
`b84e0d8` boundary, the Deck-search privacy fix changed the RandomAgent's
action order and therefore the paths for seeds 6 and 9. The other eight seeds
retained their counts. The current source reproduces 12,006 decisions; the
[README](../README.md) records its report hash and per-seed comparison.

An expanded 300-duel, four-worker sweep on seeds 9600–9609 also reached native terminal outcomes in every game. A 60-duel subset reproduced exact ordered outcomes and decision counts in a separate one-worker run. Measured rates, hardware, pins, and reproduction commands are in [the evaluation log](evaluation.md). This broadens M1 protocol evidence while M1 and the M2 card audit remain open.

The current six-tournament-deck corpus, now including Bazoo Return in place of the earlier guide-list slot, has its own complete pairwise protocol sweep: all 15 matchups, both seats, and seeds 9750–9751 reached terminal in **60/60 games** below 3,000 decisions. Ordered results and counts matched between one and four native workers; source-code and Lua-script-tree fingerprints now accompany the report. See [the evaluation log](evaluation.md). This tests the published deck corpus used to prioritize card rulings, not competitive agent strength.

A seeded Thunder Dragon / Morphing Jar fixture now checks the player-visible hand-memory boundary: a revealed search creates known opponent cards, a later hidden Set reduces the guaranteed count conservatively, and Jar's hand replacement clears current knowledge while retaining the historical reveal event. The full duel replay-verifies; see [GOAT rules](goat_rules.md).

A new **24-duel** whitelist-random, distinct-opponent probe on seeds
10000–10023 found five native protocol failures: four unsupported card-name
expression prompts (Prohibition, Mind Crush, Dark Designator) and one blind
opponent-hand choice (The Inexperienced Spy). Exact-expression catalog
decoding and a redacted blind choice resolved those cases. On the same
24-seed schedule, **24/24** duels reached terminal below 3,000 decisions;
all **25,833** decisions replay-verified. The ignored report is
`.cache/goat-ai/random-probe-distinct-10000-fixed/report.json` (SHA-256
`86576a1cf12a0836956348ee6a48735d1698e96295de1cc1f049654a038fd378`).

Fresh independent-opponent whitelist sweeps on seeds 10124–10147 and
10148–10247 reached **124/124 terminal duels** under 3,000 decisions,
with **129,521/129,521 decisions** replay-verified and visibility-audited.
The 248 generated Main Deck files had distinct hashes. The larger sweep
exercised 32 action kinds and loaded 1,306 distinct pinned native assets.
The ignored reports are
`.cache/goat-ai/random-probe-distinct-10124-10147/report.json` (SHA-256
`2a1c88991aa70f941d5198ee5c082544cbd39e41301215c062002e498daaf4d2`)
and `.cache/goat-ai/random-probe-distinct-10148-10247/report.json`
(SHA-256 `105427a10511dba17838af22f13edd3a6ef6de584d1be342a840f82ca6f86f2b`).
Both were produced at project commit `f2c209d` with
`scripts/probe_random_decks.py` SHA-256
`a5da3951f901b75a135d5db2c6b840c496e12f0e90d8b1d4ae7bde76411f6856`.
This is broad protocol and information-boundary evidence, not a ruling audit
for all cards loaded or a proof of GOAT-correct outcomes.

A later fresh sweep on seeds 10324–10355 reached **32/32 terminal duels**;
all 33,664 decisions replay-verified and passed visibility auditing. It loaded
10 native assets absent from the 10148–10247 sweep. See the
[evaluation record](evaluation.md#further-independent-whitelist-probe-27-october-2026).

The next 100 independent whitelist-deck pairs on seeds 10024–10123 initially
yielded 93 terminal, replay-verified duels. A SHA-guarded in-memory correction
fixed three pinned Firebird battle callback crashes. Bounded native
`MSG_SELECT_SUM` decoding fixed two Puppet Magic seeds; recipient-scoped hand
reveal handling and blind-choice redaction fixed two more. The corrected sweep
reached **100/100 terminal**, with **113,037 replay-verified decisions**; see
[evaluation](evaluation.md). The decoder now parses implicit mandatory cards
for exact and exceed sums, but that extension has parser-only tests. Large
sum-choice sets now use incremental legal-prefix selection; a forced staged
Puppet Magic duel matches the flat native outcome and replay-verifies. A
native mandatory-card sum prompt has not yet been observed.
A paired Firebird fixture checks the corrected callback's effect, not just
termination: a friendly Winged Beast's battle destruction adds 500 ATK,
while a friendly non-Winged Beast's does not. Both full duels replay-verify;
see [GOAT rules](goat_rules.md).
An independent second 100-pair whitelist sweep also reached **100/100
terminal** with **103,185 replay-verified decisions**; see [evaluation](evaluation.md).
This is a protocol and reproducibility result, not a historical correctness
certificate for arbitrary decks. Focused native fixtures verify the
declaration catalogs against two hidden opponent Decks and the Spy reveal
boundary; see [GOAT rules](goat_rules.md).

A new 32-pair tournament-card mix and 32-pair full-whitelist mix each used
independent legal decks for both players. All **64** duels reached terminal,
and all **64,444** decisions replay-verified and passed the legal-choice
visibility audit. These are broader protocol and selection-boundary checks,
not a full observation or historical ruling certificate; see
[the action-coverage report](competitive_action_coverage.md).

A further 50-pair distinct whitelist sweep (seeds 10224–10273) exposed two
new native-path cases. A Magical Hats Spell/Trap flipped face-up in a Monster
Zone has no Type; the observation and trajectory schema now preserve an
explicit null Type and the exact seed 10247 reaches terminal with full replay
and visibility verification. Seed 10227 exposed a recursive native event
when GOAT Rivalry of Warlords requested a Type choice while two face-up
Types were present. A SHA-guarded in-memory correction prevents the active
adjust effect from re-entering while sending away the other Type. Both Type
choices now reach terminal with full replay and visibility checks. The
corrected 50-pair sweep reached **50/50 terminal** with **52,275** decisions
replay-verified and visibility-audited. Keep M1 open for broader arbitrary-deck
coverage; see [the protocol log](evaluation.md).
A fresh distinct-whitelist 50-pair run reached **50/50 terminal** with
**54,273** replay-verified and visibility-audited decisions. A separate
50-pair run mixing cards from six sourced tournament decks also reached
**50/50 terminal**, with **46,227** verified decisions. Both used distinct
legal opponent decks and found no adapter error; neither proves complete
arbitrary-deck or historical-ruling coverage. See
[the sweep reports](evaluation.md#fresh-distinct-deck-protocol-sweeps-27-october-2026).

Two additional independent 100-pair sweeps reached **200/200 terminal** with
**204,472** replay-verified and visibility-audited decisions. The full GOAT
whitelist mix loaded 22 script assets absent from three prior local reports;
the six-deck tournament-card mix selected 68 chain-response pairs absent
from its prior 50-pair run. These increase sampled protocol coverage but do
not close M1's arbitrary-deck completeness or M2's historical ruling gate.
See [evaluation](evaluation.md).

## M2 — Historical correctness gate

A native-enabled local regression run on 2026-10-27 passed **1,003 tests**
in 13 minutes 43 seconds after correction of a schema-v6 test projection
carrying newer owner and pending-summon fields. The ignored full-run log is
`.cache/goat-ai/native_full_20261027_rerun.log` (SHA-256
`9da9d6baf3b2b25e0a95745f8c94ada560cdf3d669e5da2183efc7a35784602a`).
Two Firebird effect tests and two review-queue tests were added after that
run started; both test files then passed separately, **7 tests in 13.25s**.
This is regression coverage for the tested fixtures, not a blanket claim
that every GOAT ruling is historical.

Prioritize rulings by observed GOAT tournament play. The reproducible
`python -m scripts.report_competitive_card_priorities --native-root .cache/goat-ai`
report ranks cards in six sourced tournament Main Decks by deck presence and
copies. Its current top group is Book of Moon, Nobleman of Crossout, Delinquent
Duo, Breaker, Heavy Storm, Pot of Greed, Ring of Destruction, Black Luster
Soldier, Graceful Charity, Dekoichi, and Trap Dustshoot. Add focused interaction
fixtures for those staples and their common opponents before testing obscure
cards. A fixture reference in the report indicates code coverage only; each
historical ruling still needs its own source and behavioral assertion. Side
Deck cards and archetype-specific cards follow when a competitive matchup
requires them.

The newly sourced 2005 Phoenix Control matchup now has a linked Hand of
Nephthys / Scapegoat / Torrential Tribute fixture. It checks a Sheep Token
paid as Hand's cost, Phoenix Summoned from the Deck, effect destruction, its
next-Standby revival, and the resulting backrow sweep. The full duel
replay-verifies and passes the visibility audit; 2005 rulings and remaining
Phoenix cases are recorded in [GOAT rules](goat_rules.md).

**Status: in progress.** The source-backed Cannon Soldier / Book of Moon fixture checks historical Ignition priority after a summon, the GOAT Nobleman fixtures check a representative banish ruling and Flip-monster Deck verification, two Field Spell fixtures check replacement and chained destruction, a Dekoichi fixture checks a basic Flip Effect draw and Book of Moon's Damage Step restriction, a Peten fixture compares missed timing after Cannon Soldier's cost with a successful battle trigger, a Sangan/Thestalos fixture checks mandatory trigger ordering and reverse chain resolution, and a Solemn Judgment fixture checks Normal Summon negation. Pre-errata Dark Magician of Chaos fixtures check Spell recovery after its two-Tribute Normal Summon and its face-up versus face-down leave-field destination when tributed by Cannon Soldier. A Goat Control fixture follows Scapegoat into Metamorphosis for Thousand-Eyes Restrict, equips an opposing monster, then uses Tsukuyomi to set Restrict and checks the hidden view. A paired Book of Moon reset fixture equips two opposing Sheep Tokens in one turn by setting and Flip Summoning a Restrict that was Summoned earlier; branches with a prior manual position change, attack declaration, or Summon by the turn player correctly offer no same-turn Flip Summon. All four full duels replay-verify. Four Snatch Steal fixtures take an already equipped Restrict, check Equip Card zones across control change, Book of Moon after Snatch, Book chained before Snatch resolves, and Heavy Storm returning Restrict. All four full duels replay-verify against the official 2005 rulebook zone rule and historical card rulings. A separate Tsukuyomi fixture tests mandatory self-targeting as the only face-up monster and confirms the face-down Spirit stays on the field through End Phase. Scapegoat fixtures check four token placements, the four-vacant-zone requirement, same-turn Summon restrictions, a legal monster Set, token tribute for Cannon Soldier but not a Tribute Summon, and restoration of Summon permission after Solemn negates its activation. Trap Dustshoot fixtures check the four-card hand threshold, opponent-hand reveal scope, monster selection without private hand slots, and a terminal replay-verified duel. Common-staple fixtures check Graceful Charity's draw and discard choices, Delinquent Duo's random and chosen discards without exposing opponent hand cards, Snatch Steal's control and Standby Phase recovery followed by Heavy Storm returning the monster, and Book of Moon setting the stolen monster while control remains with the stealing player. Paired GOAT Bottomless Trap Hole fixtures check a Normal Summon banish and the historical Book of Moon escape into a known face-down field slot. A three-branch Breaker/Bottomless fixture checks the response to Breaker's counter-placement trigger, declining it, and Book of Moon chained behind Bottomless; all full duels replay-verify. Paired Sakuretsu Armor fixtures verify attack-triggered destruction versus a chained Book of Moon that saves the face-down attacker, following the historical ruling. Paired Royal Decree/Mirror Force fixtures show Decree chained to Mirror negating its effect, saving the attacker, and allowing 1900 direct damage. A Mirror Force and Book of Moon attack-response fixture checks that the chained face-down attacker survives while another Attack Position monster is destroyed. A Torrential Tribute and Book of Moon summon-response fixture checks that the face-down monster is still destroyed with the other monster. Pre-errata Ring of Destruction fixtures check own-monster targeting and equal damage, plus Breaker removing its Spell Counter as a cost before Ring deals 1600 damage and the pending Breaker effect destroys a set card. Chaos Sorcerer fixtures check the LIGHT/DARK Graveyard summon cost, opponent-monster banish, and same-turn attack restriction, a negative field-only cost case, and Book of Moon making the target invalid while still spending Sorcerer's effect and attack opportunity. A Snatch Steal/Scapegoat fixture now checks destruction of a stolen monster when Mystical Space Typhoon removes Snatch while the original controller has five occupied Monster Zones; the full duel replay-verifies. A GOAT Black Luster Soldier fixture checks its LIGHT/DARK Graveyard summon cost, optional second-attack trigger after battle destruction, direct second attack, two-attack limit, and alternative monster-banish effect with its same-turn attack restriction, plus loss of that effect after a declared attack. A pre-errata Sinister Serpent fixture checks optional Standby Phase return after a discard, including its public Graveyard and private hand boundaries. A Tribe-Infecting Virus fixture discards Serpent as an activation cost, limits Type announcements to face-up monsters, destroys the declared opponent Type, and returns Serpent on the next Standby Phase. A Book of Moon response branch verifies that Tribe does not destroy a monster turned face-down after its Type was declared, and checks the resulting hidden field view. Paired Premature Burial fixtures verify its 800 LP revival cost and the different outcomes when Book of Moon breaks the Equip link by turning the monster face-down versus Mystical Space Typhoon destroying the Equip Spell, and a chained Typhoon preventing the initial revival after the 800 LP cost is paid. Call of the Haunted fixtures check that Book of Moon severs the revived monster while Call stays face-up and the face-down monster remains, and that the two Call/Mystical Space Typhoon chain orders differ in whether a Summon is attempted before both cards and the monster end in the Graveyard. Airknight Parshath fixtures check piercing damage and its mandatory draw against a set monster, Waboku preventing both damage and the draw, and Airknight drawing before an attacked Dekoichi’s Flip Effect draw. Paired Jinzo fixtures check a set Mirror Force is unavailable while Jinzo is face-up, then becomes a legal and resolving attack response after Book of Moon turns Jinzo face-down. Paired Magician of Faith fixtures check Spell recovery after a Flip Summon, the opponent card reveal, and continued Flip Effect resolution when Book of Moon turns Magician of Faith face-down. Creature Swap fixtures check its both-sides eligibility gate, choices made during resolution, variable-length own-monster options, position-change restriction, persistent exchanged control, and retained knowledge when one or both exchanged monsters are set; both set-monster duels replay-verify. Pre-errata Brain Control fixtures distinguish Book of Moon chained before control from Book used afterward, check End Phase return of a face-down monster and known-card memory across control change, replay-verify a complete duel, and confirm that its historical target condition can take Thousand-Eyes Restrict after a Scapegoat/Metamorphosis Summon. Enemy Controller fixtures check both effect choices, Tribute as an activation cost for temporary control, and End Phase control return. Exiled Force fixtures check its self-Tribute activation cost, hidden opponent monster targeting by field slot, no effect when it is the only monster, identical target-decision views when the hidden monster changes between a Flip monster and a Normal Monster, and a replay-verified Torrential Tribute response to its summon-priority effect. Dust Tornado fixtures check destruction of a hidden set Trap, optional Set from hand, opponent field secrecy, same-turn versus following-turn Book of Moon activation timing, and no Set after chained Mystical Space Typhoon destroys Dust Tornado's target. GOAT Spirit Reaper fixtures check battle survival, target-driven self-destruction versus Book of Moon concealment, the Snatch Steal/Mystical Space Typhoon chain distinction that requires the dedicated GOAT script, and direct-attack discard only when Waboku does not prevent damage. Morphing Jar fixtures check both six-card hand discards and five-card draws, with a differential run proving that changing only the opponent's newly drawn private card does not change the acting player's observation or legal actions. D.D. Warrior Lady versus Morphing Jar fixtures check mandatory-then-optional Damage Step chain ordering, both choices for Warrior Lady, public banish destinations, and Jar's hand reset even when the monsters leave the field first. An Asura Priest/Scapegoat fixture checks four separate Token attacks, no direct attack afterward, Token cleanup, and Spirit return to hand at End Phase. Kycoo fixtures check the face-up Chaos Graveyard banish lock, its release after Book of Moon sets Kycoo, the optional one-or-two-monster banish after direct battle damage, the exclusion of a monster Kycoo just destroyed from that Damage Step choice, and Nobleman of Crossout remaining legal against a set field monster. Old Vindictive Magician fixtures check Flip Effect destruction of a face-up or hidden opposing monster, including target secrecy. GOAT Apprentice Magician fixtures check its optional battle recruitment of a face-down Level 2 Spellcaster, its opponent-only card reveal tied to the recruited field slot, and a decline branch; a linked Old Vindictive recruit and next-turn Flip Effect line reaches terminal and replay-verifies a schema-v14 trajectory. GOAT Gravekeeper's Spy fixtures recruit Guard from the Deck without exposing native Deck order, recruit another Spy under pre-errata Necrovalley despite the resulting 1700 ATK, and test opponent-only verification after an empty search using a pinned runtime utility correction. Mystic Tomato fixtures cover an optional Damage Step recruiter into Sangan after battle destruction, a decline branch, hidden attack targeting, and the recruited monster's same-turn attack option. Cyber Jar and Ground Collapse fixtures cover public five-card reveal order and a two-zone lock respectively. The remaining timing and card-specific cases below are untested.

A paired native Ring of Destruction and Book of Moon fixture now checks target validity at resolution, the no-damage outcome when Book sets the target, and the opponent's hidden field view. Its historical interpretation is identified as an inference in [GOAT rules](goat_rules.md).

An attacked Morphing Jar / Skill Drain pair now checks a sourced Damage Step
boundary: an aged Set Drain cannot be chained to Jar's battle-triggered Flip
Effect, whereas activating Drain before the attack negates that effect while
Jar remains face-up. Both full duels replay-verify and pass the visibility
audit; see [GOAT rules](goat_rules.md).

A paired Creature Swap / Scapegoat fixture now tests a common Goat Control Token exchange: Scapegoat chained to Swap adds four legal Token choices at resolution, while passing leaves only the original monster available. A Ring of Destruction response fixture removes the defender's only monster before Swap resolves and confirms the exchange fails. All three full duels replay-verify; other interruption types remain open. See [GOAT rules](goat_rules.md).

A pre-errata Sinister Serpent fixture now checks two returns within one Standby Phase, separated by Raigeki Break discarding Serpent as its cost. The hidden Trap target and opponent's known-hand update are checked in a full replay-verified duel. See [GOAT rules](goat_rules.md).

Paired Raigeki Break/Mystical Space Typhoon fixtures now test the response
when Typhoon targets a Set Break. Chaining Break pays its discard and destroys
an opposing monster before Typhoon removes Break; passing preserves the
monster. Both complete duels replay-verify and pass the visibility audit; see
[GOAT rules](goat_rules.md).

A battle-flip Magical Merchant fixture now confirms that an attacked Set
Merchant resolves its excavation while still on the field, then reaches the
Graveyard after the Damage Step. The public excavation, opponent's known-hand
card, hidden attack-target choice, complete replay, and visibility audit all
pass; see [GOAT rules](goat_rules.md).

A paired Metamorphosis fixture now confirms that Raigeki Break can discard a
card and destroy the activated Normal Spell without stopping its Fusion
Summon, matching the previously tested Mystical Space Typhoon response. Both
response and pass branches finish, replay-verify, and pass visibility checks;
see [GOAT rules](goat_rules.md). This supports the user's resource-preservation
review without making the heuristic a rules engine.

A Morphing Jar / pre-errata Night Assailant fixture now checks two discard triggers after both players draw their replacement hands, including the opponent-only reveals of the two recovered cards. Its complete duel replay-verifies; see [GOAT rules](goat_rules.md).

Paired Morphing Jar / Solemn Judgment fixtures verify that Solemn can negate Jar's Flip Summon before either hand is reset, while passing allows Jar's discard and five-card draws. Both full duels replay-verify; see [GOAT rules](goat_rules.md).

Paired Morphing Jar / Skill Drain fixtures verify a distinct response window: Skill Drain chained to Jar's Flip Effect negates the hand reset while leaving Jar face-up; passing lets the effect resolve. Both full duels replay-verify; see [GOAT rules](goat_rules.md).

Paired three-card fixtures now check Morphing Jar's Flip Effect with chained Skill Drain and a Book of Moon response: Book sets Jar face-down before Drain resolves, so Jar's already activated effect still resets both hands. The control branch without Book stays negated. Both full duels replay-verify; see [GOAT rules](goat_rules.md).

Paired D.D. Warrior Lady / Skill Drain fixtures check a Damage Step effect after Skill Drain is activated in the Battle Step: Warrior Lady can still choose her effect, but Drain negates the banish; without Drain, both battling monsters are banished. Both full duels replay-verify; see [GOAT rules](goat_rules.md).

Three Mobius the Frost Monarch fixtures cover one and two hidden backrow targets, plus chained Mystical Space Typhoon removing one target while Mobius still destroys the other. Mobius appears in two sourced tournament Side Decks. All three full duels replay-verify; see [GOAT rules](goat_rules.md).

Paired Swords of Revealing Light fixtures check that chained Mystical Space Typhoon destroys Swords but does not prevent it from flipping a Set Dekoichi and causing Dekoichi's draw. The following-turn attack is legal only in the Typhoon branch. Both full duels replay-verify; see [GOAT rules](goat_rules.md).

A separate Swords fixture verifies its duration across three opposing turns: attacks are unavailable on turns 2, 4, and 6; Swords expires in turn 6's End Phase and an attack becomes legal on turn 8. The full duel replay-verifies; see [GOAT rules](goat_rules.md).

Paired Mind Control fixtures now verify that a stolen monster cannot attack or pay Cannon Soldier's Tribute cost, including after Book of Moon turns it face-down, and that it returns to its original controller in the End Phase with the correct hidden field view. Mind Control appears in two sourced tournament Side Decks. Both full duels replay-verify; see [GOAT rules](goat_rules.md).

A third Mind Control fixture targets an already Set monster without leaking its identity in the legal action, then verifies face-down control transfer, End Phase return, and player-visible field memory. Its full duel replay-verifies; see [GOAT rules](goat_rules.md).

A fourth Mind Control fixture confirms the historically barred Metamorphosis Tribute: with a Level 4 Fusion available, Metamorphosis can use the controller's own Cannon Soldier but does not offer the stolen Level 4 monster as a cost. The full duel replay-verifies; see [GOAT rules](goat_rules.md).

Three Kuriboh fixtures now cover its private-hand Damage Step response: accepting versus declining it against a direct attack, and using it to prevent damage without saving a weaker face-up monster from battle destruction. Kuriboh appears in two sourced tournament Side Decks. All three full duels replay-verify; see [GOAT rules](goat_rules.md).

Three Mystik Wok fixtures with Breaker verify Tribute as an activation cost, the pre-counter 1600-ATK response window, and the later choice between Breaker's current 1900 ATK and 1000 DEF. Mystik Wok appears in two sourced tournament Side Decks. All three full duels replay-verify; see [GOAT rules](goat_rules.md).

Paired Zombyra the Dark fixtures cover its post-battle 200 ATK loss, direct-attack prohibition, and recovery to 2100 ATK after Book of Moon Sets it for a later Flip Summon. Zombyra appears in the sourced Warrior Main Deck and was selected in the competitive-deck protocol sample. Both full duels replay-verify; see [GOAT rules](goat_rules.md).

Four Morphing Jar deck-out fixtures verify the historical five-card draw boundary for either player: with four Deck cards the effect ends the duel, while with five it resolves and the next required draw ends the duel. Four more native fixtures check both players near empty: 3/4, 4/4, and 4/3 cards remaining each give a draw, while five each resolves and the next required draw determines the loser. All eight terminal trajectories replay-verify. A contemporaneous 2005 TCG source for the simultaneous failed-draw outcome remains to be located, so that historical interpretation is provisional. See [GOAT rules](goat_rules.md).

A June 2005 Desert Sunlight / Book of Moon correction now enables the recorded
four-link Nobleman response against a Set Morphing Jar. The fixture observes
two delayed Flip Effects, ten draws per player in two batches, and a full
terminal trajectory with replay and visibility checks. The correction is
scoped to a pending Desert Sunlight from the target's controller; other
face-down Book-target cases still need independent rulings. See
[GOAT rules](goat_rules.md) and [native setup](native_setup.md).

A source-backed Jinzo/Skill Drain timing pair checks whether Skill Drain
resolves before Premature Burial revives Jinzo or Jinzo is already active when
Traps could respond. Mirror Force is legal only in the former branch. A third
branch activates Royal Decree after both Skill Drain and Jinzo are face-up;
Mirror Force becomes unavailable again, matching the archived ruling's
observable consequence. All three complete duels replay-verify and pass the
visibility audit. Other continuous-effect permutations remain open. See
[GOAT rules](goat_rules.md).

A paired Jinzo/Solemn Judgment fixture now checks the Tribute Summon window:
Solemn is legal before Jinzo's continuous Trap suppression applies, but is
unavailable after a successful Summon. Both full duels replay-verify and pass
visibility checks; see [the ruling note](goat_rules.md#solemn-judgment-against-jinzos-tribute-summon).

**Work:** Create source-backed regression fixtures for first-turn draw, summon response and Ignition priority, chain construction and resolution, trigger ordering and missed timing, Damage Step restrictions, flip effects, summon negation, historical field spells, the April 2005 list, and representative pre-errata card rulings. Track unresolved rulings in `docs/goat_rules.md` with the chosen interpretation and evidence.

A focused native first-turn draw fixture now checks both players' initial hand
and Deck counts: six/34 for player 0 on turn one, then six/34 for player 1 on
turn two after passing. The adapter rejects unsupported rule-profile flags
instead of recording a profile that the GOAT-mode core did not execute. See
[the source and fixture](goat_rules.md#first-turn-draw).

**Exit:** Every required fixture passes with pinned engine assets, or is marked as a known incompatibility that blocks a GOAT-correct claim. Run differential checks against documented examples or independently observed duels where practical. Expand the legal-card test corpus beyond the initial fixture decks.

The six-deck tournament action probe can now save and replay-verify complete
JSON trajectories. One seeded CombatHeuristicAgent schedule covered all 15
unordered pairs with both seats: all 30 duels and 16,979 decisions verified
against fresh pinned native engines after serialization. This broadens
end-to-end adapter coverage of commonly played cards, while individual
historical effect claims still require source-backed ruling fixtures. See
[competitive action coverage](competitive_action_coverage.md).
On the identical seed and deck schedule, RandomAgent completed and
replay-verified 30 duels with 25,782 decisions. It selected 21 Dekoichi Flip
Summons, versus zero under CombatHeuristicAgent, and reached substantially
more Nobleman and Dustshoot activations. Future high-play-card audits should
sample both agents; these unequal game lengths do not imply historical usage
rates or an agent-strength comparison.

A paired Magician of Faith/Torrential Tribute fixture now confirms that a
Flip Summoned Faith still recovers its chosen Spell after Torrential destroys
it, including the opponent-only recovery reveal. It replay-verifies both
branches; broader high-play interaction coverage remains open.

A paired Time Seal/Solemn Judgment fixture now checks the next Draw Phase in
both the resolved and negated branches. Each full duel replay-verifies and
passes the player-visible legal-choice audit. This closes one frequent
competitive-probe response pair, not general chain correctness.

A historical Tribe-Infecting Virus / DNA Surgery pair now checks that a
Reptile declaration destroys Gagagigo if the opponent passes, while chaining
DNA Surgery to make all face-up monsters Aqua causes Tribe to destroy none.
Both complete native duels serialize and replay-verify. Schema v24 adds each
face-up monster's **current** public Type to the player observation; facedown
Type remains hidden. Older v23 policy and self-play recordings still verify.
The tactical Tribe evaluator now uses current Type when present rather than
printed card metadata. See [GOAT rules](goat_rules.md).

A three-branch Ring of Destruction / Rush Recklessly fixture now checks the
historical current-ATK rule and chain order: Ring deals 1900 damage to each
player when Rush is passed or Ring chains to Rush, and 2600 when the GOAT
Rush variant chains to Ring and boosts its target first. All three complete
native duels replay-verify and pass the player-visible trajectory audit; see
[GOAT rules](goat_rules.md).

A paired Dimension Fusion / pre-errata Dark Magician of Chaos fixture now
checks the optional immediate Spell recovery after Bazoo banishes DMoC. The
spent Dimension Fusion is a selectable Graveyard target, and the opponent
learns its identity in hand only when recovery is accepted. Both full duels
replay-verify and pass the visibility audit. A separate Return chained to
Heavy Storm fixture checks that a DMoC Summoned at Chain Link 2 misses its
optional recovery timing. It also replay-verifies and passes the visibility
audit; the [ruling log](goat_rules.md) records the sources and limits.

## M3 — Evaluation and data

An eight-duel two-worker native pilot now reports per-process Linux peak RSS,
reset overhead, and throughput on sourced decks; see the
[evaluation log](evaluation.md). Memory scaling to larger worker counts remains
unmeasured.

**Status: in progress.** Seeded tournament runners swap seats for each deck matchup, record individual outcomes, report seat and matchup splits, and give paired score and Wilson intervals. A spawned-process runner reproduces the sequential results on a native fixture and has a measured two-worker throughput example. A restricted-fixture baseline report is in [the evaluation log](evaluation.md). Schema v18 trajectories add a final player-visible terminal observation to the v17 decision records, which record face-up monster ATK, DEF, and counters alongside bounded public events, field-slot known-card memory, conservative opponent-hand knowledge from public returns and addressed hand reveals, a public Scapegoat restriction, public Deck-top reveals, active disabled zones, recipient-scoped private reveals, and the player's initial Main Deck composition; they can be replayed against the native engine with exact observation, legal-action, result, deck-content, rules-profile, and loaded-asset comparisons. An offline browser viewer renders these player-visible decisions with optional locally cached card art. It interpolates attack arrows, target markers, Life Point fill and numbers, and field-to-Graveyard or banished-pile movement between recorded decision snapshots; it does not reconstruct every native event. The new GOAT-only native core patch changes the binary fingerprint, so older recordings require re-recording for exact verification on the current setup. Broader deck families, held-out opponents, authorized human replay reconstruction, training/evaluation separation, and memory scaling across more workers remain outstanding.

A first sourced-deck baseline now evaluates HeuristicAgent versus RandomAgent on both Goat Control/Chaos Turbo deck assignments with seat swaps. The 32-game seeds-7000–7007 report and its limitations are in [the evaluation log](evaluation.md). This does not satisfy the held-out competitive-policy exit gate.

The offline viewer can now collect local retrospective labels for legal
decisions in a recorded duel. Annotation files are tied to the trajectory
byte hash and require explicit self-recorded authorization; cloning verifies
the full replay and visible action safety before using only labeled choices.
A one-label Breaker smoke run passed. These are hindsight annotations, not
reconstructed DuelingBook/EDOPro games or expert demonstrations; see
[the evaluation log](evaluation.md).

**Work:** Build seeded agent tournaments with deck and matchup splits, seat swaps, confidence intervals, and held-out evaluation opponents. Measure duel throughput, decisions per second, runtime memory, and initialization overhead on named hardware. Validate self-play trajectory round trips. Investigate `.yrp` and `.yrpX` reconstruction; ingest human games only when permission, legal-action recovery, and player-visible knowledge can be established.

A bounded EDOPro container reader now parses `yrp1` Deck/response records and
`yrpX` packet streams using the pinned upstream header layout. Its CLI omits
player names, Deck card IDs, and raw choices from summaries. Tests use
synthetic source-layout fixtures and reject truncation, oversized payloads,
and another simulator's `yrp2` magic. Five real modern `.yrpX` samples from
an MIT-licensed replay-tool repository now pass intake inspection, including
raw LZMA streams without end markers and one extended-header replay. This is
an intake inspection tool. Each real packet stream had no selection prompts
but did contain one valid embedded `yrp1` Deck/response record; the CLI now
reports its response count without printing private values. It is still
not replay decision reconstruction or an authorized human-data pipeline.
An optional private-safe GOAT card-pool screen rejects all five modern
samples without publishing their Deck card IDs; it is only an intake filter,
not historical or training validation. It now also rejects exact card-ID
copy counts above the whitelist limit across each player's Main and Extra
Deck. A synthetic 40-card-per-player replay test covers a duplicate limited
ID across those sections and confirms that the report contains only counts.
An opt-in native Deck screen now runs the pinned validator on the replay's
Main and Extra Decks. A native test confirms that it catches an alias pair
over the shared limited-card count and a non-Fusion in the Extra Deck that the
whitelist-only screen cannot catch. The replay container has no Side Deck
record; deck screening alone cannot admit a replay for training.
A public standalone 2012 `.yrp` with 248 saved responses now also passes
structural intake, closing the real-file check for that container form. Its
rules flags and Decks fail GOAT screens, and its repository identifies no
training license, so it remains an ignored read-only sample. See [research](research.md).
The structural reader now retains the three legacy duel settings required
to recreate startup. A separate private-safe setup screen compares the
embedded legacy replay, when present, with this project's two-player,
8000-LP, five-card, one-draw, exact-`DUEL_MODE_GOAT` profile. All five real
modern samples fail; four differ in rule flags, and one also differs in LP
and opening hand size. A match remains only a reconstruction candidate, not
permission to train or evidence of historical correctness.
The native probe can now start from the four recorded EDOPro RNG words and
preordered Main/Extra Deck entries, matching the pinned old-replay startup
contract instead of applying the project's normal Python Deck shuffle. A
complete vanilla native duel proves that this alternate startup reproduces
all decoded prompts, player views, responses, and terminal outcome when fed
identical inputs. A synthetic extended-header `yrp1` with every response from
one vanilla duel now reconstructs a complete sequence of public observations,
legal actions, selected actions, and terminal outcome on the pinned adapter;
altered and missing responses fail. Custom rule cards are rejected, and
ambiguous or invalid responses still fail explicitly. Synthetic GOAT Thunder
Dragon zero-, one-, and two-copy searches and a Puppet Magic sum choice now
replay through staged public actions when the adapter's action bound forces
them; the saved native response is committed only once. The optional native
inspection command also unwraps `.yrpX`, checks its player count, rules flags,
and RNG words against the embedded legacy replay, and reports only counts and
provenance hashes. Reconstruction also rejects any recovered choice outside
its visible legal set or flagged by the decision visibility audit; a synthetic
injected leak makes the inspection command fail closed. This does not
prove that a real EDOPro recording replays on our core or that its original
asset versions match. A permitted real GOAT fixture and independent
player-knowledge audit remain open.
Before using any `.yrp`/`.yrpX` for imitation, obtain a permitted real GOAT
replay fixture, match its original core/scripts, recover each legal-action
set and selected response, and pass the existing visibility and exact replay
gates. See [research](research.md).
The [replay contribution guide](replay_contributions.md) now distinguishes
parser-only permission from model-training permission and gives a local,
privacy-preserving intake command. Public replay archives found so far have
not supplied an explicitly licensed GOAT training fixture.

A 16-duel, sourced-deck native worker pilot now compares 1, 2, 4, and 8
spawned processes on identical seeds and both deck seat orders. Ordered
outcomes and decision counts matched at all four worker counts. The measured
throughput and per-worker peak memory are in [benchmarks](benchmarks.md);
large training jobs and instantaneous total memory remain unmeasured.

**Exit:** A reproducible benchmark report and tournament report exist for the tested core/assets/decks. Replay support is claimed only for formats that have parser and reconstruction tests.

A local batch collector now records both policy seats across named matchups
and seeds using independent native workers. It replay-verifies and audits
each player-visible trajectory and writes a SHA-bound manifest. A two-game
serial/parallel smoke schedule produced identical trajectory bytes; see
[evaluation](evaluation.md). This supplies reproducible policy-visited data
for on-policy imitation without treating it as human gameplay.

The sourced-deck single-process benchmark records reset overhead and peak process RSS alongside throughput on named hardware. A separate spawned-worker benchmark now measures one and two workers on the sourced Goat Control/Chaos Turbo decks, including per-worker high-water RSS and native reset time; the seat-swapped game outcomes reproduce across worker counts. [The benchmark log](benchmarks.md) gives the measurements and their limits. Instantaneous total memory use, broader deck families, and a scaling curve remain unmeasured.

A balanced six-deck evaluation now tests both deck assignments and both seats for HeuristicAgent versus RandomAgent and an identical random-versus-random control. The paired score-difference helper reports a measured heuristic advantage with a confidence interval on this small schedule; [the evaluation log](evaluation.md) gives the deck splits and limits. This supplies a stronger baseline for M4 comparisons without satisfying M4's held-out competitive-policy gate.

A saved-report comparator now rejects mismatched opponents, deck hashes,
global native-asset hashes, evaluation seeds, game schedules, and altered
outcome summaries before computing a paired score difference. It reproduced
the self-banish child's Tactical comparison with local deck-byte checks.
Older reports still lack full loaded-card-script manifests; see
[evaluation](evaluation.md#self-banish-preference-pilot-27-october-2026).
New policy tournament reports fingerprint the complete Lua script tree and
project/evaluator source, and the comparator enforces matching fingerprints
when present. A two-game native smoke passed with those fields.

An optional Flip-type-aware heuristic ablation increased Flip Control wins from 3/20 to 6/20 on that schedule, but its aggregate score was effectively unchanged and Chaos Control fell from 14/20 to 7/20. Keep the generic heuristic as the baseline while auditing the decision causes on high-play cards.

A visible-stat CombatHeuristicAgent baseline now uses only player-visible field stats and legal actions. On a fresh, both-deck-assignments, three-pair native schedule it scored 54–42 against the original heuristic, with a paired 95% score interval of 52.1–61.5%; see [evaluation](evaluation.md). This is a limited baseline result, not a learned-policy gain. The evaluator now offers both deck assignments explicitly and clusters mirrored assignments together for score intervals, because fixed deck assignments produced misleadingly different head-to-head results. Further deck families and independent seeds remain necessary before promoting this baseline to a demonstration teacher.

A newer balanced six-tournament-deck run put CombatHeuristicAgent at 269–205 with six draws against HeuristicAgent on eight independent seeds, both deck assignments, and both seats. Its paired score interval is above 50%, but the assigned-deck scores range from 26.2% to 81.2%. The pilot reproduced exactly across one and four workers; [the evaluation log](evaluation.md) records hashes, timings, and the per-deck split. Use this as a provisional baseline and demonstration teacher for held-out policy tests, while preserving per-deck evaluation and the historical-rules caveat.

## M4 — Learn a competitive policy

**Status: in progress.** A PyTorch policy scores variable-length legal action sets from visible observations, and behavioral cloning fits replay-verified fingerprinted trajectories into versioned checkpoints. Feature version 2 distinguishes multi-target choices by visible target location even when IDs are hidden; version 3 uses field-slot memory of publicly known facedown opponent cards; version 4 encodes disabled zones and multi-zone choices; version 5 separately pools the player's initial Main Deck composition; version 6 distinguishes Attribute, number, and card-name announcements; version 7 distinguishes ordered card choices; version 8 encodes visible current monster stats and counter counts; version 9 separately pools publicly known opponent hand cards from schema v17; version 10 encodes public chain links in resolution-relevant order; version 11 is an equal-capacity unordered-chain ablation; version 12 binds direct and multi-card field choices to the visible card and current stats at each selected slot, with no additional parameters. Old checkpoints retain their versioned encoders. Demonstrator-seat metadata filters heuristic or self-recorded CLI-human decisions after full-duel verification. The checkpoint evaluator runs paired, seat-swapped tournaments on seeds excluded from training and supports direct checkpoint opponents. A heuristic-imitation baseline won 15/16 versus RandomAgent and 9/16 versus HeuristicAgent on held-out vanilla-fixture seeds; a version-2 retrain matched these results. Direct version-2 versus version-1 evaluation on experimental control/Chaos decks was 17/32, an inconclusive result with unaudited rules and visibility. Initial terminal-reward self-play from random imitation and two runs from the heuristic baseline did not demonstrate a greedy-policy strength gain. Version 5 was trained on one random-play Ground Collapse fixture and evaluated on held-out seeds: 11/16 versus RandomAgent and 7/16 head to head versus version 4; version 4 scored 14/16 versus RandomAgent on the same schedule. This does not show a gain from the Deck feature. Version 6 has no competitive result yet. A matched schema-v17 sourced-deck comparison gave feature version 9 an 18/32 head-to-head result against feature version 8, with equal exact teacher agreement on the 229 held-out known-hand decisions that had multiple options. The interval includes 50%, so no strength gain is established. On separately held-out Chaos Return and Warrior deck files, the same models split 16–16, with a strong 4/16 versus 12/16 deck-assignment split; an exact training-deck file-hash gate supports those saved checkpoints. New checkpoints also record order-independent Main Deck composition hashes and can use a stricter opt-in unseen-Main-Deck gate. See [the evaluation log](evaluation.md). No authorized tournament-human training set, robust held-out competitive result on audited deck families, or strength claim exists yet.

The new sourced 2005 Phoenix Control holdout passed native deck and replay
checks. On Phoenix versus Dimension Fusion, the six-deck continuation beat its
four-deck parent 56–40 directly over 96 paired games, but lost more often than
the parent against Tactical v14 on a separate 64-game schedule (15–49 versus
23–41). The deck split also varied sharply. Keep the child experimental and
require cross-deck baseline gains before promotion; see [evaluation](evaluation.md).

Multi-duel PPO can now collect frozen-policy native rollouts in opt-in CPU
worker processes with seed-scoped sampling. A measured eight-game run was
1.23× faster with four persistent workers than with one, while model tensors
and replay content matched exactly. This improves training throughput, not
competitive strength; see [evaluation](evaluation.md).

A 64-duel, four-role continuation with parallel PPO, per-deck baselines,
per-episode weighting, and parent KL produced 33,341 replay-verified native
decisions. On unseen Phoenix/Dimension Fusion decks, it scored 44–50–2
directly against the parent over 96 games. Both scored 16–48 against Tactical
on a separate 64-game schedule. Do not promote this child; prioritize
stronger decision feedback or a validated value signal over more of the same
terminal-reward updates. See [evaluation](evaluation.md).

A versioned, visible-state critic experiment added public monster stats,
separate player pools, visible zone counts, and the learner's initial Main
Deck. Its first 16-game holdout MSE was slightly lower than the old critic's,
but its independent 32-game MSE was higher (1.094 versus 0.894). Keep the
original critic as the default; neither value architecture has a validated
competitive benefit. See [evaluation](evaluation.md).

A feature-version-10 checkpoint trained on the same 4,630 sourced teacher decisions as version 9 won 20–11 with one draw in 32 paired duels on separate Chaos Return and Warrior deck files. Its held-out chain-decision teacher agreement was 116/135 versus version 9's 114/135, while its overall agreement was two choices lower. Feature version 11 now supplies an equal-capacity unordered-chain GRU control. Ordered version 10 scored 16–15 with one draw against it on a fresh 32-duel schedule, and matched one more of 135 held-out multi-option chain decisions. This does not establish a chain-order strength gain; repeat the comparison across deck families and training seeds. See [the evaluation log](evaluation.md) for protocols and intervals. M4 remains open.

On another sourced Chaos Control/Warrior schedule, ordered version 10 split 16–16 against the unordered control and won 17–15 versus version 9. A same-seed HeuristicAgent control favored Warrior 24–8, revealing a large deck effect. The [evaluation log](evaluation.md) has the deck and seat splits. M4 still needs improved held-out play across decks, with audited full-deck rules.

A feature-version-8 checkpoint trained on 6,999 replay-verified heuristic decisions from the sourced Goat Control/Chaos Turbo decks improved held-out teacher-action agreement on decisions with alternatives, but split 16–16 against the vanilla-trained version-2 checkpoint and won only 18/32 versus RandomAgent on separate seeds. The [evaluation log](evaluation.md) records the direct comparison and deck asymmetry. M4 remains open: imitation accuracy has not produced a measured strength gain.

An additional held-out Warrior-versus-Chaos check yielded 14/16 for that checkpoint against HeuristicAgent, but Warrior also won 13/16 when both decks used HeuristicAgent. The deck effect prevents a strength or generalization claim from this sample. Continue the competitive-card ruling audit before expanding training claims; details and reproduction commands are in the [evaluation log](evaluation.md).

The sourced-deck self-play schedule now covers both learner seats per matchup. A 16-game REINFORCE-style update from the sourced imitation checkpoint replay-verified four deck/seat trajectories but won only 17/32 directly against its parent on fresh paired seeds, with no changed choices on the separate held-out action audit. M4 remains open; see [the evaluation log](evaluation.md).

An opt-in four-role schedule now covers both decks in both learner seats from
one listed matchup, avoiding reliance on a separately listed reverse pairing.
Four native smoke duels all terminated; their 5,110 decisions replay-verified
and passed the visibility audit. This is schedule coverage, not evidence of a
self-play strength gain; see [evaluation](evaluation.md).
The first larger four-role run completed 64 verified training duels across
four decks but scored 42–54 against its parent over 96 held-out direct games,
with particularly weak Chaos Control and Flip Control assignments. Keep that
child experimental. Further terminal-reward updates should not be promoted
without a new variance-reduction or value-learning test and cross-deck wins;
see [evaluation](evaluation.md).

A fresh feature-version-12 behavioral clone was trained on 3,812 replay-verified CombatHeuristicAgent decisions from eight sourced-deck duels, with explicit teacher provenance and exact tensor reproduction on a repeat CPU run. Held-out multi-option action agreement improved by eight choices over the older version-12 checkpoint, but the new policy split 16–16 against its teacher and scored 16–13 with three draws against that checkpoint on unseen Main Decks, both deck assignments, and fresh seeds. Both paired score intervals include 50%; no learned playing-strength gain is established. See [evaluation](evaluation.md).

The combat-clone checkpoint also underwent two snapshot-pool self-play runs. Sixteen default-temperature and 32 temperature-2 training duels all produced replay-verifiable full trajectories; the learner used each of the two training decks equally. On unseen-deck, both-assignment head-to-head tests against its parent, the children scored 16–16 and 17–15 respectively, with intervals including 50%. A held-out action audit found zero and one changed choices out of 745 multi-option decisions. Exploration temperature is now applied consistently during sampling and policy updates, but these experiments do not establish a self-play strength gain; see [evaluation](evaluation.md).

**Work:** Implement a PyTorch policy that scores variable-length legal actions from visible observations. Establish random and heuristic baselines first. Train behavioral cloning on verified demonstrations, then self-play with a historical checkpoint pool and held-out deck families. Compare PPO or other algorithms on win rate and stability rather than selecting one in advance.

**Exit:** A versioned model beats the baseline agents over held-out seeds and decks with confidence intervals, and its decisions use no hidden engine state. Record training compute, data provenance, and evaluation protocol.

A larger 9,117-decision combat-teacher clone trained from 16 freshly replay-verified Goat Control/Chaos Turbo duels improves held-out staple-decision agreement and wins a 64-game direct match against its smaller parent 37–25 with two draws on unseen Chaos Control, Chaos Return, and Warrior Main Decks. Its matched score improvement over the parent against CombatHeuristicAgent is positive on eight held-out seeds, but its absolute combat-teacher score is 30–32 with two draws and its original-HeuristicAgent score is 32–31 with one draw. Both absolute heuristic intervals include 50%; M4 remains open. See [the evaluation log](evaluation.md) for the full schedule, intervals, and ignored checkpoint provenance.

A 64-game self-play continuation from that larger clone produced 64 replay-verified trajectories (50,620 decisions), but scored only 32–31 with one draw directly against its parent on held-out deck families and changed just one of 1,454 multi-option decisions in the separate teacher audit. This does not satisfy M4's strength-gain gate. An opt-in feature-v14 policy can now encode public chain target slots from schema-v21 trajectories; a matched held-out comparison found no demonstrated target-specific or strength gain, so the default remains v10. The cloning trainer now supports opt-in optimizer minibatches; a matched held-out comparison measured higher CPU throughput but no established strength gain, so batch size 1 remains the default. Self-play now skips neural inference on forced choices; [the measured shortcut](evaluation.md#forced-choice-inference-shortcut-27-october-2026) covers one recorded decision set and does not establish whole-training throughput. The next priority is source-backed interaction coverage for the high-play GOAT staples listed below, followed by stronger held-out policy evaluation; see [the evaluation log](evaluation.md).

The cloning trainer also supports opt-in extra exposure to decisions involving selected high-play cards. A matched experiment on ten shared GOAT staples improved held-out multi-option teacher agreement by 12/947 decisions but split a 32-game direct match 16–16 against the unweighted clone. Keep ordinary sampling as the default and use competitive results, rather than teacher agreement alone, to judge this approach; see [the evaluation log](evaluation.md).

The REINFORCE self-play trainer now supports an opt-in batched update for
supported policy versions. On 211 recorded decisions, a batch of 16 measured
3.72–3.78× faster update CPU time than the scalar path with nearly equal loss
and parameters. This speeds optimization, not policy sampling or competitive
strength; [the benchmark](benchmarks.md#batched-reinforce-update) records the
inputs and limits. The scalar path remains the default for prior-run
reproducibility.

Native replay-manifest hashing now reuses digests for unchanged pinned assets
across duels in one process. Four matched policy rollouts gave equal full
trajectories and measured 1.14–1.21× lower whole-duel wall time in two
reversed-order rounds; see [the benchmark](benchmarks.md#native-replay-manifest-hash-cache).
This improves data collection overhead without changing the M4 strength gate.

Parsing the pinned native field summary before location queries now skips
empty zones and reuses public counts. Two order-reversed four-duel schedules
on both probe and sourced decks reproduced identical complete trajectories;
measured whole-duel CPU gains ranged from 1.023× to 1.055×. The gain is small
and does not address the M4 policy-strength gate; see
[the benchmark](benchmarks.md#native-field-summary-observation-queries).

A new feature-v12 clone trained on 10,449 replay-verified CombatHeuristicAgent v2 decisions from four tournament Main Decks was checked against its teacher and an older two-deck clone on unseen Chaos Control and Chaos Return decks. It scored 12–20 against the teacher and 34–30 directly against the older clone on separate balanced schedules; both direct-score intervals include 50%. Held-out multi-option teacher agreement improved by only 5/718. The broader data did not demonstrate a competitive gain or satisfy M4; [the evaluation log](evaluation.md) records checkpoints, hashes, and schedule details. Future policy work should use the six-deck baseline and per-deck splits to judge practical strength, not training loss or teacher agreement alone.

An opt-in feature-v15 encoder now supplies public field and pile counts to
test whether pooled card embeddings were losing board-size information. On
the same four-deck demonstrations, it matched 681/718 held-out multi-option
teacher choices against v12's 687/718, then scored 13–18–1 directly against
v12 on unseen Chaos Control/Chaos Return Main Decks. This negative pilot is
documented in [the evaluation log](evaluation.md); keep the default model
unchanged and do not count it as the M4 strength exit.

A targeted feature-v16 branch from v12 adds only public attack margin and
visibility to offered attack actions. It reduced held-out attack-versus-Main-2
teacher mistakes from ten to three. An independent 128-game match favored
v16 over v12 (79–48–1; paired interval above 50%), and held-out tournaments
favored v16 over RandomAgent and HeuristicAgent. A 256-game match against the
stronger CombatHeuristicAgent scored 139–114–3, but its paired interval still
includes 50% and the Chaos Control split was below 50%. See [evaluation](evaluation.md).
The M4 exit remains open pending stronger cross-deck competitive evidence and
a demonstrated self-play gain.

A 64-seed feature-v16 snapshot-pool continuation completed 62 replay-verified
training duels and censored two that exceeded 10,000 decisions. Its held-out
128-game direct match against the parent scored 62–66, with a paired interval
crossing 50%; the Chaos Control split worsened. The trainer can now record
over-cap games separately without assigning them a terminal reward or losing
the other completed updates. See [evaluation](evaluation.md). This does not
satisfy the self-play gain gate.

Schema v22 now carries the acting player's own attacker slot during target
selection, and an opt-in feature-v17 clone can compare that attacker's public
ATK with visible target stats. On 16 held-out teacher target choices it matched
15 versus v16's 13, but a 128-game held-out direct match scored 68–59–1 with a
paired interval crossing 50% and a weaker Chaos Control split. Keep v17
experimental and continue measuring competitive strength; see
[evaluation](evaluation.md). This does not close M4.

Schema v23 adds the public turn owner to observations and trajectories, and
feature v19 exposes that distinction to a policy without revealing private
state. A replay-verified smoke run proves collection, training, and inference
work end to end; it does not meet the M4 competitive gain gate. Next, collect
authorized and reviewed timing decisions, then compare v19 against a matched
parent across held-out decks and seeds. See [evaluation](evaluation.md).

The combat teacher's attack-target preference now applies to the engine's
`battle_start` target prompts as well as `battle_step`. This is teacher
version 3; prior demonstrations remain labeled version 2. The next data
collection should use version 3 on common GOAT decks, with a fresh held-out
competitive comparison before replacing any policy checkpoint. See
[evaluation](evaluation.md).

That collection and comparison are now complete. All 32 competitive-deck v3
teacher duels and four held-out duels replay-verified. A matched feature-v17
clone matched all 16 held-out teacher attack-target choices, then scored
72–56 against the v2 clone in 128 direct games. The paired interval includes
50% and Chaos Control worsened, so v17 remains experimental and M4 stays
open. Next work should improve cross-deck consistency and test a distinct
self-play update on unseen decks; see [evaluation](evaluation.md).

The v3 clone's 64-game snapshot-pool continuation now replay-verifies all
44,056 decisions after the adapter accepted a 3,003-way Return from the
Different Dimension selection. The child scored 64–62–2 against its parent
in 128 held-out direct games, with a paired interval including 50% and a
weaker Chaos Control split. This is a completed negative self-play pilot,
not the M4 strength exit. `MSG_SELECT_CARD` prompts above 4,096 complete
combinations now use staged linear-size actions; native Graceful Charity and
Thunder Dragon regressions check that boundary, and a local Return replay
matched its flat native result. Other request types may still exceed their
bounds; see [evaluation](evaluation.md).

An enlarged feature-v17 v3 clone trained from 64 replay-verified synthetic
teacher duels (21,799 teacher decisions) matched two more of 611 held-out
multi-option teacher choices than the 32-duel parent, but scored 57–68–3
directly against that parent over 128 games on unseen Chaos Control/Chaos
Return Main Decks. The paired interval includes 50% and the Chaos Control
split is much worse. This negative pilot argues against simply adding more
same-deck teacher games; investigate source-aware target choices and broader
cross-deck evaluation before another promotion. See [evaluation](evaluation.md).

The Thunder Dragon zero-copy search is a legal cancel response in the native
GOAT script. Policy inference version 3 now permits it once per distinct
visible prompt while guarding retries. Both saved combat clones recover two
held-out teacher choices; a small native smoke run completed. Continue with
other high-play cards and their interaction paths before treating clone
agreement as competitive strength. See [evaluation](evaluation.md).

An opt-in feature-v18 pilot paired the active public chain card with each
candidate action card, targeting Metamorphosis and other effect-choice errors.
It matched fewer held-out teacher actions than matched feature v17, including
both motivating Thousand-Eyes Restrict choices. Its 34–29–1 direct score on
64 unseen-deck duels has an interval spanning 50%, so it is not promoted.
Future policy work should inspect source/target labels and broader deck
coverage before adding more relation layers. See [evaluation](evaluation.md).

The later seed-6803 v9 replay exposed ineffective open Main Phase guards:
Chaos Sorcerer could still banish itself and Breaker could spend its counter
on its controller's Trap. Tactical v10 closes those cases, holds the reviewed
premature Book of Moon, and limits unhelpful battle-position changes. The
same-seed v10 replay passes native verification and visibility checks. In a
small direct 32-duel comparison it scored 18–14 against v9, with a paired
interval including 50%; broader validation remains necessary. A separate
21-preference training pilot improved reviewed choices but scored 31–32–1
against its parent on two held-out matchups, so it was not promoted. See
[replay audit](replay_audit.md) and [evaluation](evaluation.md).

A matched 32-game snapshot-pool self-play pilot compared learning rates
0.001 and 0.0001 on the same four high-play-deck pairings and seeds. All 64
training trajectories replay-verified and passed the visibility audit. Both
children scored 32–32 against their parent on an unseen Chaos Control/Chaos
Return schedule; their direct match also split 32–32. A second unseen guide
deck matchup gave the higher-rate child 32–30–2, with a paired interval
including 50%. The higher rate corrected two held-out Restrict target
choices and regressed on two others, leaving teacher agreement unchanged.
Update size alone has not met M4's self-play gain gate; see [evaluation](evaluation.md).

An opt-in learner-deck reward baseline was compared with the existing global
baseline in 32-game matched snapshot-pool runs on four common tournament
decks. Their 64 replay-verified trajectories contained identical actions,
and the two children split 31–31 with two draws on unseen Chaos Control and
Chaos Return lists. Both had identical 35–28–1 outcomes against the parent
on another held-out schedule, with a paired interval including 50% and a
large assigned-deck split. Per-deck reward centering alone has not met M4;
see [evaluation](evaluation.md).

The cloning input selector now filters legacy `self_play_rl` trajectories by
their recorded learner seat and rejects missing or contradictory seat metadata.
New self-play recordings include the explicit demonstrator seat. A 64-duel
legacy corpus check excluded 20,940 opponent decisions that would otherwise
have been mislabeled; a native replay and cloning smoke test confirmed the
corrected path. This repairs training-data provenance without claiming a
policy strength gain; see [evaluation](evaluation.md).

An opt-in public-Flip-type combat teacher now tests the missing Flip Summons
seen in the sourced-deck action audit. On a six-duel replay-verified probe it
selected Dekoichi Flip Summon five times versus one for the current teacher,
and Magician of Faith six times versus zero. A separate 32-game held-out
direct match scored 14–17–1 with a paired interval crossing 50%; the
candidate stays experimental and the default teacher remains version 3.
See [evaluation](evaluation.md) for the schedule, hashes, and reproduction
commands.

The feature-v17 v3 checkpoint was also tested on four exact published 2005
Main Decks absent from its training provenance. It scored 14–18 against
CombatHeuristicAgent v3 and 17–15 against HeuristicAgent on separate balanced
32-game schedules; both paired intervals include 50%. Cas Flip Control had a
weak split even when the same heuristic played both sides against Jesse Goat
Control, so the small Cas-specific policy split does not isolate a model
defect. Four replay-verified Cas-versus-Jesse teacher duels provide a held-out
card-choice audit, but synthetic teacher agreement remains only a diagnostic.
See [evaluation](evaluation.md). M4 remains open.

An opt-in warm-start clone now continues compatible weights while preserving
all parent and new training-game provenance for held-out evaluation. Training
on four 2005 Cas/Jesse synthetic-teacher duels did not improve the feature-v17
policy on unseen Matt/Daryl decks: parent and child both scored 6–9–1 against
the same combat teacher, and the child scored 15–17 directly against its
parent. The experiment and its deck splits are in [evaluation](evaluation.md).
M4 remains open; more 2005 data alone has not yet produced a measured gain.

Feature version 19 adds the public turn owner to the observation encoder.
In a matched 6,014-decision TacticalHeuristicAgent v3 cloning experiment,
it scored 30–33–1 directly against feature 18 over 64 unseen-Main-Deck
duels. Its held-out Scapegoat-offered agreement improved from 17/20 to
19/20, but total teacher agreement fell slightly and no held-out Scapegoat
End Phase opportunity occurred. Keep the feature opt-in. Next collect
replay-verified demonstrations that actually include both own-turn and
opponent-turn End Phase Scapegoat choices, then test timing agreement and
paired strength on separate seeds and decks. See [evaluation](evaluation.md).

A replay-verified scripted Scapegoat probe now supplies three explicitly
synthetic End Phase labels. An overfit warm-start learned the probe's later
opponent-turn activation and repeated it on four new shuffle seeds, but its
69–59 head-to-head result against the parent on unseen decks has a paired
interval spanning 50% and large deck splits. Keep the child experimental.
Collect authorized skilled-player timing decisions or broader marked
synthetic scenarios, then test a training method that retains strength
across Chaos and control decks; see [evaluation](evaluation.md).

Mixed rehearsal now supports verified tactical decisions and separately
annotated synthetic timing decisions in one run, with explicit source
weights and a guard against unannotated scripted filler. Two source-weighted
rehearsals still passed at the target End Phase. Restricting a three-label
update to the state-number encoder and scorer learned the timing probe but
lost 8–56 against its parent on unseen Main Decks. Keep both approaches as
negative experimental results; the next M4 step is a broader decision corpus
and a measured stability method, not promotion of the probe-fitting policy.

A frozen-parent KL experiment now supplies one measured stability method:
it fit the Scapegoat timing probe and split 66–61–1 against its parent over
128 unseen-Main-Deck games, with a paired interval spanning 50%. Teacher
agreement where Scapegoat was offered fell from 19/20 to 13/20, and Chaos
deck assignments remained weak. Keep it experimental. Next obtain more
independent positive and negative timing examples, then measure both
card-specific calibration and deck-balanced strength before promotion.

Published 2005 deck probes now provide 19 explicitly synthetic Scapegoat
choices per duel, including early passes and a later opponent End Phase
activation. Training on Cas and Matt transferred the final timing choice to
Jesse, but the weighted child scored 29–35 against its parent on unseen
Main Decks and still activated prematurely during one held-out opponent
Main Phase. The next data pass should add independent threat and no-threat
board contexts and authorized expert examples where available; evaluate
Scapegoat calibration and win rate together. See [evaluation](evaluation.md).

An opt-in visible-state guard now rejects Sakuretsu Armor under face-up Royal
Decree. A separate `policy_review` annotation source lets reviewers correct
checkpoint-attributed policy decisions without misclassifying them as human
demonstrations. Five such choices transferred to fixed Scapegoat states, but
the child split 31–32–1 against its parent in 64 unseen-Main-Deck games.
The verified replay shortlist found one clear Heavy Storm resource error in
eight additional games. An extended player-visible review now also finds three
weak Magician of Faith summons with a Set option, two Tribe activations without
a face-up enemy, and one Tribe Type choice that destroys two own Spies instead
of four opposing Sheep Tokens. These are review prompts, not training labels;
see the [replay audit](replay_audit.md). Scapegoat timing prompts still need
contextual review. Prioritize independent high-quality decision data and
cross-deck play gains; neither the guard nor review-fit child closes M4.

A versioned experimental guard v4 substitutes a Set when the guarded policy
would Normal Summon a low-ATK Flip monster, preserving plausible visible direct
lethal. It corrects three saved Magician of Faith choices, but scored 23–25
against guard v3 in 48 direct held-out duels. The [evaluation log](evaluation.md)
records the paired report and a replay-verified full duel. Do not promote v4
as a strength improvement on these data.

An independent replay review found two Black Luster Soldier self-banishes and
one Mystical Space Typhoon choice destroying an own Set Solemn Judgment despite
legal opposing targets. An opt-in guard v5 changes those fixed-state targets
and replay-verifies as a full-duel policy, but scored only 25–23 against v3 on
the same 48-game held-out schedule, with an interval including 50%. Keep it
experimental. The next M4 step remains broader high-quality target and timing
examples with cross-deck strength measurement, including effect activation
choices as well as target choices; see the [replay audit](replay_audit.md).
An eight-label, four-replay scorecard now verifies reviewed alternatives and
reports their raw checkpoint ranks and margins. All eight alternatives rank
below the unchanged feature-19 policy's recorded choice; this gives future
updates a fixed-state diagnostic, not a substitute for held-out duels.
An eight-label parent-KL child fit six of those eight decisions but scored
99–91–2 against its parent over 192 direct games on four unseen Main Deck
compositions. Its paired interval includes 50%, and the Bazoo Return and
Chaos Turbo splits diverged. Keep the child experimental and prioritize
independent, diverse target/timing demonstrations before more fine-tuning;
see [evaluation](evaluation.md).

A matched 64-game visible-state value-baseline run completed and replay-verified
49,531 decisions. On three unseen deck families, it split 49–46–1 directly
against the scalar-baseline self-play child and lost 44–52 to their unchanged
parent. Neither comparison meets M4's strength-gain gate. The sampled
self-play audit also found recurring own-card removal and weak Flip summons;
these are exploration choices, not proof about greedy checkpoint preferences.
Prioritize visible activation and target valuation, independently reviewed
decision data, and a fresh held-out schedule before another checkpoint
promotion; see [evaluation](evaluation.md) and [replay audit](replay_audit.md).

An opt-in four-review preference update with frozen-parent KL improved the
reviewed action margins but still ranked setting Magician of Faith fifth in
its training state. Its held-out 96-game score against the unchanged parent
was 49–47, with a paired interval spanning 50% and poor Chaos Control and
Flip Control splits. Keep the parent as reference. Expand independent review
coverage across decks and effects before another preference fit; evaluate on
new seeds and compositions, not the four training decisions. See
[evaluation](evaluation.md).

A replay-bound Tribe-Infecting Virus review identified a feature-19 Type-mask
scaling fault: the policy nearly tied Spellcaster, Aqua, and Beast despite
their very different visible consequences. Opt-in feature version 20 encodes
the 64 Type bits exactly and keeps older checkpoints readable. A same-data
feature-20 clone scored 42–53–1 against feature 19 on 96 held-out duels. A
five-review parent-KL child corrected the Tribe training state but split
49–47 against its feature-20 parent on another 96 held-out duels, with severe
Flip Control weakness. This improves action representation and diagnosis,
but does not close M4's competitive gate. Schema-v24 current-Type observations
now support opt-in feature version 21, which relates a declared Type to the
count and ATK of matching face-up monsters on each side. A one-game same-data
feature-20/21 training smoke test completed. A larger same-data clone on
2,459 teacher decisions ranked the separately reviewed Beast choice first
with feature 21 versus second with feature 20, but its 64-duel held-out,
seat-swapped match ended only 33–31 for feature 21 with a paired interval
crossing 50% and large deck splits. Add diverse Type/target reviews, compare
fresh seeds and additional training runs, and require consistent cross-deck
improvement before promotion; see
[evaluation](evaluation.md).

A fresh feature-21 replay again exposed a weak Magician of Faith Normal
Summon where setting that same card was legal and its Flip effect had useful
Spell targets. One reviewed preference corrected the child checkpoint's
ranking at that frame, but the child scored only 31–29–4 against its frozen
parent in 64 held-out, seat-swapped duels, with a paired interval crossing
50% and large deck splits. Keep the parent as reference. Collect diverse
independent Flip-monster decisions and test whether corrections transfer
across decks before promoting another checkpoint.

Two further feature-21 policy replays supplied independent Faith Set
preferences, and one supplied a player-visible Ring target correction from
own Faith to opposing Chaos Sorcerer. A four-review parent-KL child ranked
all four preferred actions first at those fixed frames, yet scored only
31–32–1 against its frozen parent on 64 fresh, unseen-composition duels;
Flip Control and Goat Control splits were weak. This supports adding generic
Flip-effect readiness and Spell-in-Graveyard context to action scoring before
another update. Keep the parent as reference and use a new held-out schedule
for any feature experiment; see [evaluation](evaluation.md).

Feature version 22 now encodes pinned printed Flip/ATK properties and public
resource counts. A same-data clone moved preferred Faith/Ring actions higher
at four reviewed frames, but its two 64-duel unseen-composition comparisons
with feature 21 scored 36–27–1 and 28–34–2, with severe role dependence.
Do not promote it from these results. Player review of seed 3900 added two
Thunder Dragon preference labels: the policy used Pot before an available
Thunder search and then voluntarily selected zero of two available copies.
The replay audit can now inspect the opponent seat separately; this revealed
that TacticalHeuristicAgent v4, not the learned policy, self-targeted Black
Luster Soldier and negated Scapegoat with Solemn Judgment. Tactical v5
addresses those visible cases, but its broader strength is unmeasured.
Next, train on more independent reviewed decisions and add public context for
control-change and summon-response value before any promotion claim.

An additional strict unseen-Main-Deck evaluation of the feature-v23 tactical
clone on Jesse/Michael 2005 Goat Control, Warrior, and Chaos Return pairings
scored 16–32 against Tactical v7 over 48 seat-swapped duels. Applying the
optional tactical and weak-Flip guard scored 18–30 on the same schedule; the
paired difference interval spans a loss and a gain. A complete replay in that
schedule confirms the unguarded policy still Normal Summoned Magician of Faith
with a legal Set available. See [evaluation](evaluation.md). M4 remains open;
collect independent reviewed decisions and demonstrate a cross-deck strength
gain before selecting a default inference correction.

A 64-game on-policy Tactical v14 imitation expansion raised exact held-out
teacher agreement to 1,136/1,292 but scored only 13–51 against Tactical on
the tested unseen deck schedule. Oversampling response decisions improved
chain/pass agreement on recorded states yet split 32–32 with the unweighted
clone on fresh complete duels. See [evaluation](evaluation.md). M4 remains
open; future training changes must improve held-out game outcomes.

A separate 64-duel Tactical-v14 demonstration continuation on four previously
unseen training decks did improve held-out outcomes: **43–21** directly against
the unchanged neural parent, and **25–39** against Tactical-v14 versus the
parent's **13–51** on a matched 64-duel schedule. One Dimension Fusion list
split 8–8 against the parent, and the child still loses to Tactical overall.
Keep the checkpoint experimental until independent deck families and self-play
improvement are demonstrated; see [evaluation](evaluation.md).
One 64-duel PPO continuation from that checkpoint scored 27–37 against its
unchanged imitation parent on fresh held-out seeds. All training duels replay-
verified and passed the visibility audit, but sampled actions still included
many visible resource-loss candidates. Keep the self-play gate open and test
credit assignment or better sampled-action quality before promotion.
A matched attempt to sharpen sampled actions by lowering PPO rollout
temperature from 1.0 to 0.5 failed to terminate seed 21211 even after raising
the decision cap from 3,000 to 10,000. It yielded no checkpoint or strength
claim. The process-worker cap error now reports its seed correctly; see the
[evaluation log](evaluation.md).
Labeling 7,538 decisions from the fixed imitation checkpoint's own games
with Tactical-v14 and upweighting 1,891 disagreements also failed a held-out
strength check: the child scored 30–34 directly against that checkpoint and
16–47–1 against Tactical-v14 versus the parent's 20–44. More synthetic
teacher agreement alone is insufficient; prioritize independently reviewed
action value and outcome-sensitive learning signals.

## M5 — Search and other formats


Evaluate policy-guided search and belief sampling only after M2 and M4. Search must sample hidden information from a player-consistent belief and must never inspect the real hidden state when choosing actions. Add Edison as a separately validated rules profile, not a changed banlist.

The [Edison feasibility audit](edison_research.md) records the official March
2010 Advanced Format restrictions as a checked data asset and lists the
remaining card-pool, native-rule, and observation validation gates. This is
M5 preparation; Edison duels are not yet supported.
The pinned core's MR1 mode now has a separate vanilla-only startup probe and
complete-duel adapter. The seed-42 Normal Monster fixture completes 1,368
decisions through the common environment, then replay-verifies and passes the
visibility audit. This is an MR1 protocol result, not an Edison duel: the
2010 release pool, restrictions, effect scripts, Synchro actions, and historical
rulings remain open.
An isolated Junk Synchron/Junk Warrior fixture now also exercises one Level 5
Synchro line under MR1. The native core offers the Extra Deck action and moves
both selected materials to the Graveyard; the complete 1,439-decision duel
replay-verifies and passes the visibility audit. The fixture uses a tiny sourced
card subset and modern pinned scripts. It does not validate all 2010 Synchro
rulings, effect text, or Edison legality; see [the Edison audit](edison_research.md).
Paired Junk Warrior ATK fixtures now distinguish a surviving friendly Level 2
monster (+500 ATK) from an opposing one (+0). Their complete 1,202- and
1,592-decision duels replay-verify and pass the visibility audit. A photographed
February 2009 printing confirms the "you control" wording, which differs from
the 2008 first printing. This validates that specific printed-text distinction,
not the broader 2010 rules profile; see [the Edison audit](edison_research.md).
A second sourced MR1 fixture now Synchro Summons Black Rose Dragon from Junk
Synchron and a Level 4 Normal Monster. Accepting or declining its optional
field-wipe trigger produces different verified board outcomes; both complete
duels replay-verify and pass the visibility audit. The narrow probe applies
the March 2010 one-copy restriction for Black Rose Dragon. This expands
Synchro protocol coverage without establishing a complete 2010 rules profile
or release pool; see [the Edison audit](edison_research.md).
An independent 2009 deck-construction validator now accepts an explicitly
audited eligible-card set and checks Main, Extra, and Side sizes, Fusion/Synchro
placement, and shared canonical copy caps. It deliberately does not infer
release eligibility from the restriction list; the complete dated card pool
and native 2010 rules profile remain open.

### Possible Stardust PC-port integration

Keep training in Python. Define a versioned, game-independent decision boundary: the game supplies a player-visible observation and legal actions; the agent returns an action identifier. When Stardust exposes those decisions in a PC port, implement a small C or C++ bridge and native model inference. Stardust's 2009 rules, card IDs, and action protocol need their own adapter and validation; GOAT checkpoints should not be assumed directly compatible. This is future work and does not block the GOAT milestones.

## Immediate next work item

Prioritize M1 and M2 card work by competitive relevance. Use the sourced [Goat Control](../examples/decks/goat_control_lolmarcus_2020.ydk), [Chaos Turbo](../examples/decks/chaos_turbo_riclar_2020.ydk), [Warrior](../examples/decks/warrior_montague_clash.ydk), [Chaos Control](../examples/decks/chaos_control_insids_worlds_2022.ydk), [Chaos Return](../examples/decks/chaos_return_dingosig_worlds_2022.ydk), and [Bazoo Return](../examples/decks/bazoo_return_weirdchamp_worlds.ydk) tournament lists, plus the [Flip Control](../examples/decks/flip_control_goatformat_guide.ydk) guide list, as the first concrete corpus. The Bazoo Return Main Deck is transcribed from [Weirdchamp's published sixth-place World Championship list](https://www.goatformat.com/bazoo-return.html). The Flip Control list is a guide example. These six tournament lists are still too few to estimate metagame frequency. In the original five-list corpus, Breaker, Delinquent Duo, Snatch Steal, Pot of Greed, Nobleman of Crossout, Book of Moon, Black Luster Soldier, Heavy Storm, Ring of Destruction, and Graceful Charity each appeared in all five. This remains a coverage priority for fixtures, not a population play-rate estimate.

A [seeded action-coverage probe](competitive_action_coverage.md) now counts offered and selected card-source decisions across six complete native duels from those deck files. Use it to identify exercised decision paths and missing fixture coverage; its random-agent counts are not metagame usage rates or historical correctness evidence. As one concrete staple matchup, Nobleman appears twice in each of the five tournament Main Decks and Gravekeeper's Spy appears three times each in Chaos Turbo and Chaos Return; a native fixture now checks Nobleman removing a set Spy before its Flip Effect can recruit.

A paired Nobleman fixture also checks a set non-Flip Kycoo against a set Flip
Dekoichi with three copies of either card in the defender's Deck. The attacker
cannot distinguish them at target selection; only the Flip branch removes
matching Deck copies and reveals Decks. Both complete duels replay-verify.

A Metamorphosis fixture now checks the historical option to Tribute the
player's own face-down Level 1 Dark Mimic for Thousand-Eyes Restrict, without
triggering Mimic's Flip draw. With no matching Fusion in the Extra Deck,
Metamorphosis is unavailable. The successful branch completes and
replay-verifies. A paired Soul Exchange fixture now confirms the distinct
restriction: an opposing face-down Dark Mimic cannot pay Metamorphosis's cost,
while a face-up opposing Mimic can. The pinned modern script required a
SHA-guarded, in-memory historical correction; both full duels replay-verify.

A tournament-described Goat Control line now activates Scapegoat in the
opponent's End Phase, confirms its Summon restriction ends with that turn,
and Tributes a Sheep Token for Metamorphosis on the controller's next turn.
The full seeded native duel replay-verifies. See [GOAT rules](goat_rules.md).

A 2005 tournament-described Snatch Steal / Tsukuyomi line now has a pinned
native fixture: Tsukuyomi Sets the stolen monster, Snatch leaves the field,
the stolen monster can be Flip Summoned after the chain closes, and it remains
with the Snatch player on the opponent's next turn. The defender's hidden view
and remembered field identity are checked. The complete duel replay-verifies;
Vampire Lord's own effect remains outside this general-rule fixture. See
[GOAT rules](goat_rules.md).

A linked Black Luster Soldier fixture now takes an opponent-Summoned BLS with
Snatch, uses its banish effect, then has Tsukuyomi Set it. After Snatch leaves,
the stolen BLS can be Flip Summoned and banish a second opposing monster that
same turn. The original owner's hidden field view retains only public memory
of BLS's identity. The full duel replay-verifies; see [GOAT rules](goat_rules.md).

A guide-described Tsukuyomi / Nobleman line now Sets an opposing GOAT BLS and
banishes it. The target action names only its field slot, while the acting
player retains public knowledge that it is BLS. Nobleman performs no Flip
monster Deck verification, and the complete duel replay-verifies; see
[GOAT rules](goat_rules.md).

The Chaos boss / Bottomless Trap Hole priority fixture now runs both official
Chaos Sorcerer and the separate GOAT Black Luster Soldier script. For each,
activating its banish effect before the Bottomless response removes the target
after the boss is banished; passing priority leaves the target in play. All
four full duels replay-verify against pinned native assets.

A paired BLS / Ring of Destruction fixture now checks the defender's choice to
destroy their own monster while BLS's banish effect is pending. Ring deals that
monster's current ATK to both players; BLS's target is gone at resolution, so
the monster reaches the Graveyard rather than being banished. Passing Ring
banishes it instead. Both complete duels serialize and replay-verify; see
[GOAT rules](goat_rules.md).

An independent April 2005 list checks the pinned card IDs and copy limits for the 18 cards appearing in at least four of the five tournament Main Decks; the ten shared by all five are pinned as a corpus regression. A read-only comparison matches all 1,679 names in GoatFormat's published card-pool spreadsheet against the pinned whitelist after ten explicit printed-name equivalences. The whitelist has two additional legal names omitted by that sheet, with separate cutoff evidence. A second source-backed audit checks the April 2005 copy limit of all 1,704 pinned whitelist IDs against GoatFormat's 73 named restrictions and finds no mismatch; see [GOAT rules](goat_rules.md). Card-specific historical rulings and release-date membership beyond the independent sheet remain open.

1. Finish interaction and interruption coverage for cards shared by these lists, especially Black Luster Soldier, Nobleman of Crossout, Book of Moon, Pot of Greed, Graceful Charity, and common removal and traps. Existing single-line fixtures are a starting point, not a complete ruling audit.
2. Expand deck-defining lines: Scapegoat, Metamorphosis, Thousand-Eyes Restrict, and Tsukuyomi for Goat Control; Chaos Sorcerer, Gravekeeper's Spy, Dekoichi, and LIGHT/DARK Graveyard setup for Chaos Turbo. Include chains, legal choices, and player-visible information at each decision.
3. Expand Warrior's Reinforcement of the Army audit beyond its tested ordinary, empty, and Exiled Force follow-through searches, Mystic Swordsman LV2 beyond its tested attack on set Dekoichi, Blade Knight beyond its tested hand-size bonus and Dekoichi battle, and Don Zaloog beyond its tested discard/mill, attacked-while-dealing-damage, empty-hand, and Waboku damage-prevention branches. These add high-use decisions absent from the two control/Chaos lists.
4. Cover other cards when they block a representative full duel, expose a general engine or observation defect, or appear in additional sourced competitive decks. Defer isolated low-play card edge cases until the staple paths work reliably.

Use the [SJC Indianapolis 2005 Top 8 card ranking](card_priorities.md) to select the next fixture: common contemporary cards such as Tsukuyomi, Scapegoat, Magician of Faith, Metamorphosis, and Sinister Serpent take precedence over isolated low-use cases. Five legal 40- or 42-card published lists are executable deck fixtures; printed 38- and 39-card lists remain ranking evidence only unless an independently sourced correction is found. For each fixture, record the historical source, native script and rules profile, expected outcome, and any unresolved discrepancy in [GOAT rules](goat_rules.md). Keep implementation changes small enough to demonstrate with a command, test, and documented limitation. Resume strength experiments after the audited deck corpus is broad enough to support meaningful evaluation.

## Next position-decision experiment

The feature-21 replay audit found 12 decisions moving defending 0-ATK Sheep
Tokens into attack. A narrow optional inference guard prevents that pattern,
but a 64-duel comparison against the unguarded identical checkpoint scored
31–33. Keep the guard as an ablation until independently reviewed examples
show when staying in defense is best. Next, label repeated position changes
for non-token monsters with board context and run a held-out, seat-swapped
comparison before changing the default policy. See
[replay audit](replay_audit.md) and [evaluation](evaluation.md).

The first action-conditioned position representation (feature v23) reduced
0-ATK token changes from 12 to 9 on the reviewed replay states but scored
33–30–1 against the v21 reference over 64 held-out duels, with large deck
splits. Do not promote it on this evidence. Collect independent position
labels across several decks and compare both decision quality and match
results before changing the default checkpoint.

A 12-choice Sheep Token preference child fit the reviewed replay and beat its
unchanged policy parent 76–48–4 across two held-out 64-duel schedules, but
its gains were concentrated in Chaos Return and Warrior. Against Tactical
v6 it scored 18–46, only +3.13 percentage points over its parent on a
matched schedule, with an interval crossing zero. It remains experimental;
M4 still needs a policy with measured strength across audited deck families
and a demonstrated self-play gain. The next training-data priority is
independent, high-quality tactical decisions beyond a single replay and card.

A four-deck Tactical-v6 clone now has 5,445 replay-verified teacher decisions
and scored 48–16 against the older learned reference on unseen Main Decks,
but only 14–48–2 against Tactical v6. An opt-in rare-Set sampling run improved
held-out teacher Set agreement from 0/11 to 9/11, yet split 32–32 directly
against the unweighted clone on fresh unseen-deck seeds. M4 therefore stays
open. Prioritize more independent expert decisions and an algorithm that
converts tactical decision quality into match wins; do not use imitation
agreement alone as the promotion gate. See [evaluation](evaluation.md).

### Position-switch correction (October 2026)

A replay review found a second avoidable position pattern besides defending
Sheep Tokens moving to attack: on an empty opposing field, the tactical teacher
repeatedly moved monsters whose ATK exceeded their DEF from attack to defense,
then moved them back on later turns. The visible-state position guard now
filters those switches when another legal action exists. It still allows a
defender to move into attack for a possible direct attack, and it leaves
attack-to-defense choices available when the opponent controls a monster.
TacticalHeuristicAgent is version 7; the optional policy inference mode is
`greedy_position_guard_v2`. Version 1 remains available to audit older replays.

In the single paired seed-3901 replay, policy-seat position changes fell from
6 to 4 and opponent tactical-teacher changes fell from 14 to 6. The former
replay had three empty-field attack-to-weaker-defense choices across both
seats; the new replay had none. Both games were won by seat 1. This is a
behavior regression check, not evidence of improved match strength. The new
visual replay is `replays/fv21_position_guard_v2_3901_p0.json`; both its
683 decisions and the older 721-decision replay passed native replay and
policy-choice verification. Next, run a held-out, seat-swapped tournament
before making the guard a default policy inference mode.

A subsequent same-checkpoint, held-out 128-duel comparison measured a
69–55–4 score for the optional position guard over unguarded inference, but
the candidate split 32–32 in the first seat and its assigned-deck results
varied widely. Against TacticalHeuristicAgent v7 it scored 14–49–1 over
64 further held-out duels. This supports retaining the narrow guard as an
optional behavior correction; it does not meet M4's cross-deck strength or
self-play improvement gates. See [evaluation](evaluation.md) for confidence
intervals, hashes, and reproduction commands.

A fresh 64-duel Tactical-v7 imitation set on the current native assets gave a
feature-v23 clone 21,394 verified teacher decisions. It beat the 16-duel
current-asset clone 59–37 across two 48-game unseen-composition schedules,
but scored only 17–31 against Tactical-v7 on one matched schedule. The gain
is uneven across assigned decks. M4 still needs a policy that beats baselines
with robust cross-deck evidence, plus a separate self-play improvement.

An opt-in frozen-parent KL term was tested in 32-game self-play continuations
of that larger clone. All 64 saved duels replay-verified and passed visibility
checks. The KL child beat an unregularized child 28–20 on one unseen-deck
schedule but lost 21–27 on another; both children scored 25–23 against their
unchanged parent on a matched schedule. Keep the regularizer optional. Neither
child meets M4's self-play strength gate; see [evaluation](evaluation.md).

An opt-in per-decision mean policy-gradient reduction was compared with the
legacy summed update in matched eight-duel native self-play runs. All 16
trajectories replay-verified and passed visibility checks. On held-out decks,
the mean and sum children split 32–32; the mean child scored 33–30–1 against
its parent, with a severe assigned-deck split. No self-play gain is established.
Keep the legacy reduction as default while testing stronger credit assignment
and larger independent training sets; see [evaluation](evaluation.md).

The seed-6803 Matt/Chaos replay audit identified concrete card-value mistakes
and clarified that only Player 2 used Tactical v7; Player 1 used Combat
Heuristic v3. Tactical v8 now corrects several local choices and can be
recorded against itself with `--opponent tactical`. Direct v8-versus-v7
results were 38–25–1 on Matt/Chaos and 40–24 on four different pairings.
The next milestone is a general, visible-state card-advantage model covering
discard costs, removal targets, and backrow commitment. Compare each change
against unchanged v8 across unseen deck compositions and audit fresh replays
for new waste patterns before promoting it to training data. See
[replay audit](replay_audit.md) and [evaluation](evaluation.md).

Seven explicit seed-6803 user reviews can now enter the optional preference
pipeline as `baseline_review`, bound to the replay hash and reviewed seat.
A small parent-KL child changed three greedy fixed-state choices but split
33–29–2 against its parent across two held-out deck pairings. This is useful
feedback plumbing, not the M4 strength gate. Collect more independently
reviewed decisions, including target and resource-cost comparisons, before
another promotion attempt; keep evaluation decks and seeds separate.

The later seed-6803 seat-0 replay review found that both players used Tactical
v8 and exposed repeated own-monster removal, early Thunder Dragon discards,
weak Metamorphosis, and poor Swap and Tsukuyomi targets. Tactical v9 adds
visible-state baseline checks without changing the historical GOAT zero-copy
Thunder Dragon rule. It scored 34–29–1 against v8 on a 64-duel, four-matchup
schedule. M4 still needs trained policy gains on independent decks and seeds;
this heuristic revision does not close that gate. See [replay audit](replay_audit.md)
and [evaluation](evaluation.md).

Subsequent user review found that v10 missed a legal BLS banish of an
opposing Set monster before a Tsukuyomi reset, and that v11 still spent
Book of Moon on its own Chaos Sorcerer in an idle Draw Phase before
discarding to Raigeki Break a Sheep Token. The versioned v11 and v12
baselines correct these fixed decisions. Their separate 32-duel direct
comparisons against the prior version both split 16–16, so neither closes
M4's competitive gate. The reviewed choices are bound to source replay
hashes as baseline preferences; see [replay audit](replay_audit.md).

The v12-versus-v12 seed-6803 replay exposed six additional reviewed resource
and BLS/Thunder Dragon choices. Tactical v13 changes those exact visible-state
decisions and a fresh self-play replay passes full verification. Its first
64-duel direct comparison against v12 scored 34–30, with an uneven assigned-deck
split and a paired interval touching 50%. Keep M4 open: this heuristic change
does not establish cross-deck strength or a learned self-play gain. See
[replay audit](replay_audit.md) and [evaluation](evaluation.md).

The later v13 player review added three resource preferences. A small
parent-KL neural update improved all three pairwise margins but did not make
two preferred actions the checkpoint's top choices. On 128 held-out duels
across four deck pairings, it scored 68–59–1 against its parent, with a paired
interval crossing 50% and severe assigned-deck splits. A second schedule
also uncovered a 10,000-decision select/unselect loop; policy inference v6
now progresses through that native prompt, and the exact seed completes.
Keep the child experimental. Broader independent labels, robust deck-balanced
evaluation, and a separate self-play gain are still required for M4; see
[evaluation](evaluation.md).

Sixteen replay-verified Tactical-v14 demonstrations from four training Main
Deck compositions supplied 3,786 teacher decisions for a feature-v23 neural
continuation. On two independent held-out parent comparisons, that child
scored 79–47–2 over 128 duels (paired-bootstrap score interval 53.9%–70.7%),
but it scored only 12–52 against Tactical-v14 itself on 64 fresh duels.
Continue training and evaluation across more independently sourced decks;
keep the teacher as a baseline, and require a separate measured self-play
gain before closing M4. The [evaluation log](evaluation.md) records provenance,
hashes, deck splits, and exact limitations.

A 32-duel snapshot-pool self-play continuation from that stronger neural
checkpoint replay-verified all 17,103 decisions. On two new unseen-deck
schedules it scored 66–62 over 128 duels against the unchanged parent,
with a paired-bootstrap interval of 43.8%–59.4%. This does not satisfy M4's
self-play strength gate. Keep the imitation checkpoint as the neural reference;
investigate a stronger learning signal and evaluate any change against the
same frozen parent on independent deck families.

An opt-in policy-visited Tactical-v14 label path now checks the source
checkpoint hash and player-visible replay before fitting synthetic teacher
choices. Eight policy-versus-teacher duels supplied 626 multi-option labels,
including 69 disagreements with the policy's executed actions. The child
scored 28–35–1 against its unchanged parent on 64 held-out duels, so it is
not promoted. M4 still needs more capable generalization and a separately
verified self-play gain; see [the experiment](evaluation.md).

A user-reviewed Spirit Reaper position mistake now has an opt-in tactical
Set preference. Its exact replay decision changes as intended, but a 96-duel
comparison scored 52–44 against v14 with an interval touching 50%, so the
default teacher stays v14. That comparison also uncovered a historical
Dark Balter/Sinister Serpent native loop. A source-backed, SHA-guarded
pre-errata script correction removes the invalid Standby response; the
formerly capped sourced-deck duel now terminates and replay-verifies. See
[the ruling](goat_rules.md) and [the evaluation](evaluation.md).

The player-reviewed neural-v14 replay also exposed a self-target Nobleman
and a Heavy Storm that destroyed only friendly back row. The replay audit
now flags those choices and visible negative Heavy Storm trades. An opt-in
Tactical card-count variant corrects 27 of 56 such synthetic-teacher choices
but split 47–49 against unchanged v14 over 96 duels. A feature-v25 neural
trade head trained on 149 balanced activation opportunities corrected both
reviewed frames and improved resource-choice counts on 16 separate recorded
duels, while scoring only 31–33 against its frozen neural parent over 64
fresh held-out duels. Keep both experimental. The next M4 step is a broader
card-value and timing signal that improves independent match outcomes while
preserving profitable resource use, followed by a separately demonstrated
self-play gain; see [the evaluation](evaluation.md).

An expanded v25 resource head trained on 207 verified opportunities across
four deck pairings corrected nine of 10 later flagged own-only Nobleman
choices and all four negative Heavy Storm choices on recorded states. Across
96 new held-out direct duels it scored 51–43–2 against its v23 parent, with a
paired interval crossing 50%; against Tactical-v14 it scored 21–75 versus
the parent's 20–76. The narrow card-trade signal still does not establish the
M4 strength gate; see [the expanded outcome check](evaluation.md#diverse-resource-trade-head-and-held-out-outcome-check-27-october-2026).

A focused 71-decision Thunder Dragon imitation fit improved fixed-state
teacher agreement on separate recorded duels, but scored 26–38 directly
against its parent on unseen deck families and 7–57 against Tactical versus
the parent's 6–58. A local activation correction alone did not close M4's
competitive gap; keep the unchanged v23 reference and measure match strength
before promoting future decision-specific fits. See
[the evaluation](evaluation.md#focused-thunder-dragon-imitation-pilot-27-october-2026).

An opt-in clipped PPO update now reuses each native self-play duel for
minibatch policy updates. In matched 32-duel training runs from the v23
parent, PPO scored 122–69 with one draw against the REINFORCE child over
192 held-out games. It scored only 31–33 against its unchanged parent and
11–52 with one draw against Tactical on another held-out schedule; the
parent scored 13–50 with one draw against Tactical there. This relative
algorithm gain does not satisfy M4's absolute strength gate. Keep the parent
as the neural reference and require a measured gain against the parent and
Tactical across deck families before promoting an RL update; see
[the evaluation](evaluation.md).

A 64-duel policy-versus-Tactical collection supplied 4,679 replay-verified,
player-visible synthetic labels, including 1,025 policy/teacher
disagreements. Plain and disagreement-weighted clones did not beat their
unchanged v23 parent directly. The weighted child improved its paired score
against Tactical by 9.0 points over the parent on two held-out pairings
(95% interval +2.3 to +16.0), but lost 9.4 points on an additional unseen
Dimension Fusion family (−17.2 to −0.8). The plain child shared that
regression. This is useful evidence of deck-family overfitting, not M4's
cross-deck strength gain. Keep the parent as the neural reference; see
[the expanded evaluation](evaluation.md).

An exploratory continuation combined those 64 verified duels with eight
policy-visited Tactical labels from a separate WikiFormat Dimension Fusion
list. The 5,180-label child split 46–45–5 directly against its parent on 96
held-out games and scored 26–70 versus Tactical, compared with the parent's
19–77 on the same schedule. Another eight verified Chaos Turbo/Matt Peddle
duels expanded training to 5,749 labels. The three-family child split 46–48–2
against the two-family child on 96 fresh held-out games; across two 96-game
Tactical schedules its paired score advantage was only +2.9 points with a
95% interval of −2.1 to +8.1. These synthetic-teacher data additions did not
demonstrate a direct parent gain, broad competitive strength, or self-play
gain. Keep the v23 parent as reference; [the pilot log](evaluation.md#on-policy-teacher-diversity-pilot-27-october-2026)
records the decks, pins, and report hashes.

A player-visible review queue prioritizes conservative audit flags and then
diverse policy/Tactical disagreements from native-verified,
checkpoint-attributed greedy replays. Its first 16-duel pass selected 20 of
292 candidates for human inspection. These are not
ground-truth labels; reviewed preferences and fresh held-out outcome gains
remain necessary before using them to support an M4 strength claim. See
[the queue protocol](evaluation.md#player-visible-disagreement-review-queue-27-october-2026).
An extended 18-duel pass adds self-banish findings for Chaos Sorcerer and
Black Luster Soldier with legal opposing targets, selecting 24 of 335
candidates after 8,578 native-verified decisions. The audit also recognizes
Raigeki Break targeting a friendly card while an opposing target is legal;
no such case occurred in this measured set.
A new four-matchup development collection with both seats produced 16
native-verified duels and 11,617 decisions. Its 24-frame review queue spans
all four pairings and ten conservative audit prompts, including own-only
Nobleman, empty Thunder Dragon search, and BLS self-targeting. It is a
human-review artifact, not training labels or a strength result; see
[the replay audit](replay_audit.md#four-matchup-development-review-queue-27-october-2026).
An AB/BA eight-game REINFORCE pilot measured about 1.38–1.40× shorter
training wall time with the existing opt-in batch size 16 versus scalar
updates. Its matching summaries are not a held-out strength result; see
[evaluation](evaluation.md#batched-reinforce-update-microbenchmark-27-october-2026).
Two rule-derived self-banish preferences fit their exact Chaos Sorcerer and
Black Luster Soldier target states, but their feature-v23 child scored
66–61–1 against its parent across 128 held-out-deck games, with a paired
interval including 50%, and remained well behind Tactical-v14. Keep it
experimental; see [the preference pilot](evaluation.md#self-banish-preference-pilot-27-october-2026).

Preference training can now use fresh, current-asset native replays for
frozen-parent KL preservation while retaining exact replay verification,
visibility audits, and held-out provenance. A two-preference pilot using
four such preservation games fit both training choices but scored 18–14
against its parent and 5–27 against Tactical on a 32-game unseen-deck
schedule; neither paired interval establishes a strength gain. Keep the
parent as reference and gather broader reviewed choices before another
promotion; see [the pilot](evaluation.md#fresh-asset-kl-preservation-for-replay-preferences-27-october-2026).

Four-duel PPO rollout batching and equal-duel loss weighting were tested
from that same parent on the same 32-game training schedule. The unweighted
rollout child lost 20–44 to single-duel PPO on 64 held-out games; the
equal-weight child scored 29–33 with two draws against it. The latter also
scored 29–35 versus its unchanged parent and 17–47 versus Tactical on a
separate held-out schedule. Neither variant meets the M4 gate or shows a
measured speed gain. Keep single-duel updates as the default and pursue a
better learning signal before scaling rollout volume; see
[the evaluation](evaluation.md).

Self-play training now saves exact terminal-duel trajectories by default and
binds their SHA-256 hashes to new checkpoint training-game entries. A native
1,072-decision replay verified after a one-game smoke, including a visibility
audit. This closes a reproducibility gap; M4's held-out competitive strength
gate remains open. See [the provenance check](evaluation.md#exact-self-play-replay-provenance-27-october-2026).

Replay writing now avoids a recursive dataclass copy while preserving the
same current-schema JSON bytes. Four-round serialization benchmarks on two
native self-play replays showed 1.36–1.78× faster in-memory encoding, with
no measured whole-training speedup yet. See
[the serialization benchmark](evaluation.md#replay-serialization-cost-27-october-2026).

Native script loading now computes each script's relative path once. A
matched four-game AB/BA run showed a 1.45–1.53× reset-subtotal speedup and a
1.02–1.04× complete-duel wall-time gain, with identical per-game decisions,
winners, and one byte-identical replay across versions. This improves rollout
startup without changing the historical Lua patches; see
[the native benchmark](benchmarks.md#native-script-path-dispatch).

Staged multi-card picks now reuse their unchanged player-visible observation
until the native response is submitted. A six-round matched complete-duel
benchmark removed one observation build per 1,197-decision duel, with no
reliable wall-time gain (median reference/reused ratio 1.006×). The next
training-speed experiment should therefore target work that occurs on most
decisions, such as batched policy inference across concurrent duels, and
measure full training throughput and held-out strength before adoption; see
[the benchmark](benchmarks.md#staged-selection-observation-reuse).

The existing opt-in REINFORCE batch-16 update now also has a matched complete
one-duel training measurement: 1.19× faster than scalar updates in both AB/BA
orders, with an identical recorded 924-decision rollout. This is a useful CPU
experiment setting, but one training game does not justify changing the
reproducibility default or establish strength; see
[the training benchmark](benchmarks.md#complete-one-duel-reinforce-training-scalar-versus-batch-16).

An opt-in multi-duel PPO rollout now batches learner inference across native
duels in one process. Eight matched games produced byte-identical trajectories
and equal policy tensors across one-worker, batched, and four-worker modes.
Complete training took 8.710, 8.322, and 6.897 seconds respectively on the
measured CPU. Four process workers remain faster for this workload; the new
mode is an experiment for machines where process scaling or accelerator
inference changes that tradeoff. See
[the full benchmark](benchmarks.md#single-process-batched-ppo-inference-27-october-2026).

An opt-in single-process PPO path now reuses the player-visible feature tensors
computed when sampling each learner action. A matched four-game AB/BA run kept
all replay bytes and policy tensors identical while reducing complete reported
training time by about 2% and increasing observed peak RSS by 3,604 KiB. This
is a modest local saving, not a change to the default or evidence of stronger
play; see [the benchmark](benchmarks.md#reusing-visible-ppo-features-from-rollout-27-october-2026).

A separate four-duel PPO profile on sourced decks found native observation
construction, policy forward calls, and visible feature encoding to be the
largest recurring Python costs in that sample. Its four replays and checkpoint
matched an unprofiled reference exactly; the observed profile overhead is
reported separately. The next speed experiment should target the frequent
observation path and preserve exact visible decisions; see
[the profile](benchmarks.md#four-duel-ppo-training-profile-27-october-2026).
The first observation-path experiment caches immutable, viewer-specific card
projections. A four-duel complete-training AB/BA comparison kept all replay
bytes and model tensors equal and ran faster in both orders (1.37× and 1.09×
uncached/cached); the reversed order gives the more cautious estimate. Native
verification and the visibility audit passed. See
[the measured comparison](benchmarks.md#cached-viewer-specific-card-projections-27-october-2026).
After the card-projection cache, a 16-duel single-process profile found policy
forward calls ahead of observation construction in cumulative Python time.
Matched replays and model tensors were identical and all 8,151 decisions
replay-verified. A separate four-versus-eight worker scaling check found only
about 1–4% shorter trainer time with eight workers on two 16-duel schedules.
Prioritize a measured reduction in policy-inference overhead before adding
more rollout workers; see [the longer profile and scaling check](benchmarks.md#longer-single-process-ppo-profile).
An opt-in feature-v23 TorchScript trace now reuses frozen scorer operations
across each single-process multi-duel PPO rollout. Two matched 16-duel runs
saved about 4–6% of complete trainer time, with byte-identical replays and
equal model tensors; the traced second group's 7,179 decisions replay-verified
and passed the visibility audit. Four process workers remain faster on the
separate measured CPU workload, so tracing is not the default. See the
[trace benchmark](benchmarks.md#reused-torchscript-trace-for-frozen-ppo-rollout-inference).

Clipped PPO with frozen-parent KL now caches parent action probabilities once
per recorded decision instead of recomputing them in each epoch. One matched
native training game kept its 2,384-decision trajectory byte-identical and
reduced reported training time from 8.203 to 7.586 seconds; minor floating-point
weight differences left all 965 recorded learner top actions unchanged. This
speeds a regularized update but does not address M4's held-out strength gate;
see [the measurement](benchmarks.md#cached-frozen-parent-scores-for-ppo-27-october-2026).

An opt-in cloning continuation omitted 15,296 forced decisions from a
23,566-decision, replay-verified demonstration set. Matched fitting was 2.64×
faster, but the filtered child tied the unfiltered child 32–32 directly and
scored 16–48 versus Tactical-v14, compared with 21–43 for the unfiltered
child on matched unseen-deck seeds. Neither result promotes the filtered
checkpoint or closes M4. A separate rule to conserve ordinary Spell Sets
also failed two held-out Tactical comparisons and was discarded. Future M4
work should improve decision quality and credit assignment, then verify a
neural gain across independent deck families and a subsequent self-play gain;
see [the evaluation](evaluation.md#filtered-cloning-continuation-and-held-out-strength-27-october-2026).

A separate opt-in `--omit-forced-forward` now keeps the original cloning
minibatches and optimizer steps while avoiding neural work on forced rows in
mixed batches. On the same 23,566-label workload, fitting was 1.44× faster
and full training 1.17× faster than the original path. Its child went 32–32
directly against the original and both scored 20–43–1 versus Tactical on
matched unseen-deck seeds. The original checkpoint remains the M4 reference;
see [the measured comparison](evaluation.md#preserving-cloning-batches-while-omitting-forced-forwards-27-october-2026).

## Historical cross-controller SEGOC

The pinned upstream core builds Thestalos CL1, opponent Sangan CL2 after Soul
Exchange, while the GOAT-specific guide and archived UDE Netrep ruling require
Sangan CL1, Thestalos CL2. A checksum-verified GOAT-only native patch now
selects mandatory triggers by trigger time and gives the turn player priority
when triggers share a time. Same-controller, cross-controller, and paired
simultaneous-Sangan native regressions pass. A paired Desert Sunlight fixture
now confirms that one player may choose either order for their simultaneous
Dekoichi and Gravekeeper's Spy Flip Effects; both branches reach terminal,
replay-verify, and pass the visibility audit. A two-player Peten/Torrential
fixture also confirms simultaneous optional triggers: turn-player Link 1,
opponent Link 2, with both replacements resolving in reverse order. Mixed
Sangan/Peten fixtures now confirm mandatory Sangan Link 1 and optional Peten
Link 2 with their controllers swapped; both reach terminal and replay-verify.
A paired Raigeki Break fixture also destroys opponent Sangan at Chain Link 2
before turn-player Sangan at Link 1; the resulting mandatory triggers keep
that event order, opponent Link 1 then turn-player Link 2. This full duel
replay-verifies. Other effects recognized mid-chain and wider historical SEGOC
combinations remain to be independently checked. Re-record
old training trajectories before replay verification because the native core
binary hash and potentially the resulting games have changed. See
`docs/goat_rules.md` for source links and the conflicting Edison summary.

Fresh post-patch Tactical-v14 demonstrations now cover 16 complete duels and
4,761 teacher-seat decisions. A feature-v23 continuation replay-verified those
duels but scored 32–31–1 directly against its parent on 64 held-out duels.
On a separate matched 64-duel Tactical-v14 schedule, the child scored 18–46
and the parent 17–47; the paired interval includes zero. Keep the parent as
the neural reference. A new post-patch self-play policy gain and broader
historical trigger-order checks remain open; see [evaluation](evaluation.md#re-recording-and-retraining-after-the-goat-segoc-core-patch-27-october-2026).

A post-patch 32-duel PPO continuation replay-verified all training games but
split **33–31** against its parent on 64 held-out direct games and scored
**12–52** against Tactical-v14, versus the parent's **18–46** on the matched
baseline schedule. Neither comparison establishes a self-play gain. Keep the
parent as reference and investigate stronger decision-level feedback before
another large PPO run; see [evaluation](evaluation.md#patched-core-ppo-continuation-and-held-out-check-27-october-2026).

A separate six-rule visible-state feedback experiment generated 26 synthetic
preferences from 19 of those verified PPO replays. The trained child scored
70–58 directly against its parent on 128 fresh held-out duels, with a paired
interval including 50%, and 14–50 versus Tactical-v14 against the parent's
13–51 on a matched 64-duel schedule. This remains experimental and does not
close M4. The label source is recorded distinctly from human review, and
training recomputes each rule before fitting; see
[evaluation](evaluation.md#automated-visible-rule-preference-experiment-27-october-2026).

A second automated preference ablation added visible-state Nobleman and
Raigeki Break comparisons while preserving the v1 label contract. Fresh
current-asset replays yielded 12 labels, including four Nobleman cases and no
Raigeki Break case. The child scored 34–30 directly against its parent, but
13–49–2 versus Tactical-v14 against the parent's 18–46 on matched unseen-deck
seeds. The comparison does not establish a strength gain; keep the unchanged
reference and pursue broader, independently validated decision feedback.
See [the v2 experiment](evaluation.md#visible-rule-v2-preference-ablation-27-october-2026).

A frozen-parent diagnostic now re-scores conservative flags from sampled
self-play using the unchanged reference's greedy action on exactly the
recorded player-visible state and legal set. Across 16 new native-verified
training duels, five of eight sampled flags also appeared under greedy parent
inference, including own-only Nobleman and negative backrow trades. This
separates persistent model choices from pure sampling noise but supplies no
expert labels or demonstrated strength gain; see [the replay audit](replay_audit.md#frozen-parent-check-of-sampled-self-play-flags-27-october-2026).

An opt-in frozen-rollout PPO baseline was also tested on the same post-patch
training schedule. Its child scored 28–36 against the online-baseline PPO
child and 31–33 against the unchanged reference on separate held-out direct
checks. The matched Tactical comparison was 13–51 versus 10–54 for the
reference, with a paired interval crossing zero. Neither PPO timing meets
M4's self-play gain gate; see
[evaluation](evaluation.md#frozen-rollout-baseline-ablation-27-october-2026).
