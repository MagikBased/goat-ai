"""The contemporary card-priority sample remains source-faithful."""

from goat_ai.evaluation.historical_corpus import (
    historical_card_counts,
    historical_main_decks,
)


def test_indianapolis_top8_prevalence_and_published_totals():
    decks = historical_main_decks()
    assert len(decks) == 8
    assert {name: sum(cards.values()) for name, cards in decks.items()} == {
        "Matt Peddle": 40,
        "Michael Fukuyama": 40,
        "Jesse Twohig": 42,
        "Daryl Gessler": 42,
        "Juan Cardenas": 38,
        "Cas Stomphorst": 40,
        "Chris Mark": 39,
        "Nareg Torossian": 39,
    }
    rows = {name: (lists, copies) for name, lists, copies
            in historical_card_counts()}
    assert rows["Heavy Storm"] == (8, 8)
    assert rows["Book of Moon"] == (8, 15)
    assert rows["Magician of Faith"] == (7, 15)
    assert rows["Gravekeeper's Spy"] == (1, 3)
