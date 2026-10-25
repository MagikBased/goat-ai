"""Morphing Jar invalidates knowledge of a publicly searched hand."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

MORPHING_JAR = 33508719
THUNDER_DRAGON = 504700054


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_jar_clears_known_thunder_dragons_after_both_hands_change(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{MORPHING_JAR}.lua",
               f"goat/c{THUNDER_DRAGON}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("Morphing Jar / Thunder Dragon scripts not installed")
    deck = tmp_path / "jar_thunder.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        MORPHING_JAR, THUNDER_DRAGON, THUNDER_DRAGON, THUNDER_DRAGON,
        *VANILLA_DECK[4:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert MORPHING_JAR in {card.code for card in obs.hand}
        assert sum(card.code == THUNDER_DRAGON for card in obs.hand) == 1
        searched = jar_set = jar_flipped = False
        old_deck_counts = None
        for _ in range(95):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not searched:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == THUNDER_DRAGON), None)
                if any(a.kind == "select_cards" for a in actions):
                    action = next((a for a in actions if a.kind == "select_cards"
                                   and len(a.parameters.get("cards", ())) == 2), None)
                    searched |= action is not None
                if searched and not jar_set and action is None:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == MORPHING_JAR), None)
                    jar_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not jar_flipped:
                action = next((a for a in actions if a.kind == "flip_summon"
                               and a.parameters.get("code") == MORPHING_JAR), None)
                if action is not None:
                    other = env.engine.probe.observation(1)
                    # The hidden Set could have been either searched copy,
                    # so only one remains guaranteed in the opponent's hand.
                    assert other.known_opponent_hand_cards == (THUNDER_DRAGON,)
                    assert other.opponent_hand_count == len(obs.hand)
                    assert [[card.code for card in event.cards]
                            for event in other.private_reveals] == [
                                [THUNDER_DRAGON, THUNDER_DRAGON]]
                    old_deck_counts = obs.deck_counts
                    jar_flipped = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if jar_flipped and old_deck_counts is not None \
                    and obs.deck_counts == (old_deck_counts[0] - 5,
                                            old_deck_counts[1] - 5):
                other = env.engine.probe.observation(1)
                assert obs.chain == ()
                assert len(obs.hand) == 5
                assert other.opponent_hand_count == 5
                assert other.known_opponent_hand_cards == ()
                assert [[card.code for card in event.cards]
                        for event in other.private_reveals] == [
                            [THUNDER_DRAGON, THUNDER_DRAGON]]
                assert sum(card.code == THUNDER_DRAGON for card in obs.graveyards[0]) == 3
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                agents = (RandomAgent(3), RandomAgent(4))
                for _ in range(5000):
                    choice = agents[obs.acting_player].select_action(
                        obs, env.legal_actions())
                    obs = env.step(choice)
                    if env.is_terminal():
                        path = tmp_path / "jar_thunder.json"
                        write_trajectory(path, env.trajectory())
                        assert verify_trajectory(read_trajectory(path),
                                                 ExperimentalOcgcoreEngine(root)) == len(
                                                     env.trajectory().decisions)
                        return
                pytest.fail("Morphing Jar / Thunder Dragon duel did not finish")
    pytest.fail("Morphing Jar did not replace the known Thunder Dragon hand")
