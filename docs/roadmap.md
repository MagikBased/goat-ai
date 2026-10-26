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

A Book of Moon / Compulsory native fixture found and fixed lost opponent-hand knowledge when a previously public, now face-down monster returns to hand. A never-revealed Set monster remains unknown in the paired control fixture; the known-card duel serializes and replay-verifies. See [GOAT rules](goat_rules.md).

A paired Trap Dustshoot/Mystical Space Typhoon fixture now changes one
unrevealed opposing hand card and confirms that the Trap controller's
observation and legal responses are identical before Dustshoot activates.
Only its addressed reveal and known-hand memory differ afterward. Both
respond/pass full duels replay-verify; see [GOAT rules](goat_rules.md).

A documented [2020 championship Chaos Turbo Main Deck](../examples/decks/chaos_turbo_riclar_2020.ydk) now exercises a real archetype rather than only synthetic probes. With the experimental adapter and random agents, seeds 1–20 all reached terminal against `control_probe.ydk` within 3,000 decisions. Two seat-swapped, full-deck fixtures also serialize and replay-verify complete trajectories. These are protocol-coverage results; the random plays and current scripts do not establish historical correctness or playing strength.

A [2020 championship Goat Control Main Deck](../examples/decks/goat_control_lolmarcus_2020.ydk), paired with three test-copy Thousand-Eyes Restricts, also completed seeds 1–20 against that Chaos Turbo list within 3,000 decisions. Two seat-swapped matchup fixtures serialize and replay-verify full trajectories. The source omits the Extra Deck, so its contents are a disclosed test choice.

A documented [competitive Warrior Main Deck](../examples/decks/warrior_montague_clash.ydk) adds an aggressive archetype and Reinforcement of the Army to the corpus. It passes the pinned whitelist/deck-size gate. Random-agent Warrior versus Chaos Turbo duels completed all 20 games on seeds 1–10 in both seats within 3,000 decisions; two seat-swapped full-duel trajectories serialize and replay-verify. This extends protocol coverage, not card-by-card ruling validation or a playing-strength claim.

A further 60-duel random-agent sweep on seeds 21–30 covered all three pairings among the sourced Goat Control, Chaos Turbo, and Warrior lists in both seats. All reached terminal under a 3,000-decision cap, with 60,374 decisions total. Goat Control versus Warrior additionally has two complete seat-swapped trajectories that replay-verify. The measured two-worker runtime and limits are in [the evaluation log](evaluation.md). This widens M1 protocol coverage; M2 historical card correctness remains open.

A [GoatFormat guide Flip Control Main Deck](../examples/decks/flip_control_goatformat_guide.ydk) adds a fourth archetype centered on Tsukuyomi, Dekoichi, Magician of Faith, Mask of Darkness, and Time Seal. The guide does not name a tournament pilot or list an Extra Deck, so the fixture records neither. Forty random-agent duels against Chaos Turbo and Goat Control, paired across seats on seeds 31–40, all reached terminal under the 3,000-decision cap. Four full-duel fixtures serialize and replay-verify trajectories. A targeted native M2 fixture now checks two Mask of Darkness / Time Seal recoveries and skipped Draw Phases; interruptions and other timing branches remain open. Measured runtime and exact reproduction are in [the evaluation log](evaluation.md).

A [GoatFormat guide Dimension Fusion Turbo Main Deck](../examples/decks/dimension_fusion_turbo_goatformat_guide.ydk) adds a combo archetype centered on Thunder Dragon, Bazoo, and Dimension Fusion. The guide lists no Extra or Side Deck, and this is not a submitted tournament list. Twenty paired random-agent duels against sourced Chaos Turbo reached terminal under 3,000 decisions; two seat-swapped full-duel trajectories replay-verify. Targeted native fixtures verify Dimension Fusion's 2,000 LP cost, empty-banished-zone activation gate, revival of both Chaos Summon costs, both-player revival after D.D. Warrior Lady's battle banish, persistence through the End Phase, and matched Torrential Tribute and Solemn Judgment response windows. See [the evaluation log](evaluation.md) and [GOAT rules](goat_rules.md).

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
The older full-whitelist seeds-0–9 report cited above no longer reproduces its
12,382-decision count in this worktree: both the pre-change and current probe
scripts now record 12,006 decisions. The difference remains unexplained and
the [README](../README.md) records the current report hash.

