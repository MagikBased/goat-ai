"""Trap Dustshoot's opponent-hand reveal and monster return stay player-scoped."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

DUSTSHOOT = 64697231
BOOK_OF_MOON = 14087893


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_trap_dustshoot_reveals_hand_only_to_chooser_and_returns_monster(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{DUSTSHOOT}.lua").is_file():
        pytest.skip("Trap Dustshoot script not installed")
    own = tmp_path / "dustshoot.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        *([DUSTSHOOT] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(own), "examples/decks/vanilla_probe.ydk", seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        set_trap = activated = selected = False
        chosen_code = before_count = before_deck_count = None
        before_hand = None
        for _ in range(35):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not set_trap:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                set_trap |= action is not None
            if set_trap and not activated and observation.turn == 2 \
                    and observation.acting_player == 0:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                if action is not None:
                    assert observation.opponent_hand_count >= 4
                    assert not observation.private_reveals
                    other = env.engine.probe.observation(1)
                    assert any(c.controller == 0 and c.zone == "spell_trap"
                               and c.position == "facedown" and c.code is None
                               for c in other.field)
                    before_count = observation.opponent_hand_count
                    before_deck_count = observation.deck_counts[1]
                    activated = True
            if activated and not selected and actions[0].kind == "select_card":
                assert observation.acting_player == observation.viewer == 0
                assert observation.chain[0].card_code == DUSTSHOOT
                revealed = [card.code for event in observation.private_reveals
                            if event.recipient == 0 for card in event.cards
                            if card.controller == 1 and card.location == 2]
                assert Counter(a.parameters["code"] for a in actions) == Counter(revealed)
                assert len(revealed) == before_count
                assert all(a.parameters["location"] == 2
                           and "sequence" not in a.parameters for a in actions)
                other = env.engine.probe.observation(1)
                assert not other.private_reveals
                before_hand = Counter(c.code for c in other.hand)
                action = actions[0]
                chosen_code = action.parameters["code"]
                selected = True
            if selected and observation.deck_counts[1] == before_deck_count + 1:
                other = env.engine.probe.observation(1)
                assert len(other.hand) == before_count - 1
                assert before_hand - Counter(c.code for c in other.hand) == {
                    chosen_code: 1}
                assert f"official/c{DUSTSHOOT}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                agents = (RandomAgent(3), RandomAgent(4))
                for _ in range(5000):
                    action = agents[observation.acting_player].select_action(
                        observation, env.legal_actions())
                    observation = env.step(action)
                    if env.is_terminal():
                        trajectory = env.trajectory()
                        assert trajectory.schema_version == 14
                        assert chosen_code is not None
                        path = tmp_path / "dustshoot.json"
                        write_trajectory(path, trajectory)
                        assert verify_trajectory(read_trajectory(path),
                                                 ExperimentalOcgcoreEngine(root)) == len(
                                                     trajectory.decisions)
                        return
                pytest.fail("Trap Dustshoot duel did not finish")
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
    pytest.fail("Trap Dustshoot did not return an opponent monster to the Deck")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_dustshoot_requires_at_least_four_opponent_hand_cards(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{DUSTSHOOT}.lua").is_file():
        pytest.skip("Trap Dustshoot script not installed")
    own = tmp_path / "dustshoot.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        *([DUSTSHOOT] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    opposing = tmp_path / "books.ydk"
    opposing.write_text("#main\n" + "\n".join(map(str, (
        *([BOOK_OF_MOON] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(own), str(opposing), seed=28,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        set_trap = summoned = False
        books_set = 0
        saw_three = False
        for _ in range(65):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not set_trap:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                set_trap |= action is not None
            if observation.turn == 2 and observation.acting_player == 1:
                if not summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    summoned |= action is not None
                if action is None and books_set < 2:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOOK_OF_MOON), None)
                    books_set += action is not None
            if set_trap and observation.acting_player == 0 and books_set == 2:
                if observation.opponent_hand_count == 3:
                    saw_three = True
                    assert not any(a.kind == "chain" and a.parameters.get("code")
                                   == DUSTSHOOT for a in actions)
                if observation.turn == 4 and observation.opponent_hand_count == 4:
                    assert saw_three and summoned
                    assert any(a.kind == "chain" and a.parameters.get("code")
                               == DUSTSHOOT for a in actions)
                    return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
    pytest.fail("Dustshoot hand-size threshold was not exercised")
