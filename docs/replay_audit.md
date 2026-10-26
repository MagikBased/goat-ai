# Early replay decision audit

Review each agent's decisions from its own player-visible observation and legal
actions. The replay viewer's reviewer reveals are for human diagnosis only; they
must never feed a policy or a baseline. Viewer frames below are one-based; JSON
`decisions` indices are one less. The agent is identified from trajectory
`skill_metadata`, not inferred from the viewer's opponent/your-view label.

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
