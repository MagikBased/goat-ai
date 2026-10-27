"""An exchanged Thunder Dragon searches its controller's Deck, not its owner's."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

EXCHANGE = 5556668
THUNDER_DRAGON = 504700054


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_exchanged_thunder_dragon_searches_new_controllers_deck(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/goat/c{THUNDER_DRAGON}.lua").is_file():
        pytest.skip("GOAT Thunder Dragon script not installed")
    deck_a = tmp_path / "exchange_thunder.ydk"
    deck_b = tmp_path / "opponent_thunder.ydk"
    deck_a.write_text("#main\n" + "\n".join(map(str, (
        EXCHANGE, *([THUNDER_DRAGON] * 3), *VANILLA_DECK[4:]))) + "\n#extra\n!side\n")
    deck_b.write_text("#main\n" + "\n".join(map(str, (
        *([THUNDER_DRAGON] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck_a), str(deck_b), seed=28,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert observation.known_opponent_hand_cards == ()
        exchange_activated = False
        exchanged = 0
        thunder_activated = False
        searched = False
        fallback = RandomAgent(28)
        for _ in range(3000):
            actions = env.legal_actions()
            action = None
            if not exchange_activated and observation.acting_player == 0:
                action = next((item for item in actions if item.kind == "activate"
                               and item.parameters.get("code") == EXCHANGE), None)
                exchange_activated = action is not None
            if action is None and exchange_activated and exchanged < 2 \
                    and actions[0].kind == "select_card":
                if observation.acting_player == 0:
                    action = next(item for item in actions
                                  if item.parameters.get("code") == THUNDER_DRAGON)
                else:
                    action = next(item for item in actions
                                  if item.parameters.get("code") != THUNDER_DRAGON)
                assert action.parameters.get("location") == 2
                exchanged += 1
            if action is None and exchanged == 2 and not thunder_activated \
                    and observation.acting_player == 0:
                action = next((item for item in actions if item.kind == "activate"
                               and item.parameters.get("code") == THUNDER_DRAGON), None)
                thunder_activated = action is not None
            if action is None and thunder_activated and not searched \
                    and any(item.kind == "select_cards" for item in actions):
                action = next(item for item in actions if item.kind == "select_cards"
                              and len(item.parameters.get("cards", ())) == 2)
                searched = True
            if action is None and not searched:
                action = next((item for item in actions if item.kind == "pass"), None)
                if action is None:
                    action = next((item for item in actions if item.kind == "place"), None)
            if action is None:
                action = fallback.select_action(observation, actions)
            observation = env.step(action)
            if searched and thunder_activated:
                own = env.engine.probe.observation(0)
                other = env.engine.probe.observation(1)
                if own.deck_counts[0] == 32:
                    assert other.deck_counts[1] == 35
                    assert sum(card.code == THUNDER_DRAGON for card in own.hand) == 2
                    assert sum(card.code == THUNDER_DRAGON
                               for card in own.graveyards[0]) == 0
                    assert sum(card.code == THUNDER_DRAGON
                               for card in other.graveyards[1]) == 1
                    assert other.known_opponent_hand_cards == (
                        THUNDER_DRAGON, THUNDER_DRAGON)
                    assert [(event.recipient, len(event.cards))
                            for event in own.private_reveals] == [(0, 5)]
                    assert [card.code for card in other.private_reveals[-1].cards] == [
                        THUNDER_DRAGON, THUNDER_DRAGON]
                    assert f"goat/c{THUNDER_DRAGON}.lua" in (
                        env.engine.probe.loaded_script_sha256)
                    searched = False
                    break
        else:
            pytest.fail("Exchange / Thunder Dragon search was not reached")

        for _ in range(3000):
            if env.is_terminal():
                break
            observation = env.step(fallback.select_action(
                observation, env.legal_actions()))
        assert env.is_terminal(), "Exchange / Thunder Dragon duel did not finish"
        trajectory = env.trajectory()
    assert trajectory.winner in (0, 1, None)
    path = tmp_path / "exchange_thunder.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    assert verify_trajectory(loaded, ExperimentalOcgcoreEngine(root)) == len(
        trajectory.decisions)
    assert audit_trajectory_visibility(loaded)["decisions"] == len(trajectory.decisions)