An expanded 300-duel, four-worker sweep on seeds 9600–9609 also reached native terminal outcomes in every game. A 60-duel subset reproduced exact ordered outcomes and decision counts in a separate one-worker run. Measured rates, hardware, pins, and reproduction commands are in [the evaluation log](evaluation.md). This broadens M1 protocol evidence while M1 and the M2 card audit remain open.

The current six-tournament-deck corpus, now including Bazoo Return in place of the earlier guide-list slot, has its own complete pairwise protocol sweep: all 15 matchups, both seats, and seeds 9750–9751 reached terminal in **60/60 games** below 3,000 decisions. Ordered results and counts matched between one and four native workers; source-code and Lua-script-tree fingerprints now accompany the report. See [the evaluation log](evaluation.md). This tests the published deck corpus used to prioritize card rulings, not competitive agent strength.

A seeded Thunder Dragon / Morphing Jar fixture now checks the player-visible hand-memory boundary: a revealed search creates known opponent cards, a later hidden Set reduces the guaranteed count conservatively, and Jar's hand replacement clears current knowledge while retaining the historical reveal event. The full duel replay-verifies; see [GOAT rules](goat_rules.md).

## M2 — Historical correctness gate

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

**Status: in progress.** The source-backed Cannon Soldier / Book of Moon fixture checks historical Ignition priority after a summon, the GOAT Nobleman fixtures check a representative banish ruling and Flip-monster Deck verification, two Field Spell fixtures check replacement and chained destruction, a Dekoichi fixture checks a basic Flip Effect draw and Book of Moon's Damage Step restriction, a Peten fixture compares missed timing after Cannon Soldier's cost with a successful battle trigger, a Sangan/Thestalos fixture checks mandatory trigger ordering and reverse chain resolution, and a Solemn Judgment fixture checks Normal Summon negation. Pre-errata Dark Magician of Chaos fixtures check Spell recovery after its two-Tribute Normal Summon and its face-up versus face-down leave-field destination when tributed by Cannon Soldier. A Goat Control fixture follows Scapegoat into Metamorphosis for Thousand-Eyes Restrict, equips an opposing monster, then uses Tsukuyomi to set Restrict and checks the hidden view. A paired Book of Moon reset fixture equips two opposing Sheep Tokens in one turn by setting and Flip Summoning a Restrict that was Summoned earlier; branches with a prior manual position change, attack declaration, or Summon by the turn player correctly offer no same-turn Flip Summon. All four full duels replay-verify. Four Snatch Steal fixtures take an already equipped Restrict, check Equip Card zones across control change, Book of Moon after Snatch, Book chained before Snatch resolves, and Heavy Storm returning Restrict. All four full duels replay-verify against the official 2005 rulebook zone rule and historical card rulings. A separate Tsukuyomi fixture tests mandatory self-targeting as the only face-up monster and confirms the face-down Spirit stays on the field through End Phase. Scapegoat fixtures check four token placements, the four-vacant-zone requirement, same-turn Summon restrictions, a legal monster Set, token tribute for Cannon Soldier but not a Tribute Summon, and restoration of Summon permission after Solemn negates its activation. Trap Dustshoot fixtures check the four-card hand threshold, opponent-hand reveal scope, monster selection without private hand slots, and a terminal replay-verified duel. Common-staple fixtures check Graceful Charity's draw and discard choices, Delinquent Duo's random and chosen discards without exposing opponent hand cards, Snatch Steal's control and Standby Phase recovery followed by Heavy Storm returning the monster, and Book of Moon setting the stolen monster while control remains with the stealing player. Paired GOAT Bottomless Trap Hole fixtures check a Normal Summon banish and the historical Book of Moon escape into a known face-down field slot. A three-branch Breaker/Bottomless fixture checks the response to Breaker's counter-placement trigger, declining it, and Book of Moon chained behind Bottomless; all full duels replay-verify. Paired Sakuretsu Armor fixtures verify attack-triggered destruction versus a chained Book of Moon that saves the face-down attacker, following the historical ruling. Paired Royal Decree/Mirror Force fixtures show Decree chained to Mirror negating its effect, saving the attacker, and allowing 1900 direct damage. A Mirror Force and Book of Moon attack-response fixture checks that the chained face-down attacker survives while another Attack Position monster is destroyed. A Torrential Tribute and Book of Moon summon-response fixture checks that the face-down monster is still destroyed with the other monster. Pre-errata Ring of Destruction fixtures check own-monster targeting and equal damage, plus Breaker removing its Spell Counter as a cost before Ring deals 1600 damage and the pending Breaker effect destroys a set card. Chaos Sorcerer fixtures check the LIGHT/DARK Graveyard summon cost, opponent-monster banish, and same-turn attack restriction, a negative field-only cost case, and Book of Moon making the target invalid while still spending Sorcerer's effect and attack opportunity. A Snatch Steal/Scapegoat fixture now checks destruction of a stolen monster when Mystical Space Typhoon removes Snatch while the original controller has five occupied Monster Zones; the full duel replay-verifies. A GOAT Black Luster Soldier fixture checks its LIGHT/DARK Graveyard summon cost, optional second-attack trigger after battle destruction, direct second attack, two-attack limit, and alternative monster-banish effect with its same-turn attack restriction, plus loss of that effect after a declared attack. A pre-errata Sinister Serpent fixture checks optional Standby Phase return after a discard, including its public Graveyard and private hand boundaries. A Tribe-Infecting Virus fixture discards Serpent as an activation cost, limits Type announcements to face-up monsters, destroys the declared opponent Type, and returns Serpent on the next Standby Phase. A Book of Moon response branch verifies that Tribe does not destroy a monster turned face-down after its Type was declared, and checks the resulting hidden field view. Paired Premature Burial fixtures verify its 800 LP revival cost and the different outcomes when Book of Moon breaks the Equip link by turning the monster face-down versus Mystical Space Typhoon destroying the Equip Spell, and a chained Typhoon preventing the initial revival after the 800 LP cost is paid. Call of the Haunted fixtures check that Book of Moon severs the revived monster while Call stays face-up and the face-down monster remains, and that the two Call/Mystical Space Typhoon chain orders differ in whether a Summon is attempted before both cards and the monster end in the Graveyard. Airknight Parshath fixtures check piercing damage and its mandatory draw against a set monster, Waboku preventing both damage and the draw, and Airknight drawing before an attacked Dekoichi’s Flip Effect draw. Paired Jinzo fixtures check a set Mirror Force is unavailable while Jinzo is face-up, then becomes a legal and resolving attack response after Book of Moon turns Jinzo face-down. Paired Magician of Faith fixtures check Spell recovery after a Flip Summon, the opponent card reveal, and continued Flip Effect resolution when Book of Moon turns Magician of Faith face-down. Creature Swap fixtures check its both-sides eligibility gate, choices made during resolution, variable-length own-monster options, position-change restriction, persistent exchanged control, and retained knowledge when one or both exchanged monsters are set; both set-monster duels replay-verify. Pre-errata Brain Control fixtures distinguish Book of Moon chained before control from Book used afterward, check End Phase return of a face-down monster and known-card memory across control change, replay-verify a complete duel, and confirm that its historical target condition can take Thousand-Eyes Restrict after a Scapegoat/Metamorphosis Summon. Enemy Controller fixtures check both effect choices, Tribute as an activation cost for temporary control, and End Phase control return. Exiled Force fixtures check its self-Tribute activation cost, hidden opponent monster targeting by field slot, no effect when it is the only monster, identical target-decision views when the hidden monster changes between a Flip monster and a Normal Monster, and a replay-verified Torrential Tribute response to its summon-priority effect. Dust Tornado fixtures check destruction of a hidden set Trap, optional Set from hand, opponent field secrecy, same-turn versus following-turn Book of Moon activation timing, and no Set after chained Mystical Space Typhoon destroys Dust Tornado's target. GOAT Spirit Reaper fixtures check battle survival, target-driven self-destruction versus Book of Moon concealment, the Snatch Steal/Mystical Space Typhoon chain distinction that requires the dedicated GOAT script, and direct-attack discard only when Waboku does not prevent damage. Morphing Jar fixtures check both six-card hand discards and five-card draws, with a differential run proving that changing only the opponent's newly drawn private card does not change the acting player's observation or legal actions. D.D. Warrior Lady versus Morphing Jar fixtures check mandatory-then-optional Damage Step chain ordering, both choices for Warrior Lady, public banish destinations, and Jar's hand reset even when the monsters leave the field first. An Asura Priest/Scapegoat fixture checks four separate Token attacks, no direct attack afterward, Token cleanup, and Spirit return to hand at End Phase. Kycoo fixtures check the face-up Chaos Graveyard banish lock, its release after Book of Moon sets Kycoo, the optional one-or-two-monster banish after direct battle damage, the exclusion of a monster Kycoo just destroyed from that Damage Step choice, and Nobleman of Crossout remaining legal against a set field monster. Old Vindictive Magician fixtures check Flip Effect destruction of a face-up or hidden opposing monster, including target secrecy. GOAT Apprentice Magician fixtures check its optional battle recruitment of a face-down Level 2 Spellcaster, its opponent-only card reveal tied to the recruited field slot, and a decline branch; a linked Old Vindictive recruit and next-turn Flip Effect line reaches terminal and replay-verifies a schema-v14 trajectory. GOAT Gravekeeper's Spy fixtures recruit Guard from the Deck without exposing native Deck order, recruit another Spy under pre-errata Necrovalley despite the resulting 1700 ATK, and test opponent-only verification after an empty search using a pinned runtime utility correction. Mystic Tomato fixtures cover an optional Damage Step recruiter into Sangan after battle destruction, a decline branch, hidden attack targeting, and the recruited monster's same-turn attack option. Cyber Jar and Ground Collapse fixtures cover public five-card reveal order and a two-zone lock respectively. The remaining timing and card-specific cases below are untested.

