"""Common GOAT draw/discard staples and their information boundaries."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

GRACEFUL_CHARITY = 79571449
DELINQUENT_DUO = 44763025


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_graceful_and_duo_discard_choices_keep_hands_private(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (GRACEFUL_CHARITY, DELINQUENT_DUO):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    deck = tmp_path / "staples.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL_CHARITY, DELINQUENT_DUO, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        graceful_chosen = graceful_resolved = duo_chosen = False
        for _ in range(35):
            actions = env.legal_actions()
            action = None
            if actions[0].kind == "select_cards" and not graceful_chosen:
                assert observation.viewer == observation.acting_player == 0
                assert len(observation.hand) == 8
                assert observation.deck_counts[0] == 31
                assert len(actions) == 28
                hand = Counter(card.code for card in observation.hand)
                for choice in actions:
                    selected = choice.parameters["cards"]
                    assert len(selected) == 2
                    assert all(card["controller"] == 0 and card["location"] == 2
                               for card in selected)
                    assert not Counter(card["code"] for card in selected) - hand
                other = env.engine.probe.observation(1)
                assert other.opponent_hand_count == 8
                assert not other.private_reveals
                assert all(card.controller == 1 for card in other.hand)
                graceful_chosen = True
                action = actions[0]
            elif actions[0].kind == "select_card" and duo_chosen:
                assert observation.viewer == observation.acting_player == 1
                assert len(observation.hand) == 4
                assert len(observation.graveyards[1]) == 1
                assert observation.life_points == (7000, 8000)
                assert len(actions) == 4
                assert {choice.parameters["sequence"] for choice in actions} == set(range(4))
                assert all(choice.parameters["controller"] == 1
                           and choice.parameters["location"] == 2 for choice in actions)
                other = env.engine.probe.observation(0)
                assert other.opponent_hand_count == 4
                assert not other.private_reveals
                assert all(card.controller == 0 for card in other.hand)
                selected_code = actions[0].parameters["code"]
                observation = env.step(actions[0])
                assert len(observation.graveyards[1]) == 2
                assert selected_code in [card.code for card in observation.graveyards[1]]
                assert env.engine.probe.observation(1).opponent_hand_count == 5
                return

            if (graceful_chosen and not graceful_resolved
                    and len(observation.graveyards[0]) == 3):
                graceful_resolved = True
                assert len(env.engine.probe.observation(0).hand) == 6
                assert env.engine.probe.observation(0).deck_counts[0] == 31
                assert env.engine.probe.observation(1).opponent_hand_count == 6
                assert env.engine.probe.observation(0).opponent_hand_count == 5
            if graceful_resolved and not duo_chosen and observation.acting_player == 0:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == DELINQUENT_DUO), action)
                duo_chosen |= action is not None and action.kind == "activate"
            if not graceful_chosen and observation.acting_player == 0:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == GRACEFUL_CHARITY), action)
            if action is None:
                action = next((a for a in actions if a.kind in ("place", "pass")), None)
            if action is None:
                action = next((a for a in actions if a.kind == "end_phase"), actions[0])
            observation = env.step(action)
    pytest.fail("Graceful Charity and Delinquent Duo did not reach both discard choices")
