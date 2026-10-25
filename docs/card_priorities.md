# Competitive card audit priorities

The card-specific correctness audit starts with cards used in the six sourced competitive Main Deck examples under `examples/decks/`. This is a small, deliberately varied project corpus, **not** a measured GOAT metagame or tournament play-rate estimate. Side and Extra Deck cards are excluded from this count. A test for one ruling does not certify every interaction of that card.

As of the six current lists, the highest Main Deck prevalence is:

| Card | Lists | Copies |
| --- | ---: | ---: |
| Book of Moon | 6 | 15 |
| Nobleman of Crossout (GOAT) | 6 | 12 |
| Delinquent Duo, Snatch Steal, Pot of Greed, Breaker, Graceful Charity, Black Luster Soldier (GOAT), Ring of Destruction (pre-errata) | 6 each | 6 each |
| Dekoichi | 5 | 13 |
| Mystical Space Typhoon, Heavy Storm, Mirror Force, Sangan (GOAT) | 5 each | 5 each |
| Magician of Faith, Trap Dustshoot | 4 each | 9 each |
| Chaos Sorcerer | 4 | 6 |
| Tsukuyomi | 3 | 6 |

Use list prevalence first and total copies second when choosing among unaudited common interactions. Prefer a sourced historical ruling with a concrete competitive consequence and a deterministic native fixture. Also cover archetype-defining cards with lower cross-list prevalence; for example, Return and Bazoo appear in only one of these six lists but are central to Chaos Return.

Reproduce the counts with:

```bash
.venv/bin/python scripts/rank_competitive_cards.py --top 30 \
  --cards-db .cache/goat-ai/database/cards.cdb \
  --cards-db .cache/goat-ai/database/goat-entries.cdb \
  --cards-db .cache/goat-ai/database/cards-unofficial.cdb
```

The three pinned card databases supply names, including GOAT and pre-errata variants. Omit the `--cards-db` flags to rank by card ID without native assets. The six list paths are explicit in the script so probe decks are never counted as competitive evidence.