A paired native Ring of Destruction and Book of Moon fixture now checks target validity at resolution, the no-damage outcome when Book sets the target, and the opponent's hidden field view. Its historical interpretation is identified as an inference in [GOAT rules](goat_rules.md).

A paired Creature Swap / Scapegoat fixture now tests a common Goat Control Token exchange: Scapegoat chained to Swap adds four legal Token choices at resolution, while passing leaves only the original monster available. A Ring of Destruction response fixture removes the defender's only monster before Swap resolves and confirms the exchange fails. All three full duels replay-verify; other interruption types remain open. See [GOAT rules](goat_rules.md).

A pre-errata Sinister Serpent fixture now checks two returns within one Standby Phase, separated by Raigeki Break discarding Serpent as its cost. The hidden Trap target and opponent's known-hand update are checked in a full replay-verified duel. See [GOAT rules](goat_rules.md).

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

Four Morphing Jar deck-out fixtures now verify the historical five-card draw boundary for either player: with four Deck cards the effect ends the duel, while with five it resolves and the next required draw ends the duel. Two additional native fixtures check equal Deck counts: four each gives a draw, while five each resolves and the next required draw determines the loser. All six terminal trajectories replay-verify. A contemporaneous 2005 TCG source for the simultaneous failed-draw outcome remains to be located, so that historical interpretation is provisional. See [GOAT rules](goat_rules.md).

