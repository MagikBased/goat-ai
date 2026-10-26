# Competitive card audit priorities

## Contemporary 2005 evidence

The [published SJC Indianapolis 2005 Top 8 Main Decks](https://www.goatformat.com/home/top-8-decklists7022761) now provide the primary card-priority signal for **play in 2005**. The preserved article credits Metagame.com (2005). Our [transcription](../configs/historical/sjc_indianapolis_2005_top8_main.csv) contains Main Deck names and copy counts only; it does not by itself supply playable YDKs or assert that each card's present-day simulator script matches its 2005 ruling. The source prints Main Deck totals of 40, 40, 42, 42, 38, 40, 39, and 39. The 42-card lists are legal; the 38- and 39-card lists fall below the minimum and cannot be used as printed. We preserve all published counts without filling or dropping cards. This Top 8 is one event and cannot establish overall 2005 metagame play rates.

Five published lists are encoded as playable 2005 fixtures: [Matt Peddle's](../examples/decks/goat_control_matt_peddle_indianapolis_2005.ydk) 40-card Goat Control, [Michael Fukuyama's](../examples/decks/goat_control_michael_fukuyama_indianapolis_2005.ydk) 40-card Goat Control, [Jesse Twohig's](../examples/decks/goat_control_jesse_twohig_indianapolis_2005.ydk) 42-card Goat Control, [Daryl Gessler's](../examples/decks/gravekeeper_daryl_gessler_indianapolis_2005.ydk) 42-card Gravekeeper deck, and [Cas Stomphorst's](../examples/decks/flip_control_cas_stomphorst_indianapolis_2005.ydk) 40-card Flip Control deck. Their Fusion Decks are preserved as listed (16, 19, 23, three, and 51 cards respectively); published Side Decks are omitted because current evaluation runs single duels. Source-name comparison and pinned whitelist validation check every Main and Fusion card ID, and all five complete native duels. They add contemporary competitive decks to full-duel protocol testing without changing the six-list later-GOAT ranking below. Juan Cardenas's printed 38-card Main Deck remains in the source transcription but is not executable as published.

| Card | Published Top 8 lists | Copies |
| --- | ---: | ---: |
| Book of Moon | 8 | 15 |
| Tsukuyomi | 8 | 12 |
| Delinquent Duo, Graceful Charity, Heavy Storm, Mirror Force, Pot of Greed, Ring of Destruction, Sinister Serpent, Snatch Steal, Swords of Revealing Light, Tribe-Infecting Virus | 8 each | 8 each |
| Scapegoat | 7 | 16 |
| Magician of Faith, Metamorphosis | 7 each | 15 each |
| Nobleman of Crossout | 7 | 14 |
| Airknight Parshath | 7 | 9 |
| Black Luster Soldier, Breaker, Call of the Haunted, D.D. Warrior Lady, Mystical Space Typhoon, Premature Burial, Sangan, Torrential Tribute | 7 each | 7 each |

Run `PYTHONPATH=src:. .venv/bin/python -m scripts.rank_2005_cards --top 30` to reproduce the 2005 ranking. Work through these commonly listed cards first, selecting specific untested historical interactions rather than treating a card mention in a fixture as complete coverage. For example, the 2005 lists move Tsukuyomi, Scapegoat, Magician of Faith, Metamorphosis, and Sinister Serpent higher than the later tournament sample alone would suggest. Retain archetype-specific regression work where it tests an interaction with a common card.

For the next correctness pass, prioritize **new interactions among cards appearing in at least seven of these eight lists**: Book of Moon, Tsukuyomi, the ubiquitous one-copy power Spells and Traps, Scapegoat, Magician of Faith, Metamorphosis, Nobleman of Crossout, Airknight Parshath, and the seven-list control staples. Prefer paired branches that test a real choice, ownership, timing, or information boundary. The Snatch Steal versus Mirror Force attack fixture is one such branch: both cards appear in seven or more lists, and the fixture checks where the stolen monster and Equip Spell go after destruction. Continue to cover an archetype card when it exercises one of these staples, but defer isolated low-frequency card cases until common interactions and known 2005 discrepancies have better coverage. This is a work order for this small corpus, not a claim about all GOAT tournament play.

## Later GOAT tournaments

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

For the current audit, use the contemporary sample above to choose historically common cards. Use these later lists to cover modern GOAT archetypes and matchup cards such as Dekoichi, Trap Dustshoot, and Chaos Sorcerer. When a common card already has a fixture, add a distinct historically sourced interaction or an interruption/visibility branch instead of counting another setup mention as coverage. Keep unusual cards in scope only when needed to exercise one of these interactions or a deck-defining line. Neither sample measures overall play rates.

Reproduce the counts with:

```bash
.venv/bin/python scripts/rank_competitive_cards.py --top 30 \
  --cards-db .cache/goat-ai/database/cards.cdb \
  --cards-db .cache/goat-ai/database/goat-entries.cdb \
  --cards-db .cache/goat-ai/database/cards-unofficial.cdb
```

The three pinned card databases supply names, including GOAT and pre-errata variants. Omit the `--cards-db` flags to rank by card ID without native assets. Both ranking commands use the same [tournament corpus definition](../src/goat_ai/evaluation/competitive_corpus.py), so guide and probe decks are excluded. The [fixture-reference report](competitive_action_coverage.md) adds exact numeric test references, which require human review before they count as ruling evidence.
