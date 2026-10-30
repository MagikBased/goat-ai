# Architecture and engine contract

`GoatEnvironment` validates action membership and delegates every rules transition to a `RulesEngine`. `Decision` returns one acting player's `Observation` and its variable-length legal `Action` tuple. The current default engine raises `SimulatorUnavailable`; no custom Yu-Gi-Oh! rules are simulated in Python. The restricted `RestrictedOcgcoreEngine` connects a [native core](native_setup.md) to this environment for normal-monster fixture decks and three tested spells. General response decoding and complete observation coverage are still unfinished, so the default remains fail-closed.

`RulesProfile` now selects historical Side Deck sizing (0 or 15 cards) by
default, with an explicit community option for 0–15 cards. Main Decks require
at least 40 cards and have no project-imposed maximum. The experimental native
adapter has a 61-card startup test; broader large-deck behavior is unmeasured.

For `MSG_SELECT_CARD`, requests with at most 4,096 complete combinations
retain one action per complete selection. Larger requests expose one
`select_card` action per remaining visible candidate. Each action carries
the player's already selected cards in `parameters.cards`; a legal
`finish_selection` appears once the minimum is met, and the final pick is
submitted automatically at the maximum. The adapter sends one validated,
canonical response to ocgcore only when the selection is complete. The
intermediate steps are recorded as ordinary trajectory decisions and replay
deterministically. The legal-action sequence carries selection progress;
schema v23 separately records the public turn player; v24 adds each face-up monster's current public Type.

For `MSG_SORT_CARD` and `MSG_SORT_CHAIN`, prompts with at most 2,048
permutations retain complete `sort_cards` actions. Larger prompts expose one
`sort_cards` action per remaining card and carry the already chosen order in
`parameters.cards`. The adapter sends one validated permutation to ocgcore
only after the last pick. A seven-card protocol message now exposes seven
initial actions instead of 5,040 permutations. Forcing this path on a real
three-card Fruits of Kozaky's Studies prompt produces a complete,
replay-verified duel with a passing visibility audit. No seven-card
historical duel has yet been observed.

