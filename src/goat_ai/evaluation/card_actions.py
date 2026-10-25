"""Count player-visible card-source opportunities, not target identities."""

from collections import Counter

SOURCE_KINDS = frozenset({
    "activate", "chain", "normal_summon", "flip_summon", "special_summon",
    "set_monster", "set_spell_trap", "attack", "change_position",
})


def count_source_actions(legal_actions, selected_action,
                         offered: Counter, selected: Counter) -> None:
    """Count a card once per decision where its source action is offered."""
    choices = {(action.parameters["code"], action.kind)
               for action in legal_actions
               if action.kind in SOURCE_KINDS
               and isinstance(action.parameters.get("code"), int)}
    offered.update(choices)
    choice = (selected_action.parameters.get("code"), selected_action.kind)
    if choice in choices:
        selected[choice] += 1


def count_chain_response(observation, selected_action,
                         responses: Counter) -> None:
    """Count a chosen card response to the latest public chain link."""
    if selected_action.kind != "chain" or not observation.chain:
        return
    code = selected_action.parameters.get("code")
    if isinstance(code, int):
        responses[code, observation.chain[-1].card_code] += 1
