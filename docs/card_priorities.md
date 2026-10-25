# Competitive card audit priorities

The card-specific correctness audit starts with cards used in the six sourced **tournament** Main Decks under `examples/decks/`. The [Flip Control guide deck](../examples/decks/flip_control_goatformat_guide.ydk) remains useful for duel testing but does not enter this ranking. This is a small, deliberately varied project corpus, **not** a measured GOAT metagame or tournament play-rate estimate. Side and Extra Deck cards are excluded from this count. A test for one ruling does not certify every interaction of that card.

As of the six current lists, the highest Main Deck prevalence is:

| Card | Lists | Copies |
| --- | ---: | ---: |
| Book of Moon | 6 | 14 |
| Nobleman of Crossout (GOAT) | 6 | 12 |
| Delinquent Duo, Heavy Storm, Pot of Greed, Breaker, Graceful Charity, Black Luster Soldier (GOAT), Ring of Destruction (pre-errata) | 6 each | 6 each |
| Dekoichi | 5 | 13 |
| Trap Dustshoot | 5 | 12 |
| D.D. Warrior Lady, Mirror Force, Snatch Steal, Torrential Tribute | 5 each | 5 each |
| Chaos Sorcerer | 4 | 6 |
| Mystical Space Typhoon, Sangan (GOAT) | 4 each | 4 each |
| Thunder Dragon (GOAT) | 3 | 9 |
| Magician of Faith | 3 | 6 |

Use list prevalence first and total copies second when choosing among unaudited common interactions. Prefer a sourced historical ruling with a concrete competitive consequence and a deterministic native fixture. Also cover archetype-defining cards with lower cross-list prevalence; for example, Return and Bazoo each appear in two of these six lists and define the Return decks.

Reproduce the counts with:

```bash
.venv/bin/python scripts/rank_competitive_cards.py --top 30 \
  --cards-db .cache/goat-ai/database/cards.cdb \
  --cards-db .cache/goat-ai/database/goat-entries.cdb \
  --cards-db .cache/goat-ai/database/cards-unofficial.cdb
```

The three pinned card databases supply names, including GOAT and pre-errata variants. Omit the `--cards-db` flags to rank by card ID without native assets. Both ranking commands use the same [tournament corpus definition](../src/goat_ai/evaluation/competitive_corpus.py), so guide and probe decks are excluded. The [fixture-reference report](competitive_action_coverage.md) adds exact numeric test references, which require human review before they count as ruling evidence.
