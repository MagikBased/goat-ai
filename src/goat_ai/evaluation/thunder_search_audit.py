"""Audit the demonstrated choice at a visible Thunder Dragon Deck search."""

from dataclasses import replace

from goat_ai.replay.trajectory import DecisionRecord

THUNDER_DRAGON = 504700054


def thunder_search_choice(record: DecisionRecord, seat: int) -> str | None:
    """Classify a search only when a Deck copy is a visible legal choice.

    A zero-copy choice is legal in the pinned TCG profile. This audit measures
    the training signal; it does not alter the engine or declare it illegal.
    """
    view = record.observation
    if (view.acting_player != seat or not view.chain
            or view.chain[-1].card_code != THUNDER_DRAGON
            or view.chain[-1].controller != seat):
        return None
    def is_deck_copy(action):
        return (action.kind == "select_card"
                and action.parameters.get("code") == THUNDER_DRAGON
                and action.parameters.get("location") == 1
                and action.parameters.get("controller") == seat)

    if not any(is_deck_copy(action) for action in record.legal_actions):
        return None
    selected = record.selected_action
    if is_deck_copy(selected):
        return "take_one"
    if selected.kind == "select_cards":
        cards = selected.parameters.get("cards", ())
        if not cards:
            return "take_zero"
        if all(card.get("code") == THUNDER_DRAGON
               and card.get("location") == 1
               and card.get("controller") == seat for card in cards):
            return f"take_{len(cards)}"
    return "other"


def correct_staged_thunder_search(
    records: tuple[DecisionRecord, ...], seat: int,
) -> tuple[tuple[DecisionRecord, ...], int]:
    """Make an opt-in synthetic teacher take one offered copy before finishing.

    The original replay and its SHA-256 remain untouched. Later saved states
    are still off-policy after a correction, as in other teacher relabeling.
    """
    corrected = []
    changes = 0
    for record in records:
        if thunder_search_choice(record, seat) == "take_zero":
            copy = next(action for action in record.legal_actions
                        if action.kind == "select_card"
                        and action.parameters.get("code") == THUNDER_DRAGON
                        and action.parameters.get("location") == 1
                        and action.parameters.get("controller") == seat)
            corrected.append(replace(record, selected_action=copy))
            changes += 1
        else:
            corrected.append(record)
    return tuple(corrected), changes
