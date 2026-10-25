"""Morphing Jar draws new hands before discarded Night Assailants recover."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

MORPHING_JAR = 33508719
NIGHT_ASSAILANT = 16226796


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_morphing_jar_discards_two_nights_then_recovers_both(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{MORPHING_JAR}.lua",
               f"pre-errata/c{NIGHT_ASSAILANT}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("Morphing Jar / Night Assailant scripts not installed")
    deck = tmp_path / "jar_nights.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        MORPHING_JAR, NIGHT_ASSAILANT, NIGHT_ASSAILANT,
        *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert MORPHING_JAR in {card.code for card in obs.hand}
        assert sum(card.code == NIGHT_ASSAILANT for card in obs.hand) == 2
        set_jar = flipped = False
        old_hands = old_decks = None
        trigger_count = target_slots = 0
        for _ in range(95):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not set_jar:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == MORPHING_JAR), None)
                set_jar |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not flipped:
                action = next((a for a in actions if a.kind == "flip_summon"
                               and a.parameters.get("code") == MORPHING_JAR), None)
                if action is not None:
                    other = env.engine.probe.observation(1)
                    old_hands = (Counter(card.code for card in obs.hand),
                                 Counter(card.code for card in other.hand))
                    assert old_hands[0][NIGHT_ASSAILANT] == 2
                    old_decks = obs.deck_counts
                    flipped = True
            if flipped and actions[0].kind == "chain" and all(
                    a.parameters.get("code") == NIGHT_ASSAILANT for a in actions):
                assert MORPHING_JAR in {card.code for card in obs.field}
                assert obs.deck_counts == (old_decks[0] - 5, old_decks[1] - 5)
                action = actions[0]
                trigger_count += 1
            if flipped and actions[0].kind == "select_card":
                assert len(actions) == 1
                assert actions[0].parameters.get("code") == NIGHT_ASSAILANT
                assert actions[0].parameters.get("location") == 16
                action = actions[0]
                target_slots += 1
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            other = env.engine.probe.observation(1)
            if len(other.private_reveals) == 2:
                assert flipped and old_hands is not None and old_decks is not None
                assert trigger_count == 1 and target_slots == 2
                assert obs.deck_counts == (old_decks[0] - 5, old_decks[1] - 5)
                assert len(obs.hand) == 7 and other.opponent_hand_count == 7
                assert sum(card.code == NIGHT_ASSAILANT for card in obs.hand) == 2
                assert Counter(card.code for card in obs.graveyards[0]) == (
                    old_hands[0] - Counter({NIGHT_ASSAILANT: 2}))
                assert Counter(card.code for card in obs.graveyards[1]) == old_hands[1]
                assert [reveal.recipient for reveal in other.private_reveals] == [1, 1]
                assert [[card.code for card in reveal.cards]
                        for reveal in other.private_reveals] == [
                            [NIGHT_ASSAILANT], [NIGHT_ASSAILANT]]
                assert not obs.private_reveals
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                agents = (RandomAgent(100), RandomAgent(101))
                for _ in range(5000):
                    choice = agents[obs.acting_player].select_action(
                        obs, env.legal_actions())
                    obs = env.step(choice)
                    if env.is_terminal():
                        path = tmp_path / "jar_nights.json"
                        write_trajectory(path, env.trajectory())
                        assert verify_trajectory(read_trajectory(path),
                                                 ExperimentalOcgcoreEngine(root)) == len(
                                                     env.trajectory().decisions)
                        return
                pytest.fail("Morphing Jar / Night Assailant duel did not finish")
    pytest.fail("Morphing Jar did not resolve both Night Assailant triggers")
