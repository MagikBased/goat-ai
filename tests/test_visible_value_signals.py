from goat_ai.observations import CardView, Observation
from scripts.audit_visible_value_signals import visible_margins, win_loss_auc


def test_pairwise_auc_uses_independent_games_and_ties() -> None:
    assert win_loss_auc([2, 1], [1, 0]) == 0.875
    assert win_loss_auc([], [1]) is None


def test_visible_margins_count_hidden_field_cards_without_revealing_them() -> None:
    base = {"viewer": 0, "acting_player": 0, "turn": 4, "phase": "main1",
            "life_points": (6000, 7000),
            "hand": (CardView(0, "hand", "hidden", 123),),
            "graveyards": ((), ()), "banished": ((), ()),
            "opponent_hand_count": 2, "deck_counts": (30, 30),
            "extra_deck_counts": (0, 0)}
    own = CardView(0, "monster", "faceup", 456)
    sheep = CardView(0, "monster", "faceup", 73915052)
    hidden = CardView(1, "monster", "facedown", None)
    revealed = CardView(1, "monster", "faceup", 789)
    assert visible_margins(Observation(field=(own, sheep, hidden), **base)) == (-1, -1.0)
    assert visible_margins(Observation(field=(own, sheep, revealed), **base)) == (-1, -1.0)
