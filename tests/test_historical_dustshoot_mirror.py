"""Two Dustshoot links reveal each hand only to the opposing chooser."""

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


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_dustshoot_chained_to_dustshoot_keeps_both_hand_reveals_scoped(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    script = f"official/c{DUSTSHOOT}.lua"
    if not (root / "scripts" / script).is_file():
        pytest.skip("Trap Dustshoot script not installed")
    deck = tmp_path / "dustshoot.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        DUSTSHOOT, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), str(deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert DUSTSHOOT in {c.code for c in obs.hand}
        assert DUSTSHOOT in {c.code for c in env.engine.probe.observation(1).hand}
        set_by = set()
        first = second = second_choice = first_choice = False
        first_reveal = second_reveal = Counter()
        returned_from_1 = returned_from_0 = None
        initial_decks = obs.deck_counts
        for _ in range(95):
            actions = env.legal_actions()
            action = None
            if obs.turn in (1, 2) and obs.acting_player == obs.turn - 1 \
                    and obs.acting_player not in set_by:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                if action is not None:
                    set_by.add(obs.acting_player)
            if set_by == {0, 1} and obs.turn == 3 \
                    and obs.acting_player == 1 and not first:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                first |= action is not None
            if first and obs.turn == 3 and obs.acting_player == 0 and not second:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                if option is not None:
                    assert [link.card_code for link in obs.chain] == [DUSTSHOOT]
                    action = option
                    second = True
            if second and not second_choice and actions[0].kind == "select_card":
                assert obs.acting_player == obs.viewer == 0
                assert [link.card_code for link in obs.chain] == [DUSTSHOOT] * 2
                first_reveal = Counter(c.code for event in obs.private_reveals
                                       if event.recipient == 0 for c in event.cards
                                       if c.controller == 1 and c.location == 2)
                assert first_reveal
                assert Counter(a.parameters["code"] for a in actions) == first_reveal
                assert all("sequence" not in a.parameters for a in actions)
                assert not env.engine.probe.observation(1).private_reveals
                action = actions[0]
                returned_from_1 = action.parameters["code"]
                second_choice = True
            if second_choice and not first_choice and action is None \
                    and actions[0].kind == "select_card":
                assert obs.acting_player == obs.viewer == 1
                second_reveal = Counter(c.code for event in obs.private_reveals
                                        if event.recipient == 1 for c in event.cards
                                        if c.controller == 0 and c.location == 2)
                assert second_reveal
                assert Counter(a.parameters["code"] for a in actions) == second_reveal
                assert all("sequence" not in a.parameters for a in actions)
                assert Counter(env.engine.probe.observation(0)
                               .known_opponent_hand_cards) == (
                                   first_reveal - Counter((returned_from_1,)))
                action = actions[0]
                returned_from_0 = action.parameters["code"]
                first_choice = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if first_choice and not obs.chain and obs.deck_counts == initial_decks:
                # Each player drew once after the initial observation and
                # each Deck received one Dustshoot return.
                player0 = env.engine.probe.observation(0)
                player1 = env.engine.probe.observation(1)
                assert Counter(player0.known_opponent_hand_cards) == (
                    first_reveal - Counter((returned_from_1,)))
                assert Counter(player1.known_opponent_hand_cards) == (
                    second_reveal - Counter((returned_from_0,)))
                assert Counter(player0.known_opponent_hand_cards) == Counter(
                    card.code for card in player1.hand)
                assert Counter(player1.known_opponent_hand_cards) == Counter(
                    card.code for card in player0.hand)
                assert all(event.recipient == 0 for event in player0.private_reveals)
                assert all(event.recipient == 1 for event in player1.private_reveals)
                assert env.engine.probe.loaded_script_sha256[script]
                agents = (RandomAgent(3), RandomAgent(4))
                for _ in range(5000):
                    if env.is_terminal():
                        trajectory = env.trajectory()
                        path = tmp_path / "dustshoot_mirror.json"
                        write_trajectory(path, trajectory)
                        assert verify_trajectory(read_trajectory(path),
                                                 ExperimentalOcgcoreEngine(root)) \
                            == len(trajectory.decisions)
                        return
                    action = agents[obs.acting_player].select_action(
                        obs, env.legal_actions())
                    obs = env.step(action)
                pytest.fail("Dustshoot mirror duel did not reach terminal state")
    pytest.fail(f"Dustshoot chain stalled: set={set_by} first={first} second={second} "
                f"choices={second_choice}/{first_choice} turn={obs.turn} "
                f"decks={obs.deck_counts} initial={initial_decks} chain={obs.chain}")