**Work:** Create source-backed regression fixtures for first-turn draw, summon response and Ignition priority, chain construction and resolution, trigger ordering and missed timing, Damage Step restrictions, flip effects, summon negation, historical field spells, the April 2005 list, and representative pre-errata card rulings. Track unresolved rulings in `docs/goat_rules.md` with the chosen interpretation and evidence.

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

## M3 — Evaluation and data

**Status: in progress.** Seeded tournament runners swap seats for each deck matchup, record individual outcomes, report seat and matchup splits, and give paired score and Wilson intervals. A spawned-process runner reproduces the sequential results on a native fixture and has a measured two-worker throughput example. A restricted-fixture baseline report is in [the evaluation log](evaluation.md). Schema v18 trajectories add a final player-visible terminal observation to the v17 decision records, which record face-up monster ATK, DEF, and counters alongside bounded public events, field-slot known-card memory, conservative opponent-hand knowledge from public returns and addressed hand reveals, a public Scapegoat restriction, public Deck-top reveals, active disabled zones, recipient-scoped private reveals, and the player's initial Main Deck composition; they can be replayed against the native engine with exact observation, legal-action, result, deck-content, rules-profile, and loaded-asset comparisons. An offline browser viewer renders these player-visible decisions without card art or intermediate animations. Earlier fingerprinted recordings without affected Deck-search choices, addressed face-down field reveals, or face-down control returns, or transferred set cards remain verifiable; affected recordings need re-recording for exact comparison. Broader deck families, held-out opponents, authorized human replay reconstruction, training/evaluation separation, and parallel-worker memory measurement remain outstanding.

