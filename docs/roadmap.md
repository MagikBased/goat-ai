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

A fresh [20-duel random whitelist/Fusion sample](evaluation.md#fresh-random-whitelistfusion-protocol-sample--30-october-2026)
completed on independently generated legal Deck pairs. All 20,315 decisions
replay-verified and passed the visibility audit; repeating the seeds reproduced
the same streams and outcomes. Eleven selected activation IDs were absent from
the earlier first-activation partitions. This expands sampled protocol
coverage while arbitrary-Deck and historical-ruling completeness remain open.

A fresh 21-duel first-activation sweep over a shuffled partition of the
canonical GOAT whitelist reached terminal in every game and replay-verified
23,381 decisions. It selected activations for 82 card IDs absent from the two
earlier first-activation partitions, raising their combined observed activation
set to 562 IDs. A one-worker rerun reproduced all 21 decision streams and
terminal observations exactly. This extends sampled protocol coverage, while
historical effects and arbitrary-deck completeness remain open; see the
[evaluation entry](evaluation.md#third-first-activation-whitelist-partition-29-october-2026).

A further [20-duel Tactical-v14 whitelist/Fusion sample](evaluation.md#fresh-tactical-whitelistfusion-protocol-sample-29-october-2026)
on seeds 112000–112019 completed and native-replay/visibility-verified all
9,824 decisions with distinct independently sampled opponent Main Decks and
random legal Fusion Extra Decks. It extends sampled protocol coverage while
arbitrary-deck correctness and historical card interactions remain open.

Schema v27 now retains the last 32 public attack announcements as attacker
and target field slots, including direct attacks, without recording a
face-down target's identity. The pinned native Des Koala battle fixture
replay-verifies with this observation, checks the hidden target boundary,
and also verifies a projected v26 recording of the same duel. Existing
policy encoders do not yet consume the new attack history; a learned benefit
would require a separate feature ablation and held-out evaluation.
A paired native differential now swaps a Set Des Koala for a Set Normal Monster
at the same shuffled Deck position. The attack target prompt and immediate
post-announcement observation and legal actions match exactly for the attacking
player, including the public attack slots. Both complete duels replay-verify
and pass the visibility audit; later Flip resolution may legitimately differ.

Large card/chain sort prompts now use staged, linear-size legal actions after
2,048 complete permutations. A synthetic seven-card message exercises the
bounded menu; a forced staged path on Fruits of Kozaky's Studies finishes a
native duel, replay-verifies, and passes the visibility audit. This removes
one explicit protocol limit, while a real seven-card sort remains unobserved.
See [architecture](architecture.md).

The sum-selection adapter's exact and minimum-exceed modes now have a
deterministic 120-case test against exhaustive legal-subset enumeration. It
checks both final choices and every staged prefix against the pinned core's
selection conditions, including mandatory cards and dual level values. This
supports the decoder's pruning logic; it does not prove that every card using
sum selection reaches the prompt correctly.

Tribute prompts that would exceed 2,048 flat subsets now stage card picks
and submit one weighted, count-bounded native response. A forced staged
Dark Magician of Chaos Tribute line retrieves Pot of Greed, then completes
the duel; its full trajectory replay-verifies and passes the visibility
audit. A separate 120-case exhaustive check covers weighted staged prefixes.
This removes a decoder action-count limit; naturally occurring large
Tribute prompts and additional card interactions still need coverage.

A deterministic coverage suite now partitions every one of the **1,624**
canonical legal Main Deck IDs into 41 valid decks and distributes all **52**
canonical legal Fusion IDs into their Extra Decks. Pairing those decks ran
21 isolated random-agent duels; all reached terminal state, all 20,575
decisions replay-verified, and the visibility audit passed. This proves
deck construction and sampled headless protocol operation across a complete
static catalog partition. Many cards were never drawn or activated, so it
does not prove every effect or arbitrary-deck correctness. See the
[evaluation report](evaluation.md#canonical-whitelist-coverage-suite-28-october-2026).
The rerun now separates any card action from manual effect activation:
308 distinct IDs were offered an `activate` or `chain` action and 281 were
selected at least once. Per-duel ID lists identify unexercised cards for
forced fixtures. Automatic triggers and successful effect resolution remain
outside this count; see the [refined coverage report](evaluation.md#whitelist-activation-coverage-refinement-28-october-2026).

An optional first-offered-activation probe now prefers an activation whose
card ID that player has not activated in the duel, then falls back to seeded
random play.
Two 21-duel deck partitions completed, replay-verified, and passed visibility
audits, exercising 480 distinct activation IDs between them. Combined with
the earlier random partition, 507 distinct IDs were activated at least once.
The second partition reproduced all 22,355 decisions with one and four
workers. This expands sampled effect paths without certifying unexercised
cards or historical outcomes; see the [activation probe](evaluation.md#first-offered-activation-probe-29-october-2026).

The same observation-only probe on five pairings of preserved Indianapolis
2005 decks exercised common effects absent from the random card partitions:
Scapegoat, Metamorphosis, Mirror Force, and Torrential Tribute. All ten
seat-swapped duels and 9,546 decisions replay-verified and passed visibility
audits; see [competitive action coverage](competitive_action_coverage.md#first-activation-probe-on-preserved-2005-decks-29-october-2026).

A tactical-agent Fusion stress sweep now adds 20 complete seeded duels on 40
independently generated legal Main Decks with Scapegoat, Metamorphosis, and
sampled Extra Decks containing Thousand-Eyes Restrict. All 12,385 decisions
replay-verified and passed visibility checks; the action counter confirms 34
selected Scapegoat chain responses and 33 selected Metamorphosis activations.
This extends sampled protocol evidence for a common GOAT control line, while
full arbitrary-deck and historical-ruling validation remain open. See the
[evaluation log](evaluation.md#tactical-fusion-stress-random-deck-protocol-probe-28-october-2026).

A further whitelist-wide seed-110000–110019 probe used 40 independently
generated legal Main Decks with sampled 15-card Fusion Extra Decks. All 20
duels reached terminal within 3,000 decisions, and all 21,811 decisions
replay-verified and passed the player-visibility audit. This broadens M1
protocol coverage across randomly selected legal cards; historical correctness
and exhaustive arbitrary-deck support remain open. See the
[evaluation log](evaluation.md#random-legal-decks-with-independent-opponents-and-fusion-extra-decks-28-october-2026).
A fresh 20-duel distinct-whitelist and random-Fusion probe on seeds
129000–129019 also reached terminal, replay-verified all 8,590 decisions,
passed the visibility audit, and repeated exactly on each seed. This adds
sampled protocol evidence without closing M1's arbitrary-deck gate; see the
[evaluation entry](evaluation.md#fresh-distinct-whitelist-fusion-protocol-probe-29-october-2026).
An eight-duel seed-127000–127007 Fusion stress sweep forced three Scapegoat
and three Metamorphosis copies into each random legal 40-card Main Deck and
placed 15 random legal Fusions, including Thousand-Eyes Restrict, in each
Extra Deck. Distinct random opponents were used. All 8,169 original decisions
replay-verified and visibility-audited; all eight seeded repeats matched
exactly. The sampled games exposed 29 action kinds. This is broader protocol
coverage, not a historical-correctness or arbitrary-deck guarantee; see the
[evaluation entry](evaluation.md#isolated-fusion-stress-protocol-sweep-29-october-2026).

A further [Indianapolis 2005 card-pool probe](evaluation.md#indianapolis-2005-card-pool-protocol-sweep-30-october-2026)
completed 32 RandomAgent and 16 Tactical-v14 duels against independently
generated opponents. All 48 games terminated under 3,000 decisions, and all
43,029 decisions replay-verified, passed visibility audit, and reproduced on
seeded reruns. This broadens sampled protocol coverage for historically played
cards, while M1 still requires broader deck and effect coverage.

**Status: in progress.** A direct native binding completes restricted fixture duels with selected scripted cards. It handles optional chain choices, exposes structured public chain links and their field-target slots, monster battle positions, and Battle/Damage Step timing from public core events, and redacts the ID of a set opponent monster targeted by Nobleman. Observations include a bounded history of public turn, phase, attack, Damage Step, and chain events, the player's sorted initial Main Deck and own Fusion Deck identities, narrow memory of opponent field cards publicly seen before turning facedown with their field slots, public Deck-top reveals, recipient-scoped card reveals, the active disabled-zone mask, and a public Scapegoat summon restriction. Unrevealed opponent identities remain hidden. `.ydk` parsing, pinned whitelist checks, deterministic deck shuffling, and a complete metadata/script-path inventory for the 1,685 allowed whitelist IDs are implemented. Deck validation admits more than 60 Main Deck cards and selects historical or community Side Deck sizing. A separate experimental adapter completes 50 seeded synthetic control-deck duels and 20 cross-deck duels against a Chaos-style probe, including effect yes/no prompts. It now decodes bounded multiple-zone selection, Attribute announcement, and number announcement prompts; native fixtures exercise Ground Collapse, Homunculus the Alchemic Being, and Wall of Revealing Light respectively. Question fixtures reach a 1,039-name Monster announcement, redact the activating player's Graveyard during the chain, and confirm both ordinary and GOAT-variant printed-name branches. The historical announcement catalog still needs independent validation. A Fruits of Kozaky's Studies fixture covers a three-card private Deck-top ordering prompt. An Exchange fixture verifies that privately revealed opponent hand cards become selectable only for the addressed player, without exposing native hand slots. A Nobleman Flip-monster fixture verifies that full Deck reveals are delivered only to their addressed recipients. A Gravekeeper's Spy fixture verifies Deck-search recruitment and a paired native Deck-order differential; search actions omit private Deck slot numbers and are ordered by visible values. A reproducible random-deck probe generated ten whitelist-legal 40-card decks and completed all ten seeded 3,000-decision-limit duels in 12,382 decisions on the pinned assets; the report hash reproduced. Differential tests cover hidden opening-hand, set-monster, set-Trap, targeted set-Trap, and opponent Extra Deck identities, but broader decisions and visibility remain unaudited. General effect and decision coverage, independently audited historical legality, and complete player-visible observations are still required. Face-up monster ATK, DEF, counters, and public Equip Card target slots, including face-down cards equipped to Thousand-Eyes Restrict, are now included, but other dynamic public card state remains unaudited.

A paired Pot of Greed fixture swaps the two privately drawn cards while preserving the Deck multiset and public play. The opponent's complete observation and legal actions are identical at the next Main Phase decision; the acting player's drawn hand differs. A Book of Moon / Compulsory native fixture found and fixed lost opponent-hand knowledge when a previously public, now face-down monster returns to hand. A never-revealed Set monster remains unknown in the paired control fixture; the known-card duel serializes and replay-verifies. See [GOAT rules](goat_rules.md).

A paired Different Dimension Capsule fixture now chooses two different
face-down banished Deck cards and obtains identical opponent observations
immediately afterward. The owner sees their chosen card; the opponent sees
only the hidden banished slot. Both full duels replay-verify and pass the
visibility audit. The observation model independently rejects an opponent
face-down banished card carrying an identity. This closes one banished-zone
privacy case, not every hidden-information branch; see [GOAT rules](goat_rules.md).

Schema-v26 observations now count public turn boundaries since each face-up
field card became face-up. Native Swords expiration and Giant Trunade/replay
fixtures check the count advancing and resetting across turns, with matching
views for both players. Opt-in policy feature v29 exposes that value to the
model without changing older checkpoints. This closes one timing-information
gap; other public state and broad historical validation remain open.

A paired Trap Dustshoot/Mystical Space Typhoon fixture now changes one
unrevealed opposing hand card and confirms that the Trap controller's
observation and legal responses are identical before Dustshoot activates.
Only its addressed reveal and known-hand memory differ afterward. Both
respond/pass full duels replay-verify; see [GOAT rules](goat_rules.md).

A documented [2020 championship Chaos Turbo Main Deck](../examples/decks/chaos_turbo_riclar_2020.ydk) now exercises a real archetype rather than only synthetic probes. With the experimental adapter and random agents, seeds 1–20 all reached terminal against `control_probe.ydk` within 3,000 decisions. Two seat-swapped, full-deck fixtures also serialize and replay-verify complete trajectories. These are protocol-coverage results; the random plays and current scripts do not establish historical correctness or playing strength.

A [2020 championship Goat Control Main Deck](../examples/decks/goat_control_lolmarcus_2020.ydk), paired with three test-copy Thousand-Eyes Restricts, also completed seeds 1–20 against that Chaos Turbo list within 3,000 decisions. Two seat-swapped matchup fixtures serialize and replay-verify full trajectories. The source omits the Extra Deck, so its contents are a disclosed test choice.

A documented [competitive Warrior Main Deck](../examples/decks/warrior_montague_clash.ydk) adds an aggressive archetype and Reinforcement of the Army to the corpus. It passes the pinned whitelist/deck-size gate. Random-agent Warrior versus Chaos Turbo duels completed all 20 games on seeds 1–10 in both seats within 3,000 decisions; two seat-swapped full-duel trajectories serialize and replay-verify. This extends protocol coverage, not card-by-card ruling validation or a playing-strength claim.

A further 60-duel random-agent sweep on seeds 21–30 covered all three pairings among the sourced Goat Control, Chaos Turbo, and Warrior lists in both seats. All reached terminal under a 3,000-decision cap, with 60,374 decisions total. Goat Control versus Warrior additionally has two complete seat-swapped trajectories that replay-verify. The measured two-worker runtime and limits are in [the evaluation log](evaluation.md). This widens M1 protocol coverage; M2 historical card correctness remains open.

A further independent whitelist/Fusion sample on seeds 11200–11249 reached
terminal in all 50 games and replay-verified all 51,755 decisions with the
visibility audit. Two seeds reproduced all 2,208 decisions on a repeat run.
This broadens M1 protocol evidence across distinct sampled decks, but does not
certify historical card effects; see [the measured sweep](evaluation.md#independent-goat-whitelist-and-fusion-protocol-sweep-28-october-2026).

The evaluator also runs all ten pairings of five executable Indianapolis 2005
Top 8 Main Decks through `--indianapolis-2005`. On two seeds with both agent
seats, all 40 RandomAgent duels reached terminal under the 3,000-decision
limit; ordered results and 39,057 total decisions matched between one and
four workers. This extends protocol coverage across contemporary submitted
decks, while the separate historical ruling and hidden-information audits
remain open. See [evaluation](evaluation.md).

A [2005 SJC Charlotte Zombie Main Deck](../examples/decks/zombie_jae_kim_charlotte_2005.ydk)
adds a distinct historical holdout. Its exact 40 published Main cards pass the
pinned GOAT whitelist; two seeded, seat-swapped RandomAgent duels against
Phoenix Control reached terminal and replay-verified. The source lists no
Fusion Deck, and its Side Deck is omitted for single-duel evaluation. See
[evaluation](evaluation.md) for the current policy's held-out transfer result.

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

A [2022 Worlds first-place Chaos Return list](../examples/decks/chaos_return_dingosig_worlds_2022.ydk) adds a fifth sourced tournament archetype with the published 40-card Main, 15-card Extra, and 15-card Side Deck. The public Format Library YDK was converted to pinned GOAT/pre-errata IDs, with the source hash and conversion listed in the deck header. It passes the pinned whitelist gate. Twenty random-agent games against Warrior reached terminal under 3,000 decisions; two seat-swapped full-duel trajectories replay-verify. This adds Return from the Different Dimension, Bazoo, Shining Angel, and Zaborg to the protocol corpus. Separate native fixtures now verify Return’s basic Chaos-cost revival, its historical Book of Moon End Phase exception, one-open and full-Monster-Zone legality branches, including End Phase cleanup for the revived monster, matched Mystical Space Typhoon/Solemn Judgment/Royal Decree responses, plus Decree already face-up, that distinguish destruction, activation negation, and effect negation, Bazoo’s two-monster banish cost into a Return revival, Bazoo’s three-monster banish cost with its boost persisting through the opponent’s turn, Skill Drain chained after Bazoo's cost to negate its ATK increase, and Kycoo already face-up versus revived after Bazoo's cost. Other Return and Bazoo interactions still need card-specific audits. Shining Angel now has basic battle-recruitment, same-turn attack, empty-search opponent-only Deck verification, and Snatch Steal control-change fixtures; other interruptions remain untested. Zaborg now has mandatory-target fixtures for self-destruction and an opponent’s hidden monster, a Tribute Set fixture showing no trigger, a Solemn Judgment fixture negating its Tribute Summon before the effect, and a Book of Moon response fixture where its activated effect still destroys the target after Zaborg is turned face-down. Other responses to its effect remain untested. See [the evaluation log](evaluation.md).

A [sixth sourced tournament Main Deck](../examples/decks/bazoo_return_weirdchamp_worlds.ydk) transcribes Weirdchamp's published sixth-place World Championship Bazoo Return list. It passes the pinned whitelist gate. Two seeded random-agent duels against Goat Control, with Bazoo Return in each seat, reached terminal below 3,000 decisions and their complete trajectories serialized and replay-verified. The source did not provide Extra or Side Deck contents, so both sections remain empty. These are protocol-coverage results; they do not prove that every card effect in the list is historically correct.

**Work**

1. Implement `.ydk` parsing and April 2005 deck/card-pool validation. Begin with two small legal fixture decks and expand coverage.
2. Convert each native decision request into a variable-length list of structured actions. Map selected actions to exact native responses, including multi-step targets, effect choices, chains, and phase changes.
3. Build observations solely from player-visible native queries and observed public events. Maintain known-card memory without reading hidden identities from internal state.
4. Connect the adapter to `GoatEnvironment`; run two `RandomAgent` instances through terminal states. Record decision trajectories and replay seeds.
5. Add an interactive CLI duel and a real benchmark command. Record crashes, unsupported requests, and infinite loops as failures.

**Exit:** A clean setup completes seeded random-agent duels with valid outcomes and no unhandled native messages in the fixture decks. Illegal actions are rejected. Repeated seeds reproduce action/observation/outcome traces. Changing a hidden opponent hand or deck order while holding the visible state fixed cannot change the observation supplied to the agent.

A further [20-duel independent whitelist/Fusion sample](evaluation.md#additional-independent-whitelist-and-fusion-protocol-sample-28-october-2026) reached terminal with 19,282 replay-verified, visibility-audited decisions; two seeds reproduced identical traces. This widens protocol coverage without resolving card-specific historical correctness.

Large `MSG_SELECT_PLACE` and `MSG_SELECT_DISFIELD` choices now use staged,
linear-size public zone actions when complete combinations exceed 2,048.
The adapter preserves each chosen zone's order and submits one native response
after the final pick. A synthetic five-zone prompt checks the bounded action
set; forcing the staged route on Ground Collapse's two-zone prompt produces the
same post-selection observation and legal actions as the flat route. Both
complete duels replay-verify and pass the visibility audit. A synthetic GOAT
`.yrp` with one saved zone response also reconstructs into staged choices and
the same terminal duel. This widens protocol coverage; it does not establish
historical correctness or real human replay compatibility.

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

A native multi-turn differential now replaces only the opponent's turn-two
private draw with each of 59 distinct cards from the sourced tournament Main
Deck corpus. All opening opponent hands remain identical, the private drawn
hands differ, and every first-player observation and legal-action set remains
identical through the turn-three Main Phase under the same passive public
actions. This extends the hidden-information check past startup; it does not
cover divergent public plays or all card effects. See
[evaluation](evaluation.md#tournament-card-private-draw-differential-27-october-2026).

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

An additional 100-pair full-whitelist sweep on new seeds 30150–30249 reached
**100/100 terminal** with **107,628** decisions replay-verified and
visibility-audited. The generated decks contained 1,616 distinct Main Deck
IDs and loaded 11 scripts absent from the earlier 100-pair whitelist report.
This expands sampled M1 protocol coverage; no sampled sweep can certify
arbitrary-card completeness or M2 rulings. See
[the report](evaluation.md#additional-distinct-whitelist-protocol-sweep-27-october-2026).

A fresh independent full-whitelist sweep on seeds 30250–30349 reached
**100/100 terminal** with **106,181/106,181** decisions replay-verified and
visibility-audited. Its 200 Main Decks had distinct hashes and covered 1,624
card IDs; 15 scripts were loaded that the preceding 100-pair sweep had not
loaded. This broadens sampled protocol coverage without closing arbitrary-deck
or historical-ruling correctness; see [the report](evaluation.md#further-distinct-whitelist-protocol-sweep-27-october-2026).

A paired Black Illusion Ritual/GOAT Relinquished native fixture now covers
`MSG_SELECT_SUM` Ritual material selection from either hand or field. Both
complete duels replay-verify and pass the player-visibility audit. The native
prompt has no mandatory cards, leaving that decoder path parser-tested only;
see [GOAT rules](goat_rules.md).

A fresh 50-pair whitelist sweep exposed `MSG_SORT_CHAIN` while ordering Dark Elf's and Toll's attack payments; the native message name does not mean chain links were present. The adapter now decodes that bounded ordering request, and both orders complete full replay-verified, visibility-audited duels. Rerunning the exact seeds produced 50/50 terminal games and 50,084 verified decisions; see [the protocol sweep](evaluation.md#chain-order-native-protocol-sweep-27-october-2026). This broadens native action coverage without certifying historical rulings for every sampled card.

The random-whitelist probe now optionally generates 15-card Fusion Decks and a
Scapegoat/Metamorphosis stress composition while preserving the original Main
Deck seed stream. Fifty random-Extra duels completed and verified, but offered
no Fusion card actions; 10 stress duels reached real Thousand-Eyes Restrict
actions. An additional 40 stress seeds exposed a Last Turn forced-battle native
null dereference and a Morale Boost script error. Checksum-verified corrections
and subprocess regressions now cover both; all 40 rerun duels reached terminal
with 39,677 replay-verified, visibility-audited decisions and 111 selected
Metamorphosis activations. A separate Last Turn fixture forces an attack in
response to an announced attack and verifies the End Phase winner; a Morale
Boost fixture checks its 1,000 LP Equip gain and removal damage. Both complete
duels replay-verify and pass the visibility audit. These are protocol and
specific-ruling samples, not arbitrary-deck completeness. See [the Fusion
stress report](evaluation.md#random-fusion-deck-protocol-sweep-27-october-2026).

The deck probe also supports opt-in per-seed process isolation. A failed native
worker leaves its generated deck hashes and exit code in the combined report,
and later seeds continue. Four tournament-card duels reproduced the matching
single-process outcomes and replay-verified 3,330 decisions; see the
[isolation check](evaluation.md#isolated-native-deck-probe-28-october-2026).

The same isolated probe can now run Tactical-v14 through the player-visible
agent API. Forty legal, distinct-opponent tournament-card duels completed with
17,819 verified decisions, while a matched RandomAgent run completed 40 duels
with 36,830 verified decisions. This expands realistic protocol coverage but
does not compare their playing strength; see the [matched probe](evaluation.md#tactical-agent-tournament-card-protocol-sweep-28-october-2026).

The native adapter now decodes bounded `MSG_SELECT_COUNTER` prompts as
`select_counters` actions with explicit per-card amounts. It sends the core's
ordered 16-bit allocation response and checks that each offered amount is
supported by the acting player's visible face-up field. Synthetic protocol,
adapter, visibility, and trajectory-serialization tests pass. A complete
Pitch-Black Power Stone / Anti-Spell native fixture now exercises all three
ways to remove two counters from two face-up cards; each branch serializes,
replay-verifies, and passes the visibility audit. The fixture also corrected
the observation query so face-up Spell/Trap counters are visible to both
players. See [GOAT rules](goat_rules.md). Prompts with more than
4,096 complete allocations now expose feasible per-card amount choices;
the adapter sends one validated response after the last amount. A synthetic
ten-card prompt covers the large-allocation branch, and a forced-stage
native Anti-Spell duel and saved-response reconstruction replay-verify the
same response boundary. A naturally occurring large counter prompt remains
untested. One per-card stage can still have up to 32,768 legal amounts. A
synthetic maximum-menu benchmark measured its cost on one CPU, including
381 MiB peak process memory; this remains a scaling concern for parallel
training, not a duel-throughput result. See
[evaluation](evaluation.md#synthetic-maximum-counter-menu-benchmark-27-october-2026).
Opt-in policy feature v28 now encodes each selected card's counter amount,
counter type, and total cost. It can warm-start from a v23 checkpoint without
changing logits on existing actions. This adds a learnable representation for
counter decisions; it has not been trained or evaluated for playing strength.

A third consecutive 50-pair distinct-whitelist sweep reached 50/50 terminal
games and replay-verified, visibility-audited 52,875 decisions. The exact
report hash reproduced on rerun; combined with the preceding two sweeps, it
observed 1,316 native assets and 5,748 card-source/action-kind pairs. This
extends protocol coverage without validating all historical card rulings;
see [evaluation](evaluation.md#third-consecutive-distinct-whitelist-protocol-sweep-27-october-2026).

A fresh isolated whitelist/Fusion sweep reached **100/100 terminal duels**
and replay-verified, visibility-audited all **108,360** decisions. It loaded
1,349 native assets, 241 absent from the earlier 40-seed Fusion sweep. A
separate Tactical-v14 tournament-card sweep reached **50/50 terminal** and
verified all **24,009** decisions, selecting 62 chain-response card pairs
absent from the earlier random-agent tournament sweep. Two seeds from each
schedule reproduced their full decisions and outcomes. These results widen
protocol coverage and leave historical correctness and arbitrary-deck
completeness unproven; see
[evaluation](evaluation.md#independent-whitelist-fusion-and-tactical-protocol-sweeps-28-october-2026).

## M2 — Historical correctness gate

A paired [Limiter Removal stacking and Book of Moon reset fixture](goat_rules.md#limiter-removal-stacking-and-face-down-reset)
now checks 1,400 → 2,800 → 5,600 ATK and both End Phase outcomes against the
pinned GOAT script. Both complete duels replay-verify and pass the visibility
audit. This advances one historical card interaction; M2 remains open.

A paired [Card Destruction Deck-out fixture](goat_rules.md#card-destruction-near-an-empty-deck) exposed a modern script gate that wrongly prevented a GOAT player from activating the card when the Deck could not cover the redraw. A checksum-guarded in-memory correction now allows that activation while retaining draw-prohibition checks. On the pinned core, six cards remaining produces a complete redraw and a later Draw Phase loss; one card remaining produces an immediate loss during resolution. A third duel shows the opponent loses when their empty Deck cannot supply Card Destruction's redraw; a fourth confirms Protector of the Sanctuary still prevents activation under a draw prohibition. All four complete duels replay-verify and pass the visibility audit. Simultaneous failures and draw replacements remain open.

A paired [Card Destruction/Scapegoat chain fixture](goat_rules.md#card-destruction-after-chained-scapegoat) checks that Card Destruction counts the hand when its effect resolves: chaining Scapegoat from hand reduces its controller's discard and draw count from five to four, and creates four Sheep Tokens first. Both branches finish, replay-verify, and pass the visibility audit. This covers one common chained hand change; other chains remain open.

A paired [Card Destruction empty-hand fixture](goat_rules.md#card-destruction-with-an-empty-hand) checks the archived FAQ's activation gate with a free Spell/Trap Zone. One branch activates while only the opponent has hand cards and draws zero for its controller; the other offers activation while only the controller has another card, then suppresses it after both hands become empty. Both seeded duels reach terminal, replay-verify, and pass the visibility audit. This covers a common card in the sourced tournament corpus.

A new Gravekeeper's Chief/Premature Burial fixture confirms the documented
Necrovalley exception through a complete native duel, replay verification,
and visibility audit. The no-Chief activation gate remains historically
ambiguous because the archived UDE FAQ and generic Netrep wording differ;
the simulator has not been changed on that unresolved point. See
[GOAT rules](goat_rules.md#gravekeepers-chief-exception-to-necrovalley).

A paired seed-18 Last Will/Sangan fixture now verifies the controller's
historical trigger-order choice after Cannon Soldier Tributes Sangan. A
checksum-guarded GOAT-only script correction removes the pinned custom-event
ordering artifact. Both order branches Special Summon and search, finish duels,
replay-verify, and pass the visibility audit. This resolves the previously
recorded discrepancy; other Last Will interactions remain open. See
[GOAT rules](goat_rules.md).

A paired D.D. Survivor fixture now distinguishes a face-up field banishment
by Bottomless Trap Hole, which produces an End Phase return, from a Set card
banished by Nobleman of Crossout, which does not. Both full duels replay-verify
and pass the visibility audit; see [GOAT rules](goat_rules.md). This extends
coverage to a card in a published 2005 Seattle Top 8 Deck without certifying
every banishment route or the full historical ruleset.
An additional full-duel branch confirms the archived Skill Drain interaction:
Survivor returns from banishment in the End Phase even while Skill Drain is
active, because the effect activates outside the field. It also replay-verifies
and passes the visibility audit; see [GOAT rules](goat_rules.md).

A paired Call of the Haunted/Solemn Judgment fixture checks activation
negation before Call revives its targeted monster. Both branches complete,
replay-verify, and pass visibility audits. This extends a common Trap-response
regression; the full historical correctness gate remains open. See
[GOAT rules](goat_rules.md).

The Call of the Haunted timing probe now distinguishes an ordinary Chain
Link 1 Summon, which opens a GOAT Bottomless Trap Hole response, from a
midchain Call Summon at Chain Link 2 before Upstart Goblin resolves, which
does not. Both seeded duels reach terminal state, replay-verify, and pass
visibility audits. This is one source-backed chain-window regression, not a
general proof for all chain endings; see [GOAT rules](goat_rules.md).

A paired Nobleman of Extermination fixture now distinguishes a hidden Set
Trap from a Set Spell. It checks the GOAT-variant script, same visible target
choice, Trap-only matching-copy banishment and recipient-scoped Deck reveals,
then finishes and replay-verifies both duels with visibility audits. A second
paired fixture checks the historical response rule: targeted Dust Tornado
chains, becomes face-up, and prevents Extermination's banishment and Deck
verification; passing lets the banishment proceed. Both response branches
also finish and replay-verify. Other responses remain open; see
[GOAT rules](goat_rules.md).

A source-backed Card Destruction/Banisher of the Light fixture now confirms
that both players draw their full discarded counts even though Banisher sends
those discarded cards to banishment. The complete seeded duel replay-verifies
and passes the visibility audit; see [GOAT rules](goat_rules.md).

A seed-28 Exchange/Thunder Dragon fixture now checks the period ruling that
an opponent-owned Thunder Dragon taken with Exchange can be discarded to
search the new controller's own Deck. It verifies both Deck counts, the
owner's Graveyard, opponent-only search reveal, a complete replay, and the
visibility audit. This is one high-play card interaction, not full M2
coverage; see [GOAT rules](goat_rules.md#thunder-dragon).

A second Thunder Dragon fixture checks its period banish-replacement ruling:
Banisher of the Light sends the discarded copy face-up to banishment while
the controller still searches two copies. The complete duel replay-verifies
and passes the visibility audit; see [GOAT rules](goat_rules.md#thunder-dragon).

A native-enabled local regression run on 2026-10-27 passed **1,003 tests**
in 13 minutes 43 seconds after correction of a schema-v6 test projection
carrying newer owner and pending-summon fields. The ignored full-run log is
`.cache/goat-ai/native_full_20261027_rerun.log` (SHA-256
`9da9d6baf3b2b25e0a95745f8c94ada560cdf3d669e5da2183efc7a35784602a`).
Two Firebird effect tests and two review-queue tests were added after that
run started; both test files then passed separately, **7 tests in 13.25s**.
This is regression coverage for the tested fixtures, not a blanket claim
that every GOAT ruling is historical.

The current native-enabled local suite on 2026-10-29 passed **1,650 tests**
in **1,464.57 seconds** with six PyTorch `TracerWarning`s from the GRU
trace tests. Those tests include varying action counts, chain sizes, and
field sizes, but the warnings still limit any claim that tracing generalizes
to every shape. The ignored full-run log is
`.cache/goat-ai/native_full_20261029.log` (SHA-256
`4c411075f4b14a948b3ae035181f4ab31c148e4ced1dde7748708b8140e3a2f1`).
Reproduce with `OMP_NUM_THREADS=1 PYTHONPATH=src:.
GOAT_AI_NATIVE_ROOT=.cache/goat-ai .venv/bin/python -m pytest -q` after
[native setup](native_setup.md). This passes the current regression suite;
it does not establish complete historical correctness or arbitrary-deck
support.

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

A paired native Ring of Destruction and Book of Moon fixture checks target validity at resolution, the no-damage outcome when Book sets the target, and the opponent's hidden field view. The preserved historical Book ruling states this interaction explicitly. Both branches now finish, replay-verify, and pass the visibility audit; see [GOAT rules](goat_rules.md).

A native Scapegoat/Enemy Controller fixture now checks a Sheep Token paying
Enemy Controller's Tribute cost, all four visible Token choices, use of the
freed fifth Monster Zone for the stolen monster, and End Phase return. Its
complete duel replay-verifies and passes visibility auditing; see
[GOAT rules](goat_rules.md#scapegoat-token-as-enemy-controller-cost).

A paired Breaker/Dust Tornado fixture checks the common backrow response:
Breaker spends its Spell Counter as cost, and chaining Dust to destroy a
different Set Spell leaves Breaker's original target gone at resolution.
Passing instead lets Breaker destroy Dust. Both complete native duels
replay-verify and pass the visibility audit; see [GOAT rules](goat_rules.md).

Four more source-backed response fixtures now continue through terminal duels:
both Book of Moon versus Raigeki Break branches, Ring chained to Mirror Force,
Call of the Haunted chained to Heavy Storm before Sangan searches, and both
Dust Tornado versus an activated Book of Moon branches. All six complete
trajectories replay-verify and pass player-visibility audits. These checks
extend full-duel coverage for common cards without certifying every response
ordering or the complete historical ruleset; see [GOAT rules](goat_rules.md).

A paired Ceasefire fixture now distinguishes a Set Magician of Faith from a
Set Normal Monster. Both turn face-up in Defense Position, but only Faith
counts toward Ceasefire's 500 damage, and its Flip Effect does not recover the
previously spent Pot of Greed. Both duels reach terminal, replay-verify, and
pass the visibility audit; see [GOAT rules](goat_rules.md).
An additional Ceasefire/Jinzo fixture checks the historical resolution
exception: a Set Jinzo becomes face-up during Ceasefire, which still deals
500 damage before Jinzo's Trap suppression applies. The duel reaches terminal,
replay-verifies, and passes the visibility audit. Paired Faith fixtures now
show the distinct result when Ceasefire chains to an already activated Flip
Effect: Faith still returns Pot of Greed after Ceasefire resolves. A separate
Scapegoat fixture checks that four Sheep Tokens do not enable Ceasefire in
response to Pot of Greed and add no damage once a Set Normal Monster makes
Ceasefire legal. All three new duels reach terminal, replay-verify, and pass
the visibility audit. Other Ceasefire chain orders remain open.

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
A paired Merchant/Book of Moon fixture now checks the historical rule that
an already activated Flip Effect resolves after its monster is set again.
Both branches expose the same 19-card public excavation and send the separate
kept-Pot hand reveal only to the opponent, then finish and replay-verify with
visibility audits. Other Merchant chain interruptions remain open; see
[GOAT rules](goat_rules.md#book-of-moon-chained-to-merchants-flip-effect).

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

Four Skull Lair fixtures check its Graveyard-monster banish cost, face-up
Level 1 requirement, absent effect choice during the Damage Step, and two
cost-paid activations on separate chains in one turn. All four seeded full
duels replay-verify and pass the visibility audit; see
[GOAT rules](goat_rules.md).

Four Morphing Jar deck-out fixtures verify the historical five-card draw boundary for either player: with four Deck cards the effect ends the duel, while with five it resolves and the next required draw ends the duel. Four more native fixtures check both players near empty: 3/4, 4/4, and 4/3 cards remaining each give a draw, while five each resolves and the next required draw determines the loser. All eight terminal trajectories replay-verify. A 2007 discussion corroborates the simultaneous-draw result, but a contemporaneous explicit 2005 TCG ruling remains to be located, so that historical interpretation is provisional. See [GOAT rules](goat_rules.md).

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

A Skilled Dark Magician fixture tests two Spell activations in one chain:
Mystical Space Typhoon targets an activated Pot of Greed, both resolve, Pot
draws two cards, and Skilled gains two visible Spell Counters. A paired Skill
Drain fixture then confirms that chaining the Trap to Pot removes Skilled's
existing counter and blocks a new one, while declining it leaves two counters.
All three complete duels replay-verify and pass the visibility audit. These
extend the existing Pot/Solemn counter timing pair; other counter interactions
remain open. See
[GOAT rules](goat_rules.md#skilled-dark-magician-spell-counter-timing).

Three Relinquished fixture branches now check the historical response to its
equip effect on a Set monster: the target stays in its owner's Monster Zone
when Book of Moon Sets Relinquished or Raigeki Break destroys it before
resolution, while the pass branch equips that monster. All three full duels
replay-verify and pass visibility checks; see
[GOAT rules](goat_rules.md#relinquisheds-equip-target-when-book-of-moon-or-raigeki-break-is-chained).

A paired Jinzo/Solemn Judgment fixture now checks the Tribute Summon window:
Solemn is legal before Jinzo's continuous Trap suppression applies, but is
unavailable after a successful Summon. Both full duels replay-verify and pass
visibility checks; see [the ruling note](goat_rules.md#solemn-judgment-against-jinzos-tribute-summon).

A paired Premature Burial/Giant Trunade versus Heavy Storm fixture now checks the 2003 return-versus-destruction ruling, public returned-hand memory, and same-turn reuse of Premature for a second revival. Both full duels replay-verify and pass visibility checks; see [GOAT rules](goat_rules.md#premature-burial-returned-by-giant-trunade).

A pinned-native Thunder Dragon/Solemn Judgment regression now checks that a
Set Solemn is not offered as a response to Thunder Dragon's activated monster
effect. Thunder searches two copies without paying Solemn's LP cost; the
complete duel replay-verifies and passes visibility auditing. This source-backed
response boundary extends M2 but does not certify all monster effects; see
[GOAT rules](goat_rules.md#solemn-judgment-versus-thunder-dragons-hand-effect).

A paired Sangan/Skill Drain fixture checks the historical Graveyard-effect exception: Tributing Sangan for Jinzo still offers and resolves its Deck search while Skill Drain is face-up. A second paired fixture checks battle destruction under active Skill Drain and an inactive control. All four full duels replay-verify and pass visibility checks; see [GOAT rules](goat_rules.md#sangans-graveyard-effect-under-skill-drain).

A paired Magician of Faith/Enemy Controller fixture now checks that taking
Faith after its Flip Effect starts does not transfer Spell recovery to the
new monster controller. Both branches replay-verify and pass visibility
checks, including the public recovered-card memory; see [GOAT rules](goat_rules.md#enemy-controller-chained-to-magician-of-faith).

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

A paired Smashing Ground / Book of Moon fixture now checks that this common 2005 removal Spell does not target and determines the highest-DEF face-up opposing monster on resolution. Both branches complete, replay-verify, and pass the visibility audit; the Book branch hides the surviving Set card from the acting player. A second paired fixture offers both tied highest-DEF monsters as legal choices and checks each destruction branch. Protection effects are still open. See [GOAT rules](goat_rules.md).

A paired Spell Shield Type-8 fixture now checks both historical Spell-negation
modes: a targeted Book of Moon is negated without a discard, while Pot of Greed
requires a Spell sent from hand as cost before the chain resolves. Both full
duels replay-verify and pass the visibility audit; see [GOAT rules](goat_rules.md).
Schema v28 now retains a public effect-option index when one card offers
multiple effects at the same decision. The live controls display the pinned
effect wording, and opt-in policy feature v32 represents the distinction.
Older v27 replays still verify after projection; no playing-strength benefit
has been measured for v32.
The [fresh v28 coverage audit](evaluation.md#public-effect-choice-coverage-on-fresh-v28-trajectories-29-october-2026)
found no simultaneous same-card effect-choice contexts in 21 whitelist duels
or eight sourced-deck Tactical duels. The opt-in feature remains available for
such decisions, but these samples supply no v32 training signal. Prioritize
broader independently reviewed play and M4's held-out strength gate.

## M3 — Evaluation and data

The local replay server now also supports a browser human-versus-AI duel on
the native engine. Each human turn is supplied only the player-visible
observation and enumerated legal actions; the opponent moves through the same
agent interface. A completed duel is saved as `human_web` only after native
replay and visibility verification, with `self_recorded` authorization and
the human seat in provenance. The raw cloning gate admits only that seat.
An unfinished browser session remains in local server memory and is not
training data. This is an authorized self-recording path, not expert data.

Human choices from separate review queues over one verified replay can now be
validated queue by queue and converted into a single replay-bound preference
file. This lets an upstream activation correction coexist with target-choice
reviews without changing either queue or silently counting a forced target as
approval of the activation. Conflicting labels are rejected; only changed
choices become pairwise preferences. Human data volume and independent review
quality remain the M3/M4 bottlenecks.
When a reviewed target prompt exposes its resolving chain link, the automatic
upstream queue now matches earlier optional activations by public effect code,
controller, and stable field slot. This prevents a later unrelated activation
in the same turn from being suggested as the cause of an own-card target.
If no chain link remains, earlier activations are still only review candidates;
the reviewer must confirm the causal link before making a training label.
The local review bar can now create and open a separate, replay-verified
upstream activation queue with one click. The launcher checks the exact queue
hash and reviewer alias before reusing a running save server, so labels stay
attached to the intended review source.

A new `examples/play_goat.py` path records a local human seat on arbitrary
validated GOAT YDK Decks against a Random, Tactical, or saved policy opponent.
It prints player-visible card names and field state, accepts only enumerated
legal actions, and writes a `self_recorded` trajectory only after native replay
verification and a visibility audit. A native test completes the recording
path and checks that a failed verification leaves no accepted output; a
separate display test checks hidden opponent names stay hidden. This supplies
an authorized self-recording path, not imported expert replays or a strength
claim.

An eight-duel native pilot now reports per-process Linux peak RSS, reset
overhead, and throughput at two, four, and eight spawned workers on sourced
decks; see the [evaluation log](evaluation.md#native-worker-scaling-on-sourced-decks-27-october-2026).
A [32-duel follow-up](benchmarks.md#eight-versus-sixteen-native-workers-2026-10-27)
measures eight and sixteen workers in reversed order on the same sourced
pairing. All outcomes and decision counts matched, and sixteen workers had
1.18–1.25× throughput with nearly twice the summed worker high-water RSS. Neural
inference scaling and instantaneous total memory remain unmeasured.
A [64-duel follow-up](benchmarks.md#sixteen-versus-thirty-two-native-workers-2026-10-28)
compares sixteen and thirty-two workers in reversed order: all 67,478
decisions and ordered outcomes matched, while thirty-two workers were 2–5%
slower and used about 1.92× summed worker high-water RSS. This supports
stopping pure-simulation worker scaling at sixteen on the measured host;
neural inference and training throughput still need their own measurements.
An [eight-versus-sixteen PPO worker check](benchmarks.md#eight-versus-sixteen-ppo-rollout-workers-on-mixed-decks-2026-10-28)
now measures an actual 32-game mixed-Deck training schedule with neural
inference and updates. All 16,708 decision records and saved model tensors
matched across four runs; sixteen workers were about 8–10% slower than eight
on this host. A [matched process-tree memory sample](benchmarks.md#ppo-process-tree-memory-on-the-same-mixed-decks-2026-10-30)
measured 2.49 million versus 4.51 million KiB maximum sampled RSS for eight
and sixteen workers, with identical saved duel records and model tensors.
Larger training schedules and peaks between samples remain unmeasured.

**Status: in progress.** Seeded tournament runners swap seats for each deck matchup, record individual outcomes, report seat and matchup splits, and give paired score and Wilson intervals. A spawned-process runner reproduces the sequential results on a native fixture and has a measured two-worker throughput example. A restricted-fixture baseline report is in [the evaluation log](evaluation.md). Schema v18 trajectories add a final player-visible terminal observation to the v17 decision records, which record face-up monster ATK, DEF, and counters alongside bounded public events, field-slot known-card memory, conservative opponent-hand knowledge from public returns and addressed hand reveals, a public Scapegoat restriction, public Deck-top reveals, active disabled zones, recipient-scoped private reveals, and the player's initial Main Deck composition; they can be replayed against the native engine with exact observation, legal-action, result, deck-content, rules-profile, and loaded-asset comparisons. An offline browser viewer renders these player-visible decisions with optional locally cached card art. It interpolates attack arrows, target markers, Life Point fill and numbers, and field-to-Graveyard or banished-pile movement between recorded decision snapshots; it does not reconstruct every native event. The new GOAT-only native core patch changes the binary fingerprint, so older recordings require re-recording for exact verification on the current setup. Broader deck families, held-out opponents, authorized human replay reconstruction, training/evaluation separation, and memory scaling beyond eight workers remain outstanding.

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
8000-LP, five-card, one-draw, exact-`DUEL_MODE_GOAT` profile, its recorded
RNG words, replay mode, and custom-rule-card count. It also checks agreement
between a `yrpX` wrapper and its embedded legacy replay. All five real modern
samples fail; all five differ in rule flags, four lack recorded RNG words,
three also use an unsupported legacy replay mode, and one differs in LP and
opening hand size. A match remains only a reconstruction candidate, not
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

Unfinished browser duels can now contribute explicit human choices to
behavioral cloning through a read-only, native-verified journal importer. It
freezes a private content-addressed snapshot and records the partial source
without an outcome label. A local 30 October 2026 audit found 41 usable,
non-forced choices across five unfinished games; one other saved game had no
human choice to import. These are data-pipeline evidence, not a policy-strength
result. The M4 held-out competitive gate remains open.
An additional held-out Tactical-v14 comparison of that 41-choice human-prefix
child found +2/32 wins on Max Suffridge Goat Control versus Jae Kim Zombie
and +4/64 wins on Ramon Ciriano Beastdown versus Roberto Martinez Phoenix.
The latter matched interval was above zero, but the child won only 24/64
against Tactical and split a separate direct parent match 33–31. These are
exploratory results, not a promotion; see [evaluation](evaluation.md#human-prefix-clone-against-tactical-on-unseen-decks--30-october-2026).

A [new 12-item PPO-child review queue](replay_audit.md#experimental-ppo-child-on-weak-sourced-deck-assignments-30-october-2026)
comes from eight replay-verified, visibility-audited Tactical duels on two
sourced pairings where direct parent play was weak. It includes a negative
visible Heavy Storm trade and a Breaker own-backrow target. The review UI
now finds the earlier optional Breaker activation even though its legal
alternatives are phase transitions, not Pass. These are review candidates,
not training labels; the queue has no human choices yet.

The matched-report comparator now exposes one paired score difference and
interval per candidate Main Deck alongside the overall result. This makes
deck-specific stalls visible during checkpoint selection; direct
child-versus-parent play remains a separate test.

The [larger-step PPO continuation](evaluation.md#larger-step-ppo-continuation-on-mixed-goat-decks-30-october-2026)
trained for 240 complete, replay-verified duels and changed 23 of 322
multi-option greedy choices on separate parent-policy states. Against
Tactical-v14, two unseen-Main-Deck blocks gave a pooled matched score gain
of 7.42 percentage points (paired interval +1.56 to +13.28); an independent
CombatHeuristicAgent block gained 7.03 points (interval 0 to +14.84).
Direct parent play was 105–87 on the first eight sourced holdout decks with
an interval crossing 50%, then 144–110–2 on 16 synthetic Main Deck mixes
with an interval above 50%, but a further six sourced tournament decks
reversed to 93–98–1. This is a promising mixed-deck self-play signal,
yet direct cross-deck superiority does not transfer consistently and the
absolute Tactical score remains weak. Keep the child experimental, v23
selected, and M4's exit gate open.

The [batched parent-KL fit](evaluation.md#batched-parent-kl-scoring-pilot-29-october-2026)
now scores variable-length legal-action sets in padded chunks while preserving
the full-label optimizer update. On the 244-decision Rhymus pilot it reduced
measured fit time from 86.66 to 14.65 seconds; its scalar and batched children
made the same choices on 171 separate multi-option Seattle states. This is a
training-throughput gain, not a competitive-strength gain.

A [fresh Rhymus/Beastdown on-policy Tactical pilot](evaluation.md#rhymus-and-beastdown-on-policy-tactical-pilot-29-october-2026)
re-labeled 244 player-visible policy decisions from four verified duels and
fit a 120-step, parent-KL child. It split 8–8 directly against v23 on new
seeds of the training deck family and scored 14–17–1 on four unseen Main Decks.
Its matched Tactical difference was +1.56 percentage points with a wide
interval crossing zero. Keep v23 selected; this fit does not close M4.

A [focused Rhymus Goat Control review queue](replay_audit.md#rhymus-goat-control-assignment-review-29-october-2026)
now offers eight high-margin decisions from two fresh, complete, verified
selected-v23/Tactical duels in the deck assignment where the held-out
policy performed poorly. Its Tactical alternatives remain unreviewed
suggestions; the queue is a route to broader human preference evidence,
not a strength gain.

A fresh 64-duel, both-deck-assignment held-out check of the experimental
visible-material-v5 child against selected v23 scored 30–34 on two previously
unseen tournament pairings. Against Tactical-v14 on separate matched seeds,
the child scored 22–42 and the parent 20–44; the paired difference interval
includes zero. The result and large assigned-deck splits are in the
[evaluation log](evaluation.md#resource-v5-child-on-two-fresh-tournament-pairings-29-october-2026).
Keep v23 selected. M4 still needs independently reviewed decisions that
generalize across the weak deck assignments and a measured self-play gain.

A [Seattle and Rhymus review queue](replay_audit.md#seattle-and-rhymus-parent-policy-review-queue-28-october-2026)
now offers 22 further high-margin selected-v23/Tactical disagreements from
eight replay-verified, visibility-audited duels on four Main Deck compositions
outside the selected checkpoint's training provenance. The queue was created
with no human labels. It expands the next authorized preference collection;
it is not evidence of policy improvement and does not close M4.

A [nine-choice New Jersey parent-review pilot](evaluation.md#nine-new-jersey-parent-review-preferences-pilot-28-october-2026) snapshotted 14 locally saved queue choices, converted the nine changed actions to replay-verified preferences, and fit an experimental 120-step child with parent preservation. It scored 17–15 directly against the frozen parent on two unseen Main Deck pairings, but 9–23 against Tactical-v14 versus the parent's matched 10–22. Both intervals include no improvement; keep v23 selected and continue collecting independently reviewed choices across more deck families.

A [400-step fit-length ablation](evaluation.md#longer-fit-on-the-same-nine-reviewed-choices) put the reviewed choice first at seven of nine training decisions, versus four of nine after 120 steps, but scored 13–19 against v23 and 14–18 against the shorter child on fresh direct games. Its matched Tactical comparison was inconclusive. More optimization on this nine-choice snapshot did not close the competitive gate; broader authorized decision data remains the next training input.

A new experimental preference child used 14 changed choices from 21 locally
saved high-margin reviews, with exact native replay and visibility validation.
It scored 38–25–1 directly against the selected v23 parent on four previously
unseen Main Decks, but only 13–19 on two newly transcribed 2005 New Jersey Top
8 Main Decks. A matched Tactical comparison favored the child by five wins
over 64 games but its paired interval crossed zero. Keep v23 selected: the
new-deck reversal fails the cross-family strength gate. The Deck fixtures,
label snapshot, training settings, hashes, and measured results are in the
[evaluation log](evaluation.md#high-margin-human-review-preference-pilot-on-new-2005-decks-28-october-2026).

The [new 2005 New Jersey review queue](replay_audit.md#selected-policy-on-new-2005-new-jersey-decks-28-october-2026)
adds 24 fresh human-review prompts from eight replay-verified, both-agent
reproduced policy/Tactical duels. A staged Thunder Dragon search correction
is available as an [opt-in Tactical ablation](evaluation.md#staged-thunder-dragon-search-tactical-ablation-28-october-2026):
it fixes two recorded empty-search decisions but scored 26–38 against the
unchanged Tactical-v14 baseline on 64 fresh direct games, with an interval
including 50%. Neither the review prompts nor this teacher variant closes
the learned-policy strength gate.

A separate [broader-deck review queue](replay_audit.md#broader-deck-parent-policy-review-queue-28-october-2026)
now exposes 14 high-margin disagreements from eight replay-verified v23/Tactical
duels on Warrior/Chaos and Zombie/Dimension Fusion pairings. The queue gives
human reviewers new deck contexts without treating Tactical's choices as
correct labels. A 64-duel clipped-PPO continuation of the earlier 14-preference
human-review child was replay-verified, but scored 135–121 against that child
on 256 fresh-seed direct games with a paired interval crossing 50%; it scored
64–63–1 against selected v23 on another 128 games. Neither result closes M4.
The [evaluation log](evaluation.md#human-review-preference-followed-by-self-play-28-october-2026)
records the settings, artifacts, and limits.

Two [published 2005 New Jersey Top 8 Main and Fusion Decks](evaluation.md#preference-child-on-two-new-2005-new-jersey-top-8-lists-28-october-2026)
now provide strict, training-unseen compositions for another seat-swapped
holdout. The 200-step human-preference child scored 26–37–1 against its
unchanged parent on 64 duels, with both assigned-deck splits below 50%.
This reinforces the decision to keep the child experimental; M4's measured
cross-deck strength and self-play gain gates remain open.

A new [source-backed 2005 New Jersey Beastdown Main Deck](../examples/decks/beastdown_ramon_ciriano_new_jersey_2005.ydk)
is distinct from the selected policy's training compositions and gives M4
another aggressive evaluation family. Two seat-swapped native random duels
reach terminal, replay-verify, and pass visibility checks. A stronger
200-step parent-KL fit learned all 11 changed local human-review preferences
on their training states but scored 27–37 directly against its unchanged
parent on 64 held-out Beastdown/Dimension Fusion duels, with only 2–30 when
assigned Dimension Fusion. Keep that child experimental and the selected
parent unchanged. The [measured result](evaluation.md#stronger-local-review-preference-fit-on-a-new-beastdown-holdout-28-october-2026)
shows that fitting a small preference set more strongly did not solve
cross-deck transfer; M4's competitive-strength gate remains open.

A [winner-only self-play imitation fit-length check](evaluation.md#three-epoch-winner-only-imitation-check-28-october-2026)
lowered label loss over three epochs, but split 32–32 directly with its
one-epoch child on unseen Main Decks and showed no clear Tactical-v14 score
gain over the selected parent. The current v23 parent remains selected; M4's
held-out competitive gain gate is open.

Extending the verified on-policy Tactical-v14 imitation fit from one to three
epochs reduced teacher-label loss, but the child scored 24–55–1 versus
Tactical on fresh held-out mixed decks, compared with the selected parent's
27–53 on the same schedule. The paired interval crosses zero; see the
[three-epoch check](evaluation.md#longer-fit-on-the-same-on-policy-tactical-labels-28-october-2026).
The parent remains selected. More epochs on these synthetic labels have not
closed the competitive gain gate.

A larger [160-duel policy-visited collection](evaluation.md#larger-on-policy-tactical-label-collection-28-october-2026)
fitted 12,973 synthetic Tactical labels across 40 new mixed-deck pairs. Its
v23 child tied the selected parent directly on 80 held-out games, then scored
18–61–1 versus Tactical against the parent's matched 26–53–1. Keep the
selected parent unchanged and seek independent action-quality feedback or a
different learning signal before scaling this teacher-label approach again.

A four-duel Tactical imitation continuation on previously unseen Rhymus/Zombie
2005 decks scored 35–28–1 against its parent on an independent Phoenix/Dimension
Fusion pairing. The paired interval includes 50%, and its matched Tactical
score improved by only 0.8 points with an interval including no gain. Keep the
parent selected; see the [transfer check](evaluation.md#four-duel-2005-behavioral-cloning-transfer-check-28-october-2026).

On ten additional, training-unseen tournament-card mixes, the selected parent
scored 24–55–1 against Tactical-v14 and that child scored 23–57 on the same
80-game schedule. The paired child-minus-parent interval includes no gain;
more small off-policy Tactical imitation is not yet a demonstrated path to
M4's strength gate. See the [broader holdout](evaluation.md#neural-policy-on-unseen-tournament-card-mixes-28-october-2026).

A larger, 32-duel on-policy Tactical-v14 label collection on eight new mixed
deck pairings fit 3,018 policy-visited choices. On ten separate, training-unseen
deck pairs, the child scored 36–44 directly against its parent; its matched
Tactical score improved by five points with a paired interval including no
gain. This does not justify promotion or satisfy the separate self-play gate;
see the [on-policy experiment](evaluation.md#on-policy-tactical-labels-on-mixed-tournament-cards-28-october-2026).

The action-attention v27 branch trained on those same 3,018 labels lowered
synthetic-teacher loss but scored 36–44 against the matched v23 child and tied
its Tactical score on fresh, training-unseen duels. Keep attention
experimental; see the [matched architecture check](evaluation.md#action-conditioned-attention-on-the-same-on-policy-labels-28-october-2026).

The current-core feature-v23 reference scored 25–39 versus Tactical-v14 on
two independent 2005 deck pairings. A matched Tactical mirror showed a
10.9-point policy score deficit with a paired 95% interval from −20.3 to
0.0 points. Eight new development duels on different seeds supplied a
24-frame, replay-verified human-review queue. No labels or strength gain are
claimed; M4 remains open. See the [evaluation](evaluation.md#current-core-policy-on-independent-2005-decks-27-october-2026)
and [review queue](replay_audit.md#current-2005-deck-development-queue-27-october-2026).

A 32-game current-core on-policy Tactical-v14 continuation fit 2,293
synthetic teacher choices but showed no held-out competitive gain: it tied
its parent at 9–23 against Tactical on Rhymus/Zombie and scored 6–26 versus
the parent's 9–23 on Phoenix/Dimension Fusion. The parent stays selected;
see the [experiment](evaluation.md#current-core-32-game-on-policy-tactical-continuation-27-october-2026).

The earlier 64-duel current-core Tactical imitation child now has a separate
[Rhymus/Zombie 2005 holdout](evaluation.md#current-core-imitation-child-on-a-different-2005-holdout-27-october-2026):
33–29–2 directly against its parent and a +10.9-point matched Tactical score
difference over 64 games per policy. Both paired intervals include no gain,
and its assigned-deck split remains uneven. Keep the selected reference and
M4's self-play gate unchanged.

A [128-duel half-Tactical PPO continuation](evaluation.md#half-tactical-ppo-continuation-from-the-current-core-child-27-october-2026)
replay-verified all 63,275 training decisions. On two unseen-deck families it
scored 61–66–1 directly against the imitation parent and improved matched
Tactical score by only 2.0 points, with both intervals including no gain.
This additional self-play mixture is not promoted; M4 remains open.

A [cross-pairing holdout](evaluation.md#cross-pairing-holdout-for-the-half-tactical-ppo-child-27-october-2026)
reused four training-unseen Main Decks in two new pairings and fresh seeds.
The same PPO child scored 66–60–2 directly against its parent, but its
matched Tactical score was 1.2 percentage points lower. Both intervals
include no gain. This checks matchup transfer within the available held-out
deck pool; it does not add a new unseen deck family or close M4.

**Status: in progress.** A PyTorch policy scores variable-length legal action sets from visible observations, and behavioral cloning fits replay-verified fingerprinted trajectories into versioned checkpoints. Feature version 2 distinguishes multi-target choices by visible target location even when IDs are hidden; version 3 uses field-slot memory of publicly known facedown opponent cards; version 4 encodes disabled zones and multi-zone choices; version 5 separately pools the player's initial Main Deck composition; version 6 distinguishes Attribute, number, and card-name announcements; version 7 distinguishes ordered card choices; version 8 encodes visible current monster stats and counter counts; version 9 separately pools publicly known opponent hand cards from schema v17; version 10 encodes public chain links in resolution-relevant order; version 11 is an equal-capacity unordered-chain ablation; version 12 binds direct and multi-card field choices to the visible card and current stats at each selected slot, with no additional parameters. Old checkpoints retain their versioned encoders. Demonstrator-seat metadata filters heuristic or self-recorded CLI-human decisions after full-duel verification. The checkpoint evaluator runs paired, seat-swapped tournaments on seeds excluded from training and supports direct checkpoint opponents. A heuristic-imitation baseline won 15/16 versus RandomAgent and 9/16 versus HeuristicAgent on held-out vanilla-fixture seeds; a version-2 retrain matched these results. Direct version-2 versus version-1 evaluation on experimental control/Chaos decks was 17/32, an inconclusive result with unaudited rules and visibility. Initial terminal-reward self-play from random imitation and two runs from the heuristic baseline did not demonstrate a greedy-policy strength gain. Version 5 was trained on one random-play Ground Collapse fixture and evaluated on held-out seeds: 11/16 versus RandomAgent and 7/16 head to head versus version 4; version 4 scored 14/16 versus RandomAgent on the same schedule. This does not show a gain from the Deck feature. Version 6 has no competitive result yet. A matched schema-v17 sourced-deck comparison gave feature version 9 an 18/32 head-to-head result against feature version 8, with equal exact teacher agreement on the 229 held-out known-hand decisions that had multiple options. The interval includes 50%, so no strength gain is established. On separately held-out Chaos Return and Warrior deck files, the same models split 16–16, with a strong 4/16 versus 12/16 deck-assignment split; an exact training-deck file-hash gate supports those saved checkpoints. New checkpoints also record order-independent Main Deck composition hashes and can use a stricter opt-in unseen-Main-Deck gate. See [the evaluation log](evaluation.md). No authorized tournament-human training set, robust held-out competitive result on audited deck families, or strength claim exists yet.

An opt-in feature-v26 policy now keeps separate means for each player's
visible cards, while loading the selected v23 checkpoint with exactly
unchanged logits. On eight matched Tactical-labeled policy replays it lowered
training loss, but lost 13–19 head to head against a matched v23 continuation
on the held-out New Jersey/Charlotte deck pair. It is not promoted; see
[the evaluation log](evaluation.md#separate-player-card-pools-feature-v26-27-october-2026).

A fresh 64-duel current-core Tactical-v14 imitation continuation was
replay-verified and visibility-audited before fitting. On two held-out
Phoenix/Dimension Fusion pairings it improved against Tactical-v14 from the
parent's 13–51 to 20–44 over matched 64 games (paired +10.9 points, interval
+1.6 to +20.3); an independent held-out Dimension Fusion mirror improved
from 5–27 to 11–21 over 32 matched games (paired +18.8 points, interval
+6.3 to +31.3). Direct matches against its parent were 33–30–1 and 17–15,
both inconclusive. This is a measured synthetic-teacher baseline gain on the
tested matchups, while the child remains weaker than Tactical overall and has
no human-play or self-play improvement evidence. Keep it experimental; see
[evaluation](evaluation.md#fresh-64-duel-current-core-tactical-continuation-27-october-2026).

A 64-duel PPO continuation from that fresh imitation child replay-verified
34,755 decisions and passed the visibility audit. On held-out Phoenix and
Dimension Fusion pairings, it split 31–31–2 directly against its parent and
scored 17–46–1 against Tactical-v14 versus the parent's 21–42–1 on matched
seeds. The paired Tactical difference interval includes zero. Retain the
imitation child as the experimental comparison; M4 still needs a measured
self-play strength gain. See [evaluation](evaluation.md#self-play-from-the-fresh-current-core-imitation-child-27-october-2026).

An opt-in Tactical-v14 opponent for the non-snapshot PPO branch was tested
on the same 64-duel training schedule. All 30,362 native decisions
replay-verified, but the child scored 13–48–3 against Tactical on unseen
Main Decks versus the unchanged parent's 21–42–1. The paired interval shows
a decline on that schedule, so keep the parent and do not promote this PPO
variant; see [evaluation](evaluation.md#tactical-baseline-opponent-in-ppo-27-october-2026).

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
A later 16-game AB/BA run on this host measured a 1.38× four-worker speedup in
both orders, with byte-identical trajectories and model tensors. One full arm
replay-verified and passed the visibility audit; see
[benchmarks](benchmarks.md#sixteen-game-ppo-rollout-workers).

A controlled 64-duel PPO continuation compared the usual 0.75 frozen-policy
opponent probability with 1.0, keeping the four-role training schedule fixed.
All 128 training duels replay-verified and passed visibility checks, but the
children split 33–30–1 directly on held-out Main Decks, scored 30–34 and
31–33 against their unchanged parent, and neither improved on the parent's
9–55 Tactical result. Opponent-mixture tuning alone did not close M4; see
[evaluation](evaluation.md#frozen-opponent-frequency-in-ppo-self-play-27-october-2026).

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

A fresh 64-duel fixed-policy corpus removed the earlier policy-change
confound. On 16 untouched seed-held-out duels, both visible-state critics had
higher terminal-outcome MSE than the constant training-return predictor, and
the v2-minus-v1 interval crossed zero. Keep both critics experimental and
prioritize stronger decision feedback or a different value objective before
using a critic as a PPO strength claim; see the [fixed-policy check](evaluation.md#fixed-policy-visible-state-critic-check-27-october-2026).

On those same 64 fixed-policy games, a single player-visible turn-4 card-count
margin only weakly ranked eventual wins (AUC 0.561, seed-group 95% interval
0.370–0.759). Life Point margin was 0.671 with overlapping uncertainty.
Neither retrospective margin establishes causal action value or supports a
shaped reward; see the [visible-margin diagnostic](evaluation.md#fixed-policy-visible-margin-outcome-diagnostic-27-october-2026).

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
The seed's final 1,000 decisions were an exact select/unselect loop. Self-play
sampling now shares the greedy policy's selection-progress mask, and PPO scores
the same filtered action set it samples. The first 16 lower-temperature games
now all terminate and replay-verify, including that seed; process-worker and
batched-inference runs produced identical trajectories and weights. This
removes a training protocol failure.
The complete 32-game masked continuation also terminated and replay-verified,
but scored 26–35–3 directly against its parent and 14–50 against Tactical-v14
on unseen Main Decks (parent 18–46 on matched Tactical games). Keep the
checkpoint experimental and prioritize action valuation or credit assignment.
A frozen-parent audit of that run found the same flagged choice in 49 of 62
sampled mistake candidates, especially Thunder Dragon timing and own-only
Nobleman. New sampled trajectories identify the selection mask explicitly and
the replay audit validates it; see [the replay audit](replay_audit.md#frozen-parent-check-after-selection-progress-masking).
Labeling 7,538 decisions from the fixed imitation checkpoint's own games
with Tactical-v14 and upweighting 1,891 disagreements also failed a held-out
strength check: the child scored 30–34 directly against that checkpoint and
16–47–1 against Tactical-v14 versus the parent's 20–44. More synthetic
teacher agreement alone is insufficient; prioritize independently reviewed
action value and outcome-sensitive learning signals.

A fresh broader-clone review queue now covers eight replay-verified duels on
three Main Deck compositions absent from that checkpoint's training history.
Its 24 linked frames include four conservative resource or Flip-monster flags,
but none is an expert label yet. This prepares independent decision feedback
without claiming a self-play strength gain; see
[the review queue](replay_audit.md#broader-clone-unseen-deck-review-queue-27-october-2026).

The fresh current-core imitation child now has its own balanced 24-frame
review queue from eight newly native-verified Phoenix/Dimension Fusion duels.
It includes Thunder Dragon timing, weak Flip Summoning, and own-monster Ring
target prompts. The policy and Tactical choices disagree at every frame;
none is a human label yet. Use the linked [current review queue](replay_audit.md#current-core-imitation-review-queue-27-october-2026) for independent
feedback, then reserve different Main Decks for evaluation if its labels
enter training.

A further 32-duel current-core Tactical imitation continuation trained on
Gravekeepers/Flip Control and Matt Goat Control/Warrior. It beat its parent
41–23 directly on an unseen Charlotte Zombie pairing, but lost 27–37 on a
second unseen Phoenix/Dimension Fusion family and did not improve against
Tactical-v14 on either family. Two own-resource mistakes in a verified Zombie
review queue also persisted. Keep the child experimental and prioritize
independently reviewed decision feedback and outcome learning; see
[evaluation](evaluation.md#additional-tactical-imitation-and-cross-family-holdout-27-october-2026).

The opt-in strict Heavy Storm card-advantage guard changed 48 Tactical-v14
choices across 16 of 64 previously verified policy duels, but scored
119–119–2 against unchanged Tactical v14 over a balanced 240-game sourced-deck
tournament. Keep it opt-in; the result does not improve the provisional
teacher or M4's learned-policy gate. The evaluator now records the correct
base teacher version for named Tactical variants; see [evaluation](evaluation.md#strict-heavy-storm-card-advantage-ablation-27-october-2026).

An [opt-in, observation-only own-loss guard ablation](evaluation.md#narrow-visible-own-loss-guard-ablation-29-october-2026)
corrected six own-card-loss choices on fixed parent states, but its 35–29
direct result and matched Tactical comparison did not establish a competitive
gain. Keep the selected v23 checkpoint unchanged. The M4 exit still requires
a learned policy with independently measured cross-deck strength and self-play
improvement.

A [240-duel cross-deck PPO continuation](evaluation.md#diverse-deck-ppo-continuation-from-the-larger-step-child-30-october-2026)
added three sourced training matchups to the experimental larger-step child.
All 138,789 recorded decisions replay-verified and passed visibility audit.
On four Main Deck holdout matchups, the continuation split 64–64 directly with
its starting child and scored 39–89 against Tactical-v14 versus 43–85 for the
starting child on matched games. The paired Tactical difference was −3.13
points (95% interval −14.06 to +7.81). One verified losing replay shows the
continuation taking zero Thunder Dragons with two legal copies while its
starting child selects both; this is a review case, not proof it caused that
loss. Keep both children experimental and the selected v23 checkpoint
unchanged. M4 still needs a transferable decision signal and held-out strength
gain.

## M5 — Search and other formats

An [offline branch diagnostic](evaluation.md#offline-action-branch-outcome-diagnostic-29-october-2026)
now reconstructs a verified duel to one decision and plays legal alternatives
with observation-only continuation agents. Six own-card-loss comparisons show
that a single terminal outcome can disagree with an immediate material
assessment. It is a test instrument, not online search; M5 still requires
player-consistent hidden-state sampling, held-out outcome evidence, and the
separately validated additional format below.

The [fixed-state review branch diagnostics](evaluation.md#fixed-state-branch-diagnostics-for-two-review-flags-30-october-2026)
now record the selected activation's visible material change through chain
closure. Both flagged recorded activations lost one material unit, while
changing either action left the winner unchanged in the fixed hidden deal.
The material diagnostic also reads the terminal observation when a resolving
chain ends the duel, including lethal Ring of Destruction fixtures where the
native snapshot retains the final public chain link. These are review and
correctness instruments; they do not
select an action using the actual hidden deal.

A [paired MR1 Bottomless/Synchro fixture](edison_research.md#bottomless-trap-hole-after-a-synchro-summon)
now tests the response window after Junk Warrior is Synchro Summoned. Both
branches finish, replay-verify, and pass the visibility audit. This is another
isolated protocol/ruling check; it does not certify an Edison simulator.


Evaluate policy-guided search and belief sampling only after M2 and M4. Search must sample hidden information from a player-consistent belief and must never inspect the real hidden state when choosing actions. Add Edison as a separately validated rules profile, not a changed banlist.

The [Edison feasibility audit](edison_research.md) records the official March
2010 Advanced Format restrictions as a checked data asset and lists the
remaining card-pool, native-rule, and observation validation gates. This is
M5 preparation; Edison duels are not yet supported.
The historical Edison target is now explicitly North American TCG play;
contemporary Konami policy makes promotional-card legality region-dependent.
The two external candidate pools do not establish regional eligibility, and
their differences must be adjudicated before a complete release whitelist can
be used. See [the regional scope audit](edison_research.md#regional-scope-of-the-historical-target).
An archived March 2010 Konami notice now directly establishes that newly
introduced Duel Terminal cards required another product release before they
were tournament legal. All 28 API-only DT01 candidates have now been checked
against their official English TCG card pages: each first listed non-DT01
printing is after the April 20 cutoff. Their dated source table is a partial
release exclusion asset, not a complete Edison whitelist. Konami's North
American product page separately excludes Vice Dragon after the cutoff,
bringing source-backed exclusions to 29 of the 34 named API-only
discrepancies. Restructer Revolution is included in the partial release pool
from its dated 2005 English booster printing and unrestricted March 2010 list;
this is an inference from those sources, not a complete regional whitelist.
Yu-Jo Friendship is provisionally included from its dated VIZ North American
book promotion, the official card record, and the period promotional-release
policy. Two older promotional cards and Darkness Destroyer's
cross-territory game promo still need period North American adjudication.
Konami's January 2010 Los Angeles SHONEN JUMP Championship coverage shows
Genesis Dragon in sanctioned play before the Edison cutoff, resolving one
community-only discrepancy. Exodius remains open. See the
[six-card discrepancy ledger](../configs/historical/edison_non_dt01_candidate_discrepancies_2010_04_20.tsv)
and [Edison audit](edison_research.md).
The candidate-disagreement audit command now verifies that the documented
DT01 and non-DT01 evidence covers every named API-only difference exactly
once, while keeping four remaining promotional discrepancies unresolved. It produces
no Edison whitelist; see [the Edison audit](edison_research.md).
The MR1 Synchro probe now applies a checksum-guarded in-memory correction for
Goyo Guardian's period generic-Tuner material text. Paired seed-5 duels use a
non-EARTH Tuner, accept or decline its battle recruitment effect, reach
terminal, replay-verify, and pass the visibility audit. This is one validated
historical card path, not a complete Edison profile; see the
[Edison audit](edison_research.md#goyo-guardian-historical-material-correction).
The separate Brionac fixture now restores the original any-field target and
repeatable activation in memory under MR1. Its full seed-5 duel activates
Brionac twice, first against an opponent's monster and then against itself;
the 1,111-decision trajectory replay-verifies and passes visibility checks.
This tests a material errata boundary, not the full Edison rules profile; see
the [Brionac audit](edison_research.md#brionacs-2010-effect-versus-the-pinned-current-script).
The MR1 Ryko fixture loads its checksum-pinned pre-errata script and chooses
an opposing target while the Flip Effect chain link is pending. Paired
complete-duel branches cover face-up and Set targets, three-card milling,
hidden target redaction, replay verification, and visibility. Other Ryko
responses and the wider Edison card audit remain open; see the
[Ryko audit](edison_research.md#rykos-historical-targeting-in-the-mr1-probe).
The separate MR1 protocol also checks the 2009 one-active-Field-Spell rule:
player 1's Umi replaces player 0's Yami in a complete, replay-verified,
visibility-audited duel. This narrows one historical mechanics gap without
certifying an Edison simulator; see the [Edison audit](edison_research.md#one-active-field-spell-mr1-check).
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
A third sourced MR1 fixture Synchro Summons Stardust Dragon from Junk
Synchron and Curse of Dragon, then tests both responses to an activated
Mirror Force. The chain branch negates and destroys Mirror Force and returns
Stardust at End Phase; the pass branch loses Stardust. Both complete duels
replay-verify and pass the visibility audit. This remains a narrow protocol
case, not an Edison historical-correctness or card-pool claim; see
[the Edison audit](edison_research.md).
An additional paired MR1 fixture puts Stardust Dragon opposite a newly
Synchro Summoned Black Rose Dragon. The optional Black Rose wipe offers
Stardust as a chain response: chaining preserves a separate monster and
returns Stardust at End Phase, while passing lets the wipe destroy all three
field monsters. Both terminal duels replay-verify and pass visibility checks.
This validates one interaction between two 2008 Synchro effects without
establishing a complete Edison rules profile; see [the Edison audit](edison_research.md#stardust-dragon-versus-black-rose-dragon).
The existing Exiled Force/Torrential Tribute summon-priority fixture now also
runs in the MR1 protocol, with both chain and pass branches replay-verified and
visibility-audited. It checks one rulebook-backed priority interaction while
leaving the complete historical Edison rules profile open.
An MR1 Desert Sunlight fixture now checks both owner-selected chain orders for
simultaneous Dekoichi and Gravekeeper's Spy Flip Effects. Both full duels
replay-verify and pass visibility checks under the pinned MR1 mode, advancing
one contemporary rulebook timing case without validating the full format.
A separate MR1 Soul Exchange fixture Tributes the opponent's official Sangan
for Caius and observes Caius Link 1, Sangan Link 2. Its complete native duel
replay-verifies and passes visibility checks. The paired GOAT fixture retains
the opposite format-specific order; this validates a narrow rules boundary,
not Edison as a whole. See [the Edison audit](edison_research.md).
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

A paired Dimension Fusion/Bottomless fixture now checks simultaneous revival
of two monsters with at least 1500 ATK. Bottomless banishes both without a
response; chaining Book of Moon to one protects it face-down while the other
is still banished. Both complete duels replay-verify and pass visibility
checks. This closes one staple multi-Summon branch, not general GOAT card
correctness; see [GOAT rules](goat_rules.md#bottomless-against-two-simultaneous-dimension-fusion-monsters).

A paired Cyber Jar/Bottomless fixture now checks the response after both
players place five revealed Normal Monsters in Main Phase. Bottomless removes
the five eligible face-up opposing Summons while leaving its controller's
face-down Summons. The pass branch leaves all ten. Both full duels
replay-verify and pass visibility checks. A separate attacked-Cyber-Jar duel
now checks the Damage Step exclusion: Bottomless stays unavailable and Set
through the remaining battle response windows, then the full duel
replay-verifies and passes visibility checks. See
[GOAT rules](goat_rules.md#cyber-jar-followed-by-bottomless-trap-hole).

A paired Cyber Jar placement differential now permutes five publicly revealed
monsters across hidden opponent zones. The placing player's private mapping
changes; the other player's complete observation and legal actions are
identical. Both full duels replay-verify and pass visibility checks. This
narrows the M1 hidden-information boundary for a high-use Flip monster; see
[GOAT rules](goat_rules.md#cyber-jar).

A second paired Cyber Jar differential carries those hidden permutations
through Nobleman of Crossout's target choice. The five legal target actions
and acting-player views remain identical before selection; targeting the same
zone reveals different actual cards only after resolution. Both full duels
replay-verify and pass visibility checks; see
[GOAT rules](goat_rules.md#nobleman-targeting-a-cyber-jar-set-monster).

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
An eight-game repeat found no clear whole-trainer speed gain despite identical
replays and model tensors, so feature reuse remains lower priority than the
observation and inference paths; see [the repeat](evaluation.md#ppo-rollout-feature-reuse-check-27-october-2026).

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
Skipping the chain GRU on empty-chain CPU decisions preserved outputs but did
not shorten an eight-duel complete-training run; the trial was reverted. See
[the pilot](benchmarks.md#empty-chain-gru-skip-pilot-27-october-2026).
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
Those frozen-rollout results used the earlier baseline accumulation bug; the
corrected update was evaluated separately: its 32-game child scored 14–18
against the selected parent and 15–17 versus Tactical v14 on unseen Rhymus
Goat Control versus Charlotte Zombie decks, compared with the parent's
16–16 Tactical result on the same seeds. The paired interval crosses zero;
the parent remains selected. See
[evaluation](evaluation.md#corrected-frozen-rollout-baseline-check-27-october-2026).

A 128-game PPO continuation with a lighter parent-KL penalty also failed the
held-out promotion gate. It scored 35–29 and 34–30 directly against its parent
on two unseen deck families, with both intervals crossing 50%; its Tactical
v14 results were no better than the matched parent's results. All 128 source
games replay-verified and passed the visibility audit. The recurring Thunder
Dragon and own-only Nobleman flags suggest focusing next on independently
reviewed action values and better credit assignment, rather than treating
training-game win rate as progress. See
[evaluation](evaluation.md#longer-lower-kl-ppo-continuation-27-october-2026).

A closed-form visible-resource ridge baseline now beats a constant
training-return prediction in point estimate on both held-out seeds and a
new unseen-Main-Deck pairing, but both 16-game paired intervals cross zero.
It remains an outcome-prediction diagnostic; no self-play policy gain has
been shown. See [the fixed-policy check](evaluation.md#fixed-policy-resource-regression-check-27-october-2026).

Frozen checkpoint mirror self-play separated value-model training from policy
updates. The Tactical-trained ridge lost to a zero-return baseline on mirror
games. A ridge trained on 96 mirror records then reduced outcome MSE to 0.727
on 32 held-out records and 0.790 on 16 different-deck records, against 1.000
for zero on both. The different-deck interval uses only four seed blocks.
This supports an opt-in PPO advantage-baseline ablation, followed by paired
held-out competitive evaluation; it does not yet satisfy M4's policy-strength
gate. See [the mirror check](evaluation.md#frozen-mirror-self-play-value-transfer-27-october-2026).

That ablation now exists and ran for 128 matched PPO games. The resource
baseline child scored 33–31 and 28–36 directly against the existing PPO
control on two unseen-Main-Deck pairings; both score intervals cross 50%.
Matched Tactical comparisons likewise have paired intervals crossing zero.
The outcome-prediction gain did not establish a policy-strength gain, so the
selected parent remains unchanged. See
[the ablation](evaluation.md#frozen-resource-ridge-ppo-ablation-27-october-2026).

An opt-in leave-one-out PPO baseline now uses other terminal duels from the
same rollout and learner deck to reduce return variance without consulting
the acting agent's hidden state. A matched 32-game ablation replay-verified
all training duels but tied the corrected frozen-baseline child against
Tactical v14 and did not establish a gain over the selected parent. It
remains experimental; see
[evaluation](evaluation.md#leave-one-out-ppo-rollout-baseline-27-october-2026).

The visible-resource v3 experiment adds replay-verified counterfactual
comparisons for own-only Nobleman and negative visible Heavy Storm trades,
including decisions where the recorded policy avoided the loss. A child fit
to 137 synthetic comparisons improved against Tactical-v14 on one held-out
Zombie family but regressed on a separate Phoenix family and retained an
own-only Nobleman activation. It remains experimental; M4 needs independently
reviewed resource decisions, broader outcome gains, and a separate self-play
improvement. See [the measured experiment](evaluation.md#visible-resource-v3-counterfactual-preference-experiment-27-october-2026).

An eightfold weight for the nine recorded-bad v3 comparisons did not fix the
held-out own-only Nobleman choice or establish a gain over the unweighted
child on two independent 64-duel families. Keep the weight experimental and
the reference unchanged; more synthetic weight alone has not closed M4.
See [the matched ablation](evaluation.md#recorded-bad-preference-weight-ablation-27-october-2026).

An opt-in feature-v27 action-to-visible-card attention branch preserved the
selected v23 policy's initial logits and fitted the same 437 verified
Tactical labels more closely than a matched v23 continuation. Held-out direct
comparisons split **13–19** on Rhymus/Zombie and **19–13** on Phoenix/Dimension
Fusion, each with a paired interval reaching 50%. The attention branch is not
promoted; this small synthetic-label experiment does not close M4's
cross-family strength gate. See [evaluation](evaluation.md#action-conditioned-visible-card-attention-feature-v27-27-october-2026).

The schema-v26 public-age input has now been exercised in a controlled
feature-v28/v29 pilot. Eight current-core, verified policy duels supplied 710
Tactical-v14 synthetic choices. On 32 held-out, unseen-Main-Deck games against
the selected v23 parent, both children scored 16–16 with identical individual
game outcomes; direct v29 versus v28 also split 16–16. The new age input was
nonzero after fitting but changed no greedy choice on 185 aged-Swords training
states. This does not close M4's competitive-gain gate. Keep v23 selected and
seek independent timing labels before a larger age-specific run; see the
[measured pilot](evaluation.md#public-face-up-age-v29-controlled-pilot-28-october-2026).

A paired pinned-native Airknight Parshath/Ring of Destruction fixture now
checks the competitive choice at attack declaration: passing Ring allows
1,900 battle damage and Airknight's draw, while pre-errata Ring destroys
Airknight before damage, deals 1,900 effect damage to each player, and prevents
the draw. Both branches complete, replay-verify, and pass the visibility audit.
This adds one M2 historical interaction; the wider correctness gate remains open.

A second paired Airknight fixture checks Book of Moon at attack declaration.
Setting Airknight ends the attack without a replay, damage, or draw and leaves
no Main Phase 2 Flip Summon; passing Book allows 1,900 damage and the draw.
Both branches complete and pass replay and visibility checks. The broader M2
gate and M4 learned-policy strength gate remain open.

A larger 240-duel mixed-deck PPO continuation of the selected v23 policy
completed without a decision cap; all 123,494 recorded decisions replay-verified
and passed the visibility audit. On unseen Main Decks it scored 33–31 directly
against its parent, with a paired interval spanning 50%, and 15–49 versus
Tactical-v14 compared with the parent's matched 16–48. The checkpoint is not
promoted: increasing self-play volume on this schedule did not satisfy M4's
held-out strength gate. See [the experiment](evaluation.md#larger-mixed-deck-ppo-continuation-of-selected-v23-28-october-2026).

The 240-duel child changed only 7 of 710 greedy choices on separately
verified parent-policy states. A matched ablation lowering parent KL from
0.5 to 0.05 changed 8 of 710, then scored 29–34–1 against the selected
parent on unseen Main Decks. It improved its matched Tactical-v14 score
from 15–49 to 20–44, but the paired interval still reaches zero and a fresh
64-game direct match between the two children split 32–32. Neither is
promoted. The next M4 experiment should improve the decision signal or
credit assignment and test it on new deck families and seeds; larger volume
or weaker KL alone has not met the exit. See [the ablation](evaluation.md#ppo-parent-kl-ablation-after-the-240-duel-plateau-28-october-2026).

A matched 240-duel continuation raised learner sampling temperature from
1.0 to 2.0. All 132,618 saved decisions replay-verified and passed the
visibility audit. On 710 verified parent-policy multi-option states it
changed six greedy choices. On unseen Main Decks it split 33–31 directly
with the selected parent; against Tactical-v14 it scored 22–42 versus the
parent's matched 16–48, then 20–44 versus the parent's 17–47 on fresh
seeds. Both paired Tactical difference intervals reached zero. A fresh
direct match favored it 37–27 over the temperature-1 child, with the paired
interval touching 50%. Keep the parent selected; higher rollout temperature
is a useful ablation but does not close M4's held-out gain gate. See
[the experiment](evaluation.md#ppo-learner-temperature-ablation-after-the-240-duel-plateau-28-october-2026).

An opt-in, terminal-only GAE estimator now uses the frozen player-visible
resource ridge to assign local PPO advantages between learner decisions.
In a matched 240-duel test against the existing return-minus-value baseline,
both arms reached terminal and all 247,466 combined recorded decisions
replay-verified and passed the visibility audit. On a Main-Deck holdout
separate from both policy and value training, lambda-0.5 scored 28–35–1
directly against the control and 16–47–1 against Tactical-v14, versus the
control's matched 21–42–1. The paired Tactical difference favored the
control. Neither child beat the selected parent convincingly. Keep GAE
opt-in and v23 selected; M4 still needs an independently useful decision
signal and competitive gain across deck families. See
[the ablation](evaluation.md#frozen-visible-value-local-advantage-ppo-ablation-28-october-2026).

A replay-verified raw-logit diagnostic on eight previously inspected,
training-seed-held-out parent-policy duels measured the selected v23 parent
against its 240-duel PPO child. Only 7/710 multi-option choices changed; the
parent's top-two action-score margin was at most 0.191 for all seven changes,
while unchanged choices had a 2.840 median margin. This does not explain the
competitive plateau by itself, but it narrows the next M4 experiment toward
independently sourced corrections of confidently wrong decisions, checked on
new deck families and seeds. See [the diagnostic](evaluation.md#raw-action-margin-diagnostic-for-the-240-duel-ppo-child-28-october-2026).

The review selector now offers an opt-in raw-logit margin threshold and ranking
mode. A local queue from those same eight verified duels retains 22 distinct
high-margin policy/Tactical disagreements for human review; the synthetic
alternatives are not training labels. This targets the high-margin error
hypothesis without claiming those 22 plays are mistakes. See the
[review queue](replay_audit.md#high-margin-policy-disagreements-for-human-review-28-october-2026).

A separate six-duel [diverse-deck queue](replay_audit.md#diverse-deck-high-margin-parent-review-28-october-2026)
now offers 23 high-margin disagreements across three additional Deck pairings
and both policy seats. All 3,295 source decisions replay-verified and passed
visibility checks. This expands the independent human-review surface for M4;
the queue starts unlabeled and establishes no policy-strength gain.

The local replay server now offers a browser game creator for two selected AI
agents and Decks. It records complete native duels, replay-verifies them, and
opens reviewer-only visual replays. Browser human-versus-AI play is available
at `/games/play` through the local server. A live native duel remains on one
worker thread across requests, and the browser receives the human seat's
observation and legal actions. Illegal and stale choices are rejected. A completed duel
is replay-verified, audited for player visibility, and saved as a `human_web`
self-recording with a separate postgame full-information replay. Unfinished
games remain in server memory and are lost when the server stops. The terminal
`HumanAgent` also exercises the same action contract.
Locally created games can now pass through the existing visible-decision
review scanner with an explicit seat. Their heuristic flags are linked to
viewer frames and stored separately from trajectories and human annotations;
no flag is treated as a training label. On a verified 543-decision Tactical
versus Random game at seed 4321 it reported two flags for Random and none for
Tactical. A separate verified 348-decision selected-policy-versus-Tactical
game at seed 6803 produced no flags for either seat. This is a narrow
diagnostic, not a policy-strength comparison.
The game creator can now open a save-enabled review queue for flagged choices
made by its selected neural policy. Policy games carry checkpoint and
inference provenance, while non-policy AI games cannot be misidentified as
human `self_recorded` demonstrations. Queue generation verifies the native
replay, writes a player-visible label page, and keeps full-information
reveals separate. The heuristic flag and Tactical alternative are prompts,
not endorsed training labels; a person must select a legal alternative.
Before serving a generated policy queue, the creator now independently
reproduces every recorded choice by the named policy checkpoint, in addition
to native replay and visibility verification. The check runs even when the
queue already exists, so a saved queue cannot bypass policy provenance.

An [action-encoding audit](evaluation.md#legal-action-representation-collision-audit-28-october-2026)
found no collision in the current 22 shortlisted review comparisons, but did
find that v23 cannot distinguish two card-announcement prompts in the source
duels. Experimental v30 resolves the observed option-choice collisions. An
opt-in v31 now represents announced card IDs exactly and uses only public
known-hand information; the same eight-duel audit found no distinct-choice
collisions. Its warm start preserves v23 logits, but it has not been trained
or competitively evaluated. Obtain independent reviewed announcement labels
and run held-out strength checks before considering promotion. M4's policy
strength gate remains open.

An [experimental resolved-material diagnostic](evaluation.md#resolved-material-changes-for-monster-abilities-and-card-effects-28-october-2026)
now measures both monster ability activations and Spell/Trap effects on
replay-verified, player-visible self-play trajectories. It does not produce
counterfactual expected card advantage or training labels; candidate reward
shaping still requires a controlled held-out strength experiment.
The paired 64-duel outcome check found only weak winner associations for
both ability and Spell/Trap material changes, with game-level bootstrap
intervals crossing zero. Do not promote raw material delta to a training
reward on that evidence; see the [outcome analysis](evaluation.md#does-immediate-material-change-track-the-duel-winner).
An [action-level material preference experiment](evaluation.md#action-level-material-comparisons-29-october-2026)
now compares own-only Nobleman and negative Heavy Storm activations, boss
self-banish choices, and Tribe Type choices using only the acting player's
visible state. The broader 754-comparison child did not show a reliable gain
against its parent or Tactical on unseen Main Decks. Keep the v23 reference;
further M4 work needs a value signal that improves complete-duel outcomes
across opponents, not just its own preference loss.
The [v5 avoidance experiment](evaluation.md#avoiding-visibly-wasteful-activations-with-all-legal-alternatives-29-october-2026)
broadened each negative activation comparison to all other offered actions.
It fit 783 verified comparisons but split 32–32 with v4 and did not show a
reliable gain against the parent or Tactical. Its held-out top-action mistake
count was unchanged from v4. Keep this rule and checkpoint experimental.
The [masked-parent pilot](evaluation.md#masked-parent-bad-action-training-pilot-28-october-2026)
instead removes probability from flagged bad actions while keeping the frozen
parent's relative ranking of other legal moves. The 85-comparison child
avoided both flagged top choices on 16 held-out fixed states and won 55–41
across two direct parent blocks, but the larger matched Tactical block was
24–40 versus the parent's 25–39. The selected v23 reference remains unchanged.
The next M4 trial needs broader reviewed activation and target decisions,
fresh deck families, and repeatable own-card opportunity rates alongside
held-out competitive strength.
A [larger masked-parent fit](evaluation.md#scaling-masked-parent-preferences-to-783-comparisons-29-october-2026)
used all 783 verified v5 comparisons from 187 duels. It matched the small
child's 0/16 held-out flagged top choices and split 17–15 against that child
in fresh direct games, with the paired interval crossing even play. Scaling
the same automated rule has not established a stronger checkpoint; prioritize
better decision labels and opponent transfer before promotion.
A [focused own-card removal review queue](replay_audit.md#focused-own-card-removal-review-queue-29-october-2026)
now offers six independently replay-verified v23 choices across four source
duels. One forced Breaker target is represented by its earlier optional
activation, so a reviewer can choose Pass if that was the actual mistake.
These are review candidates only; wait for independent legal-action choices
before treating them as training labels.
The [v6 optional-own-loss ablation](evaluation.md#optional-own-card-effect-activation-ablation-29-october-2026)
adds upstream Breaker, boss-banish, Tribe, and Torrential activation contexts.
A higher bad-choice weight reduced own-only Nobleman choices in eight fresh
games, but both tested children scored 15–17 directly against the parent on
unseen Main Decks. Keep the selected v23 checkpoint and M4 strength gate open.
The [expanded inference guard](evaluation.md#expanded-own-loss-guard-held-out-strength-check-29-october-2026)
subsequently beat the same unguarded checkpoint 144–112 directly and improved
matched Tactical-v14 results by 14 wins over 256 held-out games. Local viewer
games now use the guarded inference mode. The neural checkpoint remains
unchanged, still loses to Tactical-v14, and M4's learned-strength gate remains
open.
An [idle own-only Ring ablation](evaluation.md#idle-own-only-ring-inference-experiment-29-october-2026)
adds an opt-in v3 inference filter without changing the selected checkpoint or
local viewer. It defers Ring on the policy's own turn with no chain and no
opposing face-up monster, while preserving visible lethal damage. Against
Tactical-v14 it changed five of 256 matched held-out outcomes, all in v3's
favor, but v3 still lost most games. A [direct v3-versus-v1 comparison](evaluation.md#direct-v3-versus-v1-ring-guard-comparison)
then scored 131.5/256 against a v1-versus-v1 control of 128/256 on two fresh
blocks; its paired interval crosses zero. Keep it experimental and pursue a
learned general action-value model and independent human review of edge cases.
An [exact guard-distillation child](evaluation.md#exact-visible-guard-distillation-into-v23-29-october-2026)
reduced held-out fixed-state guard violations from seven to four, but scored
63–65 directly against its v23 parent on 128 unseen-deck games. Its matched
Tactical gain was inconclusive. Keep the inference guard for local play and
continue pursuing a learned policy with a verified complete-duel gain.
A [matched complete-replay audit](evaluation.md#matched-complete-replay-own-card-loss-audit-29-october-2026)
found zero of six previously observed clear own-card-loss flags in 16 guarded
duels on the same seeds, seats, decks, and checkpoint. It also found an MST
chained to a resolving one-shot Spell; this narrower behavioral improvement
does not imply a general card-advantage model. The small sample scored 3/16
guarded wins against Tactical versus 4/16 unguarded; use the larger 256-duel
study for the existing guard's strength estimate.
The [idle own-only removal audit](evaluation.md#idle-own-only-removal-activation-audit-29-october-2026)
now counts optional MST and Raigeki Break activations before their target
prompts. In the same paired replay set it found one parent MST own-only
activation and none in four guarded opportunities; neither set offered an
idle own-only Raigeki Break opportunity. Broader source duels and independent
activation reviews remain necessary before claiming general material judgment.
An [opt-in one-shot response ablation](evaluation.md#one-shot-response-guard-ablation-29-october-2026)
defers MST on an isolated activated Normal Spell/Trap using only the public
chain source and static printed Type. It removed the remaining one-shot MST
review flag in 16 matched verified games, but scored 96 rather than 95 wins
against Tactical-v14 over 256 held-out paired games. This is too little
strength evidence to replace the current local-play guard or count as learned
improvement.
An [outcome-blind Ring coverage audit](replay_audit.md#idle-own-ring-coverage-and-outcome-blind-review-29-october-2026)
found no applicable Ring decisions in the current guard-distillation corpus.
A fresh 128-duel verified batch found 47 applicable prompts and 14 v1-policy
Ring activations; all 14 are now available for independent review. The next M4
step is to collect explicit human judgments across own-card activation and
target decisions, train on reviewed preferences, and require a held-out
complete-duel strength gain before selecting a new checkpoint.
The same fixed batch exposed two negative visible Heavy Storm trades and one
own-monster Ring target with a safer opposing target. A separate verified
review queue now includes these three cases; the Tactical alternative also
chooses Heavy Storm in both Storm positions, so reviewer rejection should
target the avoidable activation rather than accept a weak automatic label.
An [offline branch check](evaluation.md#guarded-replay-branches-for-own-card-losses-29-october-2026)
now reproduces guarded source inference through terminal continuations. In
three flagged decisions, the recorded and alternate lines had the same winner
on the recorded hidden deal despite different duel lengths. These branch
winners are not suitable preference labels; M4 still needs independent review
and a held-out competitive gain.
An [opt-in Ring target guard ablation](evaluation.md#own-ring-target-filter-ablation-29-october-2026)
corrected one conspicuous own-target choice in a fixed state but lost one more
than the v3 control over 128 matched, unseen-Main-Deck direct games. In the
changed game the own-target line won and the opposing-target line lost. This
shows why a visible one-card trade cannot be promoted as general action value;
v4 remains experimental, and the learned-policy strength gate stays open.
The [combined outcome-blind own-card review queue](replay_audit.md#idle-own-ring-coverage-and-outcome-blind-review-29-october-2026)
now puts 17 verified Ring and Heavy Storm decisions in one place. Review
choices or explicit rejections from that queue are the next usable human
signal; its suggested alternatives and offline branch winners are not labels.

An [on-policy Thunder Dragon teacher experiment](evaluation.md#on-policy-staged-thunder-dragon-correction-29-october-2026)
corrected two fresh staged-search diagnostics, but the preserved child scored
129–126–1 against its parent over 256 unseen-deck duels; the paired interval
includes 50%. This does not close M4 or address the broader own-card removal
failure. Prioritize explicit human review of activation and target choices,
then evaluate the resulting policy for fewer verified own-card losses and a
complete-duel strength gain. Keep the selected v23/v1 checkpoint meanwhile.
The [fresh own-card baseline](evaluation.md#fresh-own-card-decision-baseline-29-october-2026)
verified 64 complete selected-policy duels and found four remaining visible
own-card flags, including two negative-material idle Ring activations. Those
four decisions have been added to the single 55-item local review queue.
Human choices in that queue, followed by held-out replay-error and duel-win
checks, are the next M4 evidence needed; the flags alone are not labels.
The [varied-deck baseline](evaluation.md#varied-deck-own-card-baseline-29-october-2026)
adds 64 complete games across four 2005 pairings and still finds four idle
own-only Ring activations, three negative visible Heavy Storm trades, and an
MST chain to its own resolving one-shot card. These eight cases are in the
63-item local review queue. The next M4 policy candidate should be trained
only from authorized reviewed choices, then compared against the unchanged
selected checkpoint on fresh decks and seeds; the queue itself does not
demonstrate improvement.
The [fresh v3 Ring guard transfer check](evaluation.md#fresh-ring-guard-direct-transfer-check-29-october-2026)
suppressed six fresh idle own-only Ring activations, but a 256-duel direct
comparison against v1 tied its matched v1 control at 127 wins, 127 losses,
and two draws. The guard remains experimental; use independent human review
and wider competitive evidence before selecting it as the default.
A later [seven-case Ring branch diagnostic](evaluation.md#seven-idle-own-only-ring-activation-branches-29-october-2026)
reproduced fresh selected-policy activations against legal Tactical
alternatives. All seven pairs had the same winner on their exact recorded
hidden deals, despite different continuation lengths. The remaining M4 gate
is still independent activation review followed by held-out competitive
evaluation; fixed-deal branch winners cannot supply the training labels.
The [strict preference-score holdout gate](evaluation.md#strict-reviewed-preference-holdout-gate-29-october-2026)
now rejects training replays, seeds, and optionally Main Deck compositions
before fixed-state human-review scores are reported. It validated 11 older
reviewed choices as held out for the selected parent and rejected a replay
used to train a child. Use this gate for M4 diagnostic scores alongside
fresh complete-duel comparisons; it is not a substitute for them.
The [cross-review transfer check](evaluation.md#cross-review-transfer-check-for-human-preferences-29-october-2026)
trained on 11 broader human choices and ranked all 11 first after 400 steps,
but ranked only one of nine untouched New Jersey choices first and scored
27–36–1 against its v23 parent in 64 held-out duels. Training on the nine
New Jersey choices likewise ranked only one of 11 untouched broader choices
first. The next M4 training set needs more varied, independent activation and
target judgments; fitting a small review set more tightly has not produced
transfer or a demonstrated strength gain.

The synthetic preference generator now defaults to
`visible_audit_no_weak_flip_v14`: weak Flip Normal Summons remain human-review
questions after exact-state Magical Merchant branches disagreed with a blanket
Set label. Old v1/v2 rule IDs still reproduce historical experiments. This
removes seven uncertain labels from the six fresh flagged source replays; it
does not count as a learned-policy gain. See the [evaluation entry](evaluation.md#weak-flip-synthetic-label-correction-29-october-2026).

The [eight-case own-loss fit](evaluation.md#eight-case-own-loss-preference-transfer-29-october-2026)
removed the disfavored action from first place on all eight source positions,
but scored 55–73 against its parent over 128 fresh, unseen-deck duels (95%
paired interval 34.38%–52.34%). The token-only Ring condition appeared only
once in 96 source duels. Keep this child experimental; prioritize diverse,
independently judged upstream decisions before another M4 policy promotion.

An [opt-in negative-trade Heavy Storm ablation](evaluation.md#negative-visible-heavy-storm-trade-ablation-29-october-2026) now defers three observed activation mistakes before targeting. On fresh unseen Main Decks it scored 65–63 directly against v1, with a matched v1 control of 64–64, tied v1 at 35 wins each against Tactical on the first 128 games, and scored 66 versus v1's 67 wins against Tactical on a further 256 games. A replay-verified changed game illustrates that avoiding an immediate four-own/two-enemy Storm trade need not win that deal. Keep v8 experimental and v1 selected; M4 still needs transferable reviewed choices and a trained complete-duel strength gain.

A paired [Airknight Parshath versus Spirit Reaper fixture](goat_rules.md#airknight-parshath-against-spirit-reaper) now verifies that a Set Reaper survives battle while Airknight pierces for 1,700 damage and draws, or deals no damage and draws nothing when Waboku is chained. Both complete duels replay-verify and pass the visibility audit. This advances M2 correctness; it does not imply learned policy improvement.

A [Skilled Dark Magician/Skill Drain removal fixture](goat_rules.md#skilled-dark-magician-spell-counter-timing) now tests counters after the continuous Trap leaves the field. Mystical Space Typhoon removes Skill Drain, then Upstart Goblin raises Skilled from one to two counters. The complete native duel replay-verifies and passes visibility checks. This closes one M2 timing branch, not general Spell Counter correctness.

A paired [Skilled Dark Magician three-counter fixture](goat_rules.md#skilled-dark-magicians-three-counter-summon) now verifies its Dark Magician Summon and the historical no-target activation with opponent-only hand and Deck verification. A Deck-order permutation leaves the verified visible prefix and legal choices unchanged. Both complete native duels replay-verify and pass visibility checks. This advances M1 and M2 without certifying all Skilled interactions.

The [fresh tournament-card mix V11 holdout](evaluation.md#fresh-tournament-card-mix-holdout-for-v11-29-october-2026) used 16 previously unseen Main Deck compositions. V11 scored 31–33 directly against the selected v23 parent; on matched Tactical-v14 games it scored 18–45–1 against the parent's 24–39–1. The paired Tactical difference was −9.38 percentage points (95% interval −21.88 to +1.56). This broader sample does not justify promotion. Keep M4's learned-strength gate open.

The [distinct current-core human-review trial](evaluation.md#distinct-current-core-human-review-preference-trial-29-october-2026) verified 24 saved label files across four queues and deduplicated them to 26 changed preferences. A 120-step child trained on those corrections scored 30–34 directly against v23 over 64 unseen-deck duels and tied v23's 25% score rate against Tactical on a separate matched 64-game block. Keep v23 selected and M4 open; the next review collection should add independent corrections across additional decks and decision types before another promotion test.

An [opt-in weighted PPO advantage normalization pilot](evaluation.md#weighted-ppo-advantage-normalization-pilot-30-october-2026) won 35–29 directly against a matched unnormalized child on four unseen Main Decks, but both children scored 30–34 against selected v23. The two extra normalized wins against Tactical-v14 were confined to one deck assignment; the paired interval touched zero. Keep the option experimental and M4 open. Better advantage scaling alone has not established competitive improvement over the selected policy.

The [240-duel normalization transfer](evaluation.md#240-duel-normalization-transfer-against-the-preserved-larger-step-control) replay-verified all 143,902 decisions, then scored 58–68–2 directly against the preserved unnormalized child on unseen decks. On a separate exact matched Tactical schedule it scored 43–84–1 versus the control's 46–81–1; the paired interval includes zero. This stronger ablation leaves the selected checkpoint and M4 gate unchanged. The next policy work needs a more informative decision signal, especially independently reviewed activation and target choices, rather than another scaling-only PPO adjustment.

An [opt-in feature-v32 PPO pilot](evaluation.md#feature-v32-ppo-action-choice-pilot-30-october-2026) removed six distinct-choice `select_option` encoding collisions found in 3,987 multi-action decisions. All 48 training duels in each arm replay-verified, but the v32 child scored 30–33–1 against the matched v23 child and 21–42–1 against Tactical-v14 versus v23's 26–38 on identical held-out schedules. This does not justify promotion. Keep selected v23 and M4's competitive-strength gate unchanged; collect more independent decision feedback before another feature or PPO scaling trial.

### Future EDOPro human client

Update (2026-10-30): The local game creation page can start a private pinned
EDOPro policy room and list its saved native replay. It links the GOAT AI
viewer only after independent replay reconstruction succeeds. This removes
the manual host command from the usual play path; recordings remain excluded
from automatic training pending the source and historical-rules gates below.
The same page can now save explicit human-seat confirmations for optional
decisions directly beside the verified replay. It rechecks the selected actions
against the native response stream before replacing an annotation file. EDOPro
can still generate automatic responses, so these opt-in confirmations do not
open the automatic training gate.

Pinned-host update (2026-10-30): The optional room now supports the project's
own pinned native core and checksum-guarded historical script corrections.
The selected v23 checkpoint completed a 20-turn, 485-response TCP-room duel
against an EDOPro-protocol client. Its saved replay reconstructed all 485
player-visible decisions on the pinned core; there were no retries or reported
Lua errors. The separate desktop GUI still needs a complete match on this
specific room, and broad historical correctness and training admission remain
open. This advances M1/M3 without closing either gate.

Update (2026-10-30): An optional local room launcher now gives EDOPro's human
seat the selected GOAT AI policy as its opponent. An EDOPro-protocol TCP client
completed an 8-turn, 276-response match; the mirror saved 276 audited
player-visible decisions and an exact same-install replay. A direct-core
policy-seat trial also completed 397 responses. These establish the policy
adapter and local room path at the protocol level. A full match played through
the desktop GUI on this new policy room, historically validated external
scripts, and admission of those records to training remain open. See
`scripts/serve_edopro_policy.py` and the current [research](research.md#edopro-live-client-bridge-probe-2026-10-30).

An EDOPro bot connection could let a human play this policy in the EDOPro
client. Project Ignis's current WindBot fork is an EDOPro-compatible bot
client, but its [FAQ](https://github.com/ProjectIgnis/projectignis.github.io/blob/main/faq.html)
says built-in bot play supports Master Rule 3 and later, and forcing older
rules is unsupported. We therefore cannot treat its GOAT behavior as a
working bridge. A prototype should first join a private local GOAT room as a
bot, complete one duel using recorded native responses, and verify both
clients use the same GOAT rule flags, card IDs, database, and scripts.

An [external headless host probe](research.md#edopro-live-client-bridge-probe-2026-10-30)
now completes a random-versus-random GOAT-flag duel and re-simulates its
EDOPro replay exactly on its own bundled core. Its legacy 15-card Extra Deck
check needs a GOAT-specific fix or an independently validated bypass. Our
pinned core diverged at response 92, so asset parity and a policy-seat adapter
remain unproven.
The same host also completed a [private TCP room probe](research.md#edopro-live-client-bridge-probe-2026-10-30)
with an EDOPro-compatible Python client: 34 turns, 715 legal responses and an
exactly re-simulated `.yrpX` on its own core. The pinned core diverged at
response 289 on this second replay. A subsequent [desktop-client probe](research.md#edopro-live-client-bridge-probe-2026-10-30)
joined the real EDOPro 41.0.2 GUI to the GOAT room, set a monster, and received
the AI's turn before the human surrendered on turn 3. Its host log contains
23 responses with no retries or reported Lua errors. The missing Sheep Token
script in an earlier trial, exact asset parity, full-match GUI verification,
the policy seat, and a training-safe human trajectory are still open. The
client's separately saved replay has a two-byte post-LZMA trailer; the bounded
reader now accepts it and finds the same 235 packets and 23 embedded
responses as the host replay. That structural match does not validate training
reconstruction.
The external host's missing Sheep Token script can now be checked and filled
with a comment-only local shim after validating its normal Token metadata.
A direct-core Chaos-versus-Chaos probe then completed 48 turns with both
players summoning Sheep Tokens, zero retries, and zero reported Lua errors.
This removes one external-host asset blocker; it does not certify a desktop
client duel or the historical rules in that package.
An explicit unpatched comparison mode can now reconstruct all 627 responses
of a complete headless duel on the external install's own core and scripts,
including a player-visible decision audit. It is excluded from strict GOAT
intake because those external scripts have not passed this project's historical
patch checks. The short desktop trial ends by surrender, which leaves its
legacy response sequence nonterminal. A complete desktop duel on a matched,
historically validated install is the next replay-data gate.
Both the host and EDOPro desktop copies of the surrendered trial now pass an
explicit partial reconstruction and player-visibility audit for all 23 saved
decisions on the exact external install. They remain ineligible for training
because the duel did not reach a native terminal state and the external scripts
have not passed historical GOAT validation. A later GUI trial disconnected
while awaiting a hand-size discard on turn 3, leaving full desktop completion
unproven. The bridge must handle every EDOPro decision prompt before it can
be considered a complete human match path.

Update (2026-10-30): The pinned policy room now has one complete seven-turn
EDOPro 41.0.2 desktop GUI match. The human answered hand-size discard prompts;
the host saved 165 responses, zero retries, and zero reported Lua errors.
Independent replay verification reconstructed all 165 player-visible decisions
and the AI's terminal win. This closes the first complete-GUI-match gate.
Broader prompt coverage, historical rulings validation, and training admission
remain open; this match is review-only.
New room recordings now carry replay-checked Main/Extra Deck composition hashes
in metadata and the review trajectory, so evaluation can group games by Deck
without mistaking player names for Deck identifiers. Draw order is omitted.
An explicit `--human-authorization self_recorded` room option now records the
human client seat and self-recording permission alongside those identifiers.
EDOPro can generate automatic responses, so the record cannot yet isolate
deliberate human choices; raw cloning admission remains off.
EDOPro `self_recorded` annotations now validate the authorized human seat and
require the recorded action itself, so a later explicit confirmation cannot
mistake an AI response or retrospective alternative for a human demonstration.
A separate `verify_edopro_human_labels.py` command replays the EDOPro room
recording before validating specific confirmed choices and reports their exact
annotation hash. It remains a review artifact, not an admitted training set.
The `confirm_edopro_human_actions.py` command accepts the viewer's one-based
decision numbers, verifies the replay, rejects AI-seat and forced responses,
and atomically saves the authorized human-action annotation. A browser review
queue and training admission still require separate gates.

For training, the bot must log the EDOPro server's decision prompt, the AI's
player-visible state and legal responses, and the response it sends. The
human's decisions require equivalent logging at the server or a validated
legacy replay reconstruction; the bot's own network view alone cannot supply
the human's complete legal-action set. Importing an EDOPro replay alone is not
a substitute for that live log: the current reader has not established exact
reconstruction or player-knowledge validation for real GOAT EDOPro files.
Keep the native `.yrpX` for visual playback, and admit a match to training
only after exact native replay and a visibility audit. Keep the client bridge
optional so Python training and Stardust-facing policy interfaces remain
independent of EDOPro's client and license.
