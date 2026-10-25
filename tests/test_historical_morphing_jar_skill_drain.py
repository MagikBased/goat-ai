"""Skill Drain chained to Morphing Jar's Flip Effect stops the hand reset."""

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
SKILL_DRAIN = 82732705


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_drain", [False, True])
def test_skill_drain_response_to_morphing_jar_flip_effect(tmp_path, chain_drain):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (MORPHING_JAR, SKILL_DRAIN)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("Morphing Jar / Skill Drain scripts not installed")
    jar_deck = tmp_path / "jar.ydk"
    jar_deck.write_text("#main\n" + "\n".join(map(str, (
        MORPHING_JAR, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    drain_deck = tmp_path / "drain.ydk"
    drain_deck.write_text("#main\n" + "\n".join(map(str, (
        SKILL_DRAIN, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(jar_deck), str(drain_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert MORPHING_JAR in {card.code for card in obs.hand}
        assert SKILL_DRAIN in {card.code for card in env.engine.probe.observation(1).hand}
        jar_set = drain_set = flipped = response_seen = False
        before_hands = before_decks = None
        for _ in range(100):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not jar_set:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == MORPHING_JAR), None)
                jar_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not drain_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SKILL_DRAIN), None)
                drain_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not flipped:
                action = next((a for a in actions if a.kind == "flip_summon"
                               and a.parameters.get("code") == MORPHING_JAR), None)
                if action is not None:
                    other = env.engine.probe.observation(1)
                    before_hands = (Counter(c.code for c in obs.hand),
                                    Counter(c.code for c in other.hand))
                    before_decks = obs.deck_counts
                    flipped = True
            if flipped and obs.acting_player == 1 and not response_seen \
                    and [link.card_code for link in obs.chain] == [MORPHING_JAR]:
                drain = next((a for a in actions if a.kind == "chain"
                              and a.parameters.get("code") == SKILL_DRAIN), None)
                assert drain is not None
                if chain_drain:
                    action = drain
                response_seen = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if response_seen and before_decks is not None and obs.turn == 3 \
                    and obs.acting_player == 0 and obs.chain == () \
                    and any(a.kind == "end_phase" for a in env.legal_actions()):
                own = env.engine.probe.observation(0)
                other = env.engine.probe.observation(1)
                assert any(c.code == MORPHING_JAR and c.position == "faceup"
                           for c in own.field)
                if chain_drain:
                    assert own.life_points == (8000, 7000)
                    assert own.deck_counts == before_decks
                    assert (Counter(c.code for c in own.hand),
                            Counter(c.code for c in other.hand)) == before_hands
                    assert any(c.code == SKILL_DRAIN and c.position == "faceup"
                               for c in own.field)
                else:
                    assert own.life_points == (8000, 8000)
                    assert own.deck_counts == (before_decks[0] - 5,
                                               before_decks[1] - 5)
                    assert len(own.hand) == len(other.hand) == 5
                    assert Counter(c.code for c in own.graveyards[0]) == before_hands[0]
                    assert Counter(c.code for c in own.graveyards[1]) == before_hands[1]
                    assert not any(c.code == SKILL_DRAIN for c in own.graveyards[1])
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                agents = (RandomAgent(52), RandomAgent(53))
                for _ in range(5000):
                    choice = agents[obs.acting_player].select_action(
                        obs, env.legal_actions())
                    obs = env.step(choice)
                    if env.is_terminal():
                        path = tmp_path / f"jar_drain_{chain_drain}.json"
                        write_trajectory(path, env.trajectory())
                        assert verify_trajectory(read_trajectory(path),
                                                 ExperimentalOcgcoreEngine(root)) == len(
                                                     env.trajectory().decisions)
                        return
                pytest.fail("Morphing Jar / Skill Drain duel did not finish")
    pytest.fail("Morphing Jar / Skill Drain chain did not resolve")
