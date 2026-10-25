"""Book of Moon can preserve Jar's Flip Effect against chained Skill Drain."""

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
BOOK_OF_MOON = 14087893
SKILL_DRAIN = 82732705


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("book_response", [False, True])
def test_book_sets_jar_before_skill_drain_can_negate_its_flip_effect(
        tmp_path, book_response):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (
        MORPHING_JAR, BOOK_OF_MOON, SKILL_DRAIN)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("Morphing Jar / Book of Moon / Skill Drain scripts not installed")
    jar_deck = tmp_path / "jar_book.ydk"
    jar_deck.write_text("#main\n" + "\n".join(map(str, (
        MORPHING_JAR, BOOK_OF_MOON, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    drain_deck = tmp_path / "drain.ydk"
    drain_deck.write_text("#main\n" + "\n".join(map(str, (
        SKILL_DRAIN, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(jar_deck), str(drain_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {MORPHING_JAR, BOOK_OF_MOON} <= {c.code for c in obs.hand}
        assert SKILL_DRAIN in {c.code for c in env.engine.probe.observation(1).hand}
        jar_set = book_set = drain_set = flipped = drain_chained = False
        book_chained = book_targeted = False
        before_hands = before_decks = None
        for _ in range(110):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not jar_set:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == MORPHING_JAR), None)
                    jar_set |= action is not None
                elif not book_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOOK_OF_MOON), None)
                    book_set |= action is not None
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
            if flipped and obs.acting_player == 1 and not drain_chained \
                    and [link.card_code for link in obs.chain] == [MORPHING_JAR]:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SKILL_DRAIN), None)
                assert action is not None
                drain_chained = True
            if drain_chained and obs.acting_player == 0 and not book_chained \
                    and [link.card_code for link in obs.chain] == [
                        MORPHING_JAR, SKILL_DRAIN]:
                book = next((a for a in actions if a.kind == "chain"
                             and a.parameters.get("code") == BOOK_OF_MOON), None)
                assert book is not None
                if book_response:
                    action = book
                    book_chained = True
            if book_chained and not book_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == MORPHING_JAR and a.parameters.get("controller") == 0),
                              None)
                assert action is not None
                book_targeted = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if drain_chained and before_decks is not None and obs.turn == 3 \
                    and obs.acting_player == 0 and obs.chain == () \
                    and any(a.kind == "end_phase" for a in env.legal_actions()):
                own = env.engine.probe.observation(0)
                other = env.engine.probe.observation(1)
                jar = next(c for c in own.field if c.code == MORPHING_JAR)
                assert own.life_points == (8000, 7000)
                assert any(c.code == SKILL_DRAIN and c.position == "faceup"
                           for c in own.field)
                if book_response:
                    assert book_chained and book_targeted
                    assert jar.position == "facedown"
                    hidden_jar = next(c for c in other.field if c.zone == "monster"
                                      and c.controller == 0)
                    assert hidden_jar.code is None and hidden_jar.position == "facedown"
                    assert own.deck_counts == (before_decks[0] - 5,
                                               before_decks[1] - 5)
                    assert len(own.hand) == len(other.hand) == 5
                    assert Counter(c.code for c in own.graveyards[0]) == (
                        before_hands[0] + Counter([BOOK_OF_MOON]))
                    assert Counter(c.code for c in own.graveyards[1]) == before_hands[1]
                else:
                    assert not book_chained
                    assert jar.position == "faceup"
                    assert own.deck_counts == before_decks
                    assert (Counter(c.code for c in own.hand),
                            Counter(c.code for c in other.hand)) == before_hands
                    assert BOOK_OF_MOON not in {c.code for c in own.graveyards[0]}
                required_scripts = (scripts if book_response else
                                    scripts - {f"official/c{BOOK_OF_MOON}.lua"})
                assert required_scripts <= env.engine.probe.loaded_script_sha256.keys()
                agents = (RandomAgent(52), RandomAgent(53))
                for _ in range(5000):
                    obs = env.step(agents[obs.acting_player].select_action(
                        obs, env.legal_actions()))
                    if env.is_terminal():
                        path = tmp_path / f"jar_book_drain_{book_response}.json"
                        write_trajectory(path, env.trajectory())
                        assert verify_trajectory(read_trajectory(path),
                                                 ExperimentalOcgcoreEngine(root)) == len(
                                                     env.trajectory().decisions)
                        return
                pytest.fail("Morphing Jar / Book / Skill Drain duel did not finish")
    pytest.fail("Morphing Jar / Book / Skill Drain chain did not resolve")
