# Competitive-deck action coverage probe

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