A first sourced-deck baseline now evaluates HeuristicAgent versus RandomAgent on both Goat Control/Chaos Turbo deck assignments with seat swaps. The 32-game seeds-7000–7007 report and its limitations are in [the evaluation log](evaluation.md). This does not satisfy the held-out competitive-policy exit gate.

The offline viewer can now collect local retrospective labels for legal
decisions in a recorded duel. Annotation files are tied to the trajectory
byte hash and require explicit self-recorded authorization; cloning verifies
the full replay and visible action safety before using only labeled choices.
A one-label Breaker smoke run passed. These are hindsight annotations, not
reconstructed DuelingBook/EDOPro games or expert demonstrations; see
[the evaluation log](evaluation.md).

**Work:** Build seeded agent tournaments with deck and matchup splits, seat swaps, confidence intervals, and held-out evaluation opponents. Measure duel throughput, decisions per second, runtime memory, and initialization overhead on named hardware. Validate self-play trajectory round trips. Investigate `.yrp` and `.yrpX` reconstruction; ingest human games only when permission, legal-action recovery, and player-visible knowledge can be established.

**Exit:** A reproducible benchmark report and tournament report exist for the tested core/assets/decks. Replay support is claimed only for formats that have parser and reconstruction tests.

The sourced-deck single-process benchmark records reset overhead and peak process RSS alongside throughput on named hardware. A separate spawned-worker benchmark now measures one and two workers on the sourced Goat Control/Chaos Turbo decks, including per-worker high-water RSS and native reset time; the seat-swapped game outcomes reproduce across worker counts. [The benchmark log](benchmarks.md) gives the measurements and their limits. Instantaneous total memory use, broader deck families, and a scaling curve remain unmeasured.

A balanced six-deck evaluation now tests both deck assignments and both seats for HeuristicAgent versus RandomAgent and an identical random-versus-random control. The paired score-difference helper reports a measured heuristic advantage with a confidence interval on this small schedule; [the evaluation log](evaluation.md) gives the deck splits and limits. This supplies a stronger baseline for M4 comparisons without satisfying M4's held-out competitive-policy gate.

An optional Flip-type-aware heuristic ablation increased Flip Control wins from 3/20 to 6/20 on that schedule, but its aggregate score was effectively unchanged and Chaos Control fell from 14/20 to 7/20. Keep the generic heuristic as the baseline while auditing the decision causes on high-play cards.

A visible-stat CombatHeuristicAgent baseline now uses only player-visible field stats and legal actions. On a fresh, both-deck-assignments, three-pair native schedule it scored 54–42 against the original heuristic, with a paired 95% score interval of 52.1–61.5%; see [evaluation](evaluation.md). This is a limited baseline result, not a learned-policy gain. The evaluator now offers both deck assignments explicitly and clusters mirrored assignments together for score intervals, because fixed deck assignments produced misleadingly different head-to-head results. Further deck families and independent seeds remain necessary before promoting this baseline to a demonstration teacher.

A newer balanced six-tournament-deck run put CombatHeuristicAgent at 269–205 with six draws against HeuristicAgent on eight independent seeds, both deck assignments, and both seats. Its paired score interval is above 50%, but the assigned-deck scores range from 26.2% to 81.2%. The pilot reproduced exactly across one and four workers; [the evaluation log](evaluation.md) records hashes, timings, and the per-deck split. Use this as a provisional baseline and demonstration teacher for held-out policy tests, while preserving per-deck evaluation and the historical-rules caveat.

## M4 — Learn a competitive policy

