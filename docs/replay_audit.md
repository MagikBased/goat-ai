# Early replay decision audit

Review each agent's decisions from its own player-visible observation and legal
actions. The replay viewer's reviewer reveals are for human diagnosis only; they
must never feed a policy or a baseline. Viewer frames below are one-based; JSON
`decisions` indices are one less. The agent is identified from trajectory
`skill_metadata`, not inferred from the viewer's opponent/your-view label.

## Seed 2202, policy versus CombatHeuristicAgent v3

Replay: `replays/policy_vs_combat_2202.json`. Policy P0 uses
`combat_fourdeck_fv17_v3_17000_17003.pt`; P1 is CombatHeuristicAgent v3.

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
removal. The current observation does not explicitly identify the turn player,
so the guard allows either player's End Phase; prioritizing the opponent's End
Phase needs a versioned observation-field change. A stronger policy also needs
opponent-aware value estimates and training
examples for these exceptions.

To inspect the guarded seed 2202 duel, open
`replays/policy_guard_vs_combat_2202.html`. The JSON trajectory is independently
replayed through the native engine before the recorder accepts it. Because the
guard changes early actions, later frame numbers differ from the original.

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