For `MSG_SELECT_COUNTER`, at most 4,096 complete allocations retain one action
per allocation. Larger prompts expose the feasible amounts for the next
visible card in native order. Each staged `select_counters` action carries
the selected prefix, including zero amounts, plus the public counter type,
total, next-card index, and remaining cost. The native state does not advance
until the final amount; the adapter then submits one validated ordered
16-bit response. The visibility audit checks every prefix against public
face-up counters, and replay reconstruction expands a saved full response
into the same staged decisions. Policy feature v28 encodes the amount at each
selected card. A stage can still have up to 32,768 amount options when a
card carries that many counters; its measured synthetic CPU and memory cost
is recorded in [evaluation](evaluation.md#synthetic-maximum-counter-menu-benchmark-27-october-2026).

The observation schema has explicit visible zones, public counts, own hand and Fusion Extra Deck identities, the player's sorted initial Main Deck composition, and structured chain links with public field-target slots. Opponent Extra Deck and unrevealed Main Deck identities are withheld. Field monsters record visible attack or defense position and, while face-up, current ATK, DEF, Type, and counters. A face-up Spell/Trap temporarily occupying a Monster Zone through Magical Hats has no Type (`race=None`); schema v24+ serializes that explicit null. Face-down cards have no current Type or dynamic stats in either player view. The native adapter records bounded public turn, phase, attack, Damage Step, and chain events. It also records public `MSG_CONFIRM_DECKTOP` reveals, the current public `MSG_FIELD_DISABLED` zone mask, and opponent field cards seen face-up immediately before a public face-down position change; move, set, swap, and set-card shuffle events invalidate the latter memory. `MSG_CONFIRM_CARDS` messages are stored only for their addressed recipient, as sorted card multisets without native sequence numbers; the viewer cannot see the other recipient's message at that decision. It tracks opponent hand identities when a public Graveyard or face-up field card moves to hand, or when a card already in hand is explicitly shown to the opposing player by an addressed native reveal. The memory is an unordered multiset of guaranteed copies; Deck-only verification does not imply a card entered hand. Private draws add no identity. A public hand exit removes at most one known copy and keeps other known cards. An ambiguous hidden exit subtracts one possible copy of each known identity, retaining only copies guaranteed under every choice of the hidden card. It has no unrevealed opponent hand identities or deck order. Other reveal messages and richer history need an audit. Schema shape alone cannot prove the native adapter redacts data. The native adapter must use the engine's player-scoped queries, hide facedown cards where appropriate, and test identical visible states with different hidden cards. A native differential now replaces one unrevealed opponent card with each of ten common Spell/Trap identities; the player's opening view and next Main Phase view, including all sixteen legal actions after the Set, remain equal across replacements. This is a bounded information-flow check, not proof for all effects or later turns. Action IDs are local to a decision and must map to the exact native response payload; effects with targets or multiple choices may take several decisions. Flip Summons are distinguished from face-up position changes in the public action API. Small field-zone prompts retain one action per complete zone set. Larger prompts expose one public zone choice at a time, preserving the selected order and submitting one exact native response after the final pick. A synthetic five-zone prompt and a forced staged Ground Collapse duel test this path; other combinatorial request types still have explicit bounds.

The trajectory visibility auditor rejects physical Deck and Extra Deck slot
numbers in single-card, multi-card, and sorting choices. A native Fruits of
Kozaky's Studies sorting prompt passes this check. It guards the action
boundary against a shuffled-slot leak; other hidden-information paths still
need their own audits.

## Next adapter implementation

1. Pin ocgcore, card database, and script revisions with checksums. Build the native core outside this repository or as a separately licensed optional package.
2. Start duels with `DUEL_MODE_GOAT`, 8000 LP, five starting cards, one draw per turn, and seeded PRNG. Parse `.ydk` and verify the April 2005 banlist and card pool before duel creation.
3. Parse every core request message into legal actions, including card/effect selection, chained responses, targets, positions, tribute choices, attacks, and phase transitions. Map each selected action back to exact response bytes; reject overflow or unsupported messages explicitly.
4. Construct player-scoped observations from native queries. Test hidden opponent hands, deck order, facedown identities, and privately revealed information. Capture public history and known-card memory only through observed events.
5. Run a complete duel with two random agents; add historical ruling fixtures. Then add multiworker runs and measured benchmarks.

Do not use `ygoenv`'s current EDOPro binary as a GOAT engine: its source currently selects MR5. The direct `ctypes` probe reaches real native decisions without a fixed option-list size, so it is the current M1 adapter direction. Its response protocol and visibility boundary are only partially implemented. The interface avoids coupling downstream agent and replay code to this choice.

Trajectory JSON schema v28 stores the visible observation, full legal action list, chosen action, acting player and phase (inside the observation), deck identifiers, ruleset, source, optional skill metadata, and result. It retains monster orientation and structured chain links from v2, the rules profile, deck hashes, and loaded native-asset hashes from v3, and the latest 64 observed public turn, phase, attack, Damage Step, and chain events from v4. Version 5 adds opponent field-card identities known through a public face-up-to-facedown position change; version 6 associates those identities with controller, zone, and slot. Version 7 populates a narrow public Scapegoat summon restriction from native player-hint add/remove events. Version 8 adds public Deck-top reveals and distinguishes Flip Summons from face-up position changes. Version 9 adds active disabled field zones from a public native message. Version 10 adds recipient-scoped private card reveals. Version 11 adds the player's initial Main Deck as a sorted multiset. Version 12 adds visible current monster ATK, DEF, and counters. Version 13 removes native Deck and Extra Deck slot numbers from action parameters and canonicalizes ordinary Deck-search choice order by visible values. Version 14 retains recipient-addressed reveals of face-down opponent field cards as known identities tied to field slots; the current field view remains face-down. Version 15 carries prior known identity across face-down field-to-field control changes. Version 16 retains a former controller’s knowledge when its own face-down card changes control, including native swap messages; raw IDs are used only when both the former and new controllers can legally know the card. Version 17 adds an unordered, conservative multiset of opponent hand cards observed returning from the public Graveyard or face-up field; a private draw adds no identity, and an ambiguous hand exit retains only copies guaranteed under every hidden-card choice. Version 18 adds a final player-visible observation after the native terminal result, separate from all decision records. Version 19 adds the public target monster field slot for a face-up Equip Card. Version 20 also records the public target slot of a face-down Equip Card, while continuing to hide that card’s identity from the opponent. Version 21 records public field-target slots on active chain links without exposing the targeted card identity. Version 22 records the acting player’s own attacker field slot only during an attack-target choice; it does not expose an opponent card identity. Version 23 records the current turn player from ocgcore's public turn message, separate from the player acting at a response window. Version 24 records the current Type of face-up monsters from a native public query; face-down Type remains hidden. Version 25 records the original owner of face-up field monsters and a public summon announcement awaiting a response. Owner remains hidden for face-down monsters, and the pending summon appears only when its announced slot matches the visible field. Version 26 records the number of public turn boundaries since each face-up field card became face-up, based only on native public messages; a face-up control change preserves the count, while returning a card to the hand or setting it resets it. Version 27 retains the last 32 announced attacks as public attacker and target field slots, or a direct attack, without adding card identities. Version 28 distinguishes multiple legal effects of the same visible card with a public effect-option index; the verifier removes this field only when checking earlier recordings. The reader accepts v1–v28 trajectories; the verifier ignores fields added later when checking older recordings and maps older position actions at Flip Summon decisions. Existing v17 recordings with an addressed opponent-hand reveal from a search or a hidden hand exit after duplicate-card knowledge may need re-recording for exact verification after observation corrections. Existing v18 recordings where a previously known face-down field card returns to its owner’s hand may also need re-recording: the corrected adapter retains that identity in the known opponent-hand multiset. That v18 correction did not change the schema structure. Pre-v13 recordings with Deck-search choices, pre-v14 recordings with addressed face-down field reveals, and pre-v15 recordings with face-down control returns, pre-v16 recordings with transferred set cards, and pre-v17 recordings with public hand returns may require re-recording for exact action and observation comparison; other earlier fingerprinted recordings remain verifiable. No native full-state snapshot is stored. The optional [PyTorch policy](ml.md) maps player-visible decisions to variable-length action logits independently of the simulator. Its default feature version 10 uses the ordered public chain alongside the version-9 opponent-hand multiset; experimental version 12 also binds selected field slots to visible card properties. Neither change has established a playing-strength benefit. The behavioral cloning command verifies trajectories before fitting; other training algorithms can use the same decision boundary.

The trajectory writer rejects a schema version that would discard populated
public observation fields or effect-option choices on read. Native recordings
use v28 and include a terminal observation; older hand-built v17 recordings
remain readable for compatibility. Callers creating current records directly
must set v28 and supply the terminal observation.

A native paired attack test changes only the identity of a Set opponent
defender while keeping the attacking player's visible state and seed fixed.
The attacker receives identical observations and legal actions before the
target selection and after the public attack announcement. Both complete
trajectories replay-verify and pass the visibility audit. This checks the v27
attack-slot boundary; it does not validate every hidden-card interaction.

The opening information-flow audit can be reproduced with the pinned native
assets:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/audit_hidden_opening_pool.py \
  --output .cache/goat-ai/hidden_opening_pool_audit_52.json
```

At seed 52 it replaces one card in the opponent's Main Deck with each of the
1,430 whitelist-eligible non-Fusion IDs present in the pinned database. The
chosen card is confirmed in the opponent's opening hand. Every resulting
player-zero observation and legal-action tuple matched; no startup errors
occurred. The full run took 57.68 seconds on this host. The script reports
asset hashes and exits nonzero on any difference or failed candidate. It
checks only the first decision: later effects, private reveals, and hidden
field states still need separate differential tests.

A second native audit covers the next own Main Phase after the opponent Sets
one Spell/Trap from the same pinned pool:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/audit_hidden_set_pool.py \
  --output .cache/goat-ai/hidden_set_pool_audit_52.json
```

At seed 52, 551 of 557 eligible Spell/Trap IDs could be Set. For all 551,
the card was verified privately in its Set field slot, while the acting
player saw no identity. Complete observations and legal-action lists matched
within the two publicly distinct placement groups: 532 ordinary backrow and
19 Field Spell slots. The other six IDs are placement-only Spirit Messages
and Second/Third Sarcophagus cards; the native engine offered no manual Set
action. The full run recorded zero mismatches and zero errors in 25.55 seconds
on this host. This checks one passive route to the following Main Phase; it
does not validate chain responses, later reveals, or all possible field states.

The same script can continue through activating Mystical Space Typhoon from a
generated first-player Deck and compare the **target-selection** decision:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/audit_hidden_set_pool.py \
  --target-hidden --output .cache/goat-ai/hidden_mst_target_full_52.json
```

At seed 52, all 551 Settable Spell/Trap IDs retained a hidden target ID and
identical player-zero observation and complete legal-action list within their
public placement group (532 ordinary slots, 19 Field Spell slots). The same
six placement-only cards had no manual Set action. The full run found zero
mismatches and zero errors in 26.09 seconds on this host. A focused native
regression compares ten common GOAT backrow cards at that prompt. This checks
one target window before MST resolves; it does not establish that every chain
response or subsequent public reveal is handled correctly.

The same command accepts `--zone monster` to audit face-down monsters:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/audit_hidden_set_pool.py \
  --zone monster --output .cache/goat-ai/hidden_set_monster_audit_52.json
```

At seed 52, the native engine offered a Set action for 644 of 873 eligible
Main Deck monster IDs in the empty-field fixture. All 644 produced identical
player-zero observations and legal actions at the next Main Phase, with zero
runtime errors or differences; the measured run took 39.12 seconds on this
host. The other 229 lacked a Set action **in this setup**. Many monsters need
Tributes or have Summon restrictions, so this number is not a claim that they
can never be Set or are illegal in a deck. The audit checks one field slot
and passive turn path; a separate Nobleman fixture checks a later target
prompt for six common hidden monster identities.

The full-pool audit can also continue to Nobleman of Crossout's target prompt:

```bash
PYTHONPATH=src:. .venv/bin/python scripts/audit_hidden_set_pool.py \
  --zone monster --target-hidden \
  --output .cache/goat-ai/hidden_nobleman_target_full_52.json
```

At seed 52, the same 644 Settable IDs all yielded identical player-zero
observations and full legal-action lists at that prompt. Their target action
named only the opponent's public Monster Zone slot. The other 229 still had no
Set action in the empty-field fixture; no mismatch or runtime error occurred.
The full run took 39.21 seconds on this host. The audit stops before Nobleman
resolves, when a Flip monster may be publicly revealed; it does not validate
the later effect or every possible prior information state.

Keep older replay files byte-for-byte when they back SHA-256-bound reviews:
reading and verifying v23 is supported, but rewriting it with a newer writer
can change its JSON bytes and invalidate those sidecar hashes.

`goat_ai.replay.verify_trajectory` reconstructs a duel from its seed and
decklists, compares each player-visible observation and complete legal-action
set with the recording, applies the selected action, and checks the result.
The optional replay-viewer reviewer export selects the engine by the recorded
GOAT or narrow MR1 protocol ruleset, rejects unknown rulesets, runs that
engine's verifier first, then
reconstructs the same duel and combines the two player-scoped native views
at each decision. It stores hand, Set field, banished, and Extra Deck identities
in a SHA-256-bound `.review.json` sidecar and generated HTML, not in trajectory
JSON or `GoatEnvironment` observations. Reviewer mode disables action labels
in the browser to avoid training on decisions inspected with hidden information.
The reviewer exporter additionally queries the native engine's private Deck
locations after verifying the replay and stores each player's *current*
remaining Deck in draw order, top card first, at every frame. It checks those
lengths against both player-visible Deck counts. The ordinary label viewer
continues to show only starting Main Deck composition and current counts;
the agent never receives the private order.
The v19 equip relation comes from ocgcore's `QUERY_EQUIP_CARD` field on the
Spell/Trap Zone. The adapter exposes only the field slot of a face-up Equip
Card's current target, including a monster absorbed by Thousand-Eyes Restrict;
it exposes that public relation even when the Equip Card is face-down, without revealing its identity.
The default PyTorch feature version 10 and experimental version 12 omit
this relation. Opt-in versions 13 and 14 bind the Equip Spell embedding to its public
monster target slot. Version 14 also binds public chain targets to their links. A first small held-out comparison found no strength gain; see [evaluation](evaluation.md).
Opt-in version 15 adds twelve public occupancy features: own and opposing
face-up/face-down monster and Spell/Trap counts, plus each player's Graveyard
and banished counts. Field counts use only visible zones and positions; they
do not include hidden card identities. The default remains version 10 so old
checkpoints keep their exact feature width.
Opt-in version 16 branches from version 12 and adds four action-specific
combat numbers for an offered attack: the attacker's public ATK, its margin
against the weakest visible opposing battle stat, whether all opposing
monsters have visible battle stats, and whether the opposing field is empty.
The margin is zero when a hidden monster prevents that comparison. It is
computed from the same redacted observation and legal action available to
every agent; no native private query or hidden opponent card ID is used.
Schemas v3–v23 verify deck contents and native asset fingerprints as well as the
recorded path. Callers must retain the original deck files and native assets;
the recording stores hashes, not copies. Older v1/v2 recordings can still be
replayed but lack these content checks.

`goat_ai.evaluation.run_tournament` depends only on the `RulesEngine` and agent interfaces. It runs each seed and matchup with both seat assignments and records wins, losses, draws, decisions, and a Wilson interval for decisive wins. The native CLI adds deck and asset fingerprints. This keeps evaluation separate from policy implementation and makes later checkpoint opponents possible without changing the duel engine.

The intended playing agent uses a learned policy over the native engine's legal actions. The engine's legality and information boundaries are permanent constraints. `TacticalHeuristicAgent` is a versioned baseline and synthetic demonstration source; its card-value preferences are training guidance, not part of the neural policy by default. Optional inference guards are experimental and must be evaluated as separate agent variants. Experimental policy features v24–v25 estimate visible Heavy Storm and Nobleman card trades before chain responses and allow a small learned logit correction, without changing the engine's legal actions or exposing hidden identities. Opt-in feature v28 adds per-card amounts, type, and total for native counter-allocation choices; a v23 checkpoint can warm-start it with zero weights on the new inputs. It has no measured playing-strength result. Opt-in feature v29 adds the public face-up field age to v28 card inputs, with a zero-extended v23 warm start; it has no measured playing-strength result. A narrow selection-progress rule prevents a known multi-card prompt loop; it is an interface safeguard rather than a strategic card rule. Retain strategic guards in a future release only if independent cross-deck tests show they improve the final agent.

`run_tournament_parallel` executes the same schedule in spawned processes and
returns results in schedule order. It requires pickleable top-level agent and
engine factories, such as a class or `functools.partial`; spawning avoids
inheriting live native duel state. The native evaluation CLI accepts
`--workers`. The engine and public agent interfaces are unchanged, so future
network inference can use the same schedule with a suitable worker factory.