**Status: in progress.** A PyTorch policy scores variable-length legal action sets from visible observations, and behavioral cloning fits replay-verified fingerprinted trajectories into versioned checkpoints. Feature version 2 distinguishes multi-target choices by visible target location even when IDs are hidden; version 3 uses field-slot memory of publicly known facedown opponent cards; version 4 encodes disabled zones and multi-zone choices; version 5 separately pools the player's initial Main Deck composition; version 6 distinguishes Attribute, number, and card-name announcements; version 7 distinguishes ordered card choices; version 8 encodes visible current monster stats and counter counts; version 9 separately pools publicly known opponent hand cards from schema v17; version 10 encodes public chain links in resolution-relevant order; version 11 is an equal-capacity unordered-chain ablation; version 12 binds direct and multi-card field choices to the visible card and current stats at each selected slot, with no additional parameters. Old checkpoints retain their versioned encoders. Demonstrator-seat metadata filters heuristic or self-recorded CLI-human decisions after full-duel verification. The checkpoint evaluator runs paired, seat-swapped tournaments on seeds excluded from training and supports direct checkpoint opponents. A heuristic-imitation baseline won 15/16 versus RandomAgent and 9/16 versus HeuristicAgent on held-out vanilla-fixture seeds; a version-2 retrain matched these results. Direct version-2 versus version-1 evaluation on experimental control/Chaos decks was 17/32, an inconclusive result with unaudited rules and visibility. Initial terminal-reward self-play from random imitation and two runs from the heuristic baseline did not demonstrate a greedy-policy strength gain. Version 5 was trained on one random-play Ground Collapse fixture and evaluated on held-out seeds: 11/16 versus RandomAgent and 7/16 head to head versus version 4; version 4 scored 14/16 versus RandomAgent on the same schedule. This does not show a gain from the Deck feature. Version 6 has no competitive result yet. A matched schema-v17 sourced-deck comparison gave feature version 9 an 18/32 head-to-head result against feature version 8, with equal exact teacher agreement on the 229 held-out known-hand decisions that had multiple options. The interval includes 50%, so no strength gain is established. On separately held-out Chaos Return and Warrior deck files, the same models split 16–16, with a strong 4/16 versus 12/16 deck-assignment split; an exact training-deck file-hash gate supports those saved checkpoints. New checkpoints also record order-independent Main Deck composition hashes and can use a stricter opt-in unseen-Main-Deck gate. See [the evaluation log](evaluation.md). No authorized tournament-human training set, robust held-out competitive result on audited deck families, or strength claim exists yet.

A feature-version-10 checkpoint trained on the same 4,630 sourced teacher decisions as version 9 won 20–11 with one draw in 32 paired duels on separate Chaos Return and Warrior deck files. Its held-out chain-decision teacher agreement was 116/135 versus version 9's 114/135, while its overall agreement was two choices lower. Feature version 11 now supplies an equal-capacity unordered-chain GRU control. Ordered version 10 scored 16–15 with one draw against it on a fresh 32-duel schedule, and matched one more of 135 held-out multi-option chain decisions. This does not establish a chain-order strength gain; repeat the comparison across deck families and training seeds. See [the evaluation log](evaluation.md) for protocols and intervals. M4 remains open.

On another sourced Chaos Control/Warrior schedule, ordered version 10 split 16–16 against the unordered control and won 17–15 versus version 9. A same-seed HeuristicAgent control favored Warrior 24–8, revealing a large deck effect. The [evaluation log](evaluation.md) has the deck and seat splits. M4 still needs improved held-out play across decks, with audited full-deck rules.

A feature-version-8 checkpoint trained on 6,999 replay-verified heuristic decisions from the sourced Goat Control/Chaos Turbo decks improved held-out teacher-action agreement on decisions with alternatives, but split 16–16 against the vanilla-trained version-2 checkpoint and won only 18/32 versus RandomAgent on separate seeds. The [evaluation log](evaluation.md) records the direct comparison and deck asymmetry. M4 remains open: imitation accuracy has not produced a measured strength gain.

An additional held-out Warrior-versus-Chaos check yielded 14/16 for that checkpoint against HeuristicAgent, but Warrior also won 13/16 when both decks used HeuristicAgent. The deck effect prevents a strength or generalization claim from this sample. Continue the competitive-card ruling audit before expanding training claims; details and reproduction commands are in the [evaluation log](evaluation.md).

The sourced-deck self-play schedule now covers both learner seats per matchup. A 16-game REINFORCE-style update from the sourced imitation checkpoint replay-verified four deck/seat trajectories but won only 17/32 directly against its parent on fresh paired seeds, with no changed choices on the separate held-out action audit. M4 remains open; see [the evaluation log](evaluation.md).

A fresh feature-version-12 behavioral clone was trained on 3,812 replay-verified CombatHeuristicAgent decisions from eight sourced-deck duels, with explicit teacher provenance and exact tensor reproduction on a repeat CPU run. Held-out multi-option action agreement improved by eight choices over the older version-12 checkpoint, but the new policy split 16–16 against its teacher and scored 16–13 with three draws against that checkpoint on unseen Main Decks, both deck assignments, and fresh seeds. Both paired score intervals include 50%; no learned playing-strength gain is established. See [evaluation](evaluation.md).

The combat-clone checkpoint also underwent two snapshot-pool self-play runs. Sixteen default-temperature and 32 temperature-2 training duels all produced replay-verifiable full trajectories; the learner used each of the two training decks equally. On unseen-deck, both-assignment head-to-head tests against its parent, the children scored 16–16 and 17–15 respectively, with intervals including 50%. A held-out action audit found zero and one changed choices out of 745 multi-option decisions. Exploration temperature is now applied consistently during sampling and policy updates, but these experiments do not establish a self-play strength gain; see [evaluation](evaluation.md).

**Work:** Implement a PyTorch policy that scores variable-length legal actions from visible observations. Establish random and heuristic baselines first. Train behavioral cloning on verified demonstrations, then self-play with a historical checkpoint pool and held-out deck families. Compare PPO or other algorithms on win rate and stability rather than selecting one in advance.

**Exit:** A versioned model beats the baseline agents over held-out seeds and decks with confidence intervals, and its decisions use no hidden engine state. Record training compute, data provenance, and evaluation protocol.

A larger 9,117-decision combat-teacher clone trained from 16 freshly replay-verified Goat Control/Chaos Turbo duels improves held-out staple-decision agreement and wins a 64-game direct match against its smaller parent 37–25 with two draws on unseen Chaos Control, Chaos Return, and Warrior Main Decks. Its matched score improvement over the parent against CombatHeuristicAgent is positive on eight held-out seeds, but its absolute combat-teacher score is 30–32 with two draws and its original-HeuristicAgent score is 32–31 with one draw. Both absolute heuristic intervals include 50%; M4 remains open. See [the evaluation log](evaluation.md) for the full schedule, intervals, and ignored checkpoint provenance.

A 64-game self-play continuation from that larger clone produced 64 replay-verified trajectories (50,620 decisions), but scored only 32–31 with one draw directly against its parent on held-out deck families and changed just one of 1,454 multi-option decisions in the separate teacher audit. This does not satisfy M4's strength-gain gate. An opt-in feature-v14 policy can now encode public chain target slots from schema-v21 trajectories; a matched held-out comparison found no demonstrated target-specific or strength gain, so the default remains v10. The cloning trainer now supports opt-in optimizer minibatches; a matched held-out comparison measured higher CPU throughput but no established strength gain, so batch size 1 remains the default. The next priority is source-backed interaction coverage for the high-play GOAT staples listed below, followed by stronger held-out policy evaluation; see [the evaluation log](evaluation.md).

The cloning trainer also supports opt-in extra exposure to decisions involving selected high-play cards. A matched experiment on ten shared GOAT staples improved held-out multi-option teacher agreement by 12/947 decisions but split a 32-game direct match 16–16 against the unweighted clone. Keep ordinary sampling as the default and use competitive results, rather than teacher agreement alone, to judge this approach; see [the evaluation log](evaluation.md).

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

## M5 — Search and other formats

Evaluate policy-guided search and belief sampling only after M2 and M4. Search must sample hidden information from a player-consistent belief and must never inspect the real hidden state when choosing actions. Add Edison as a separately validated rules profile, not a changed banlist.

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
3. Expand Warrior's Reinforcement of the Army audit beyond its tested ordinary, empty, and Exiled Force follow-through searches, Mystic Swordsman LV2 beyond its tested attack on set Dekoichi, Blade Knight beyond its tested hand-size bonus and Dekoichi battle, and Don Zaloog beyond its tested direct-attack discard/mill choices. These add high-use decisions absent from the two control/Chaos lists.
4. Cover other cards when they block a representative full duel, expose a general engine or observation defect, or appear in additional sourced competitive decks. Defer isolated low-play card edge cases until the staple paths work reliably.

Use the [SJC Indianapolis 2005 Top 8 card ranking](card_priorities.md) to select the next fixture: common contemporary cards such as Tsukuyomi, Scapegoat, Magician of Faith, Metamorphosis, and Sinister Serpent take precedence over isolated low-use cases. Five legal 40- or 42-card published lists are executable deck fixtures; printed 38- and 39-card lists remain ranking evidence only unless an independently sourced correction is found. For each fixture, record the historical source, native script and rules profile, expected outcome, and any unresolved discrepancy in [GOAT rules](goat_rules.md). Keep implementation changes small enough to demonstrate with a command, test, and documented limitation. Resume strength experiments after the audited deck corpus is broad enough to support meaningful evaluation.
