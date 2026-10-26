"""A face-down Magician of Faith escapes chained Skill Drain at resolution."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

POT_OF_GREED = 55144522
MAGICIAN_OF_FAITH = 31560081
BOOK_OF_MOON = 14087893
SKILL_DRAIN = 82732705


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
@pytest.mark.parametrize("book_response", [False, True])
def test_faith_flip_effect_chained_skill_drain_and_book(tmp_path, book_response):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (
        POT_OF_GREED, MAGICIAN_OF_FAITH, BOOK_OF_MOON, SKILL_DRAIN)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("Faith, Pot, Book, or Skill Drain script not installed")
    faith_deck = tmp_path / "faith.ydk"
    faith_deck.write_text("#main\n" + "\n".join(map(str, (
        POT_OF_GREED, MAGICIAN_OF_FAITH, BOOK_OF_MOON, *VANILLA_DECK[3:])))
        + "\n#extra\n!side\n")
    drain_deck = tmp_path / "drain.ydk"
    drain_deck.write_text("#main\n" + "\n".join(map(str, (
        SKILL_DRAIN, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(faith_deck), str(drain_deck), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {POT_OF_GREED, MAGICIAN_OF_FAITH, BOOK_OF_MOON} <= {
            card.code for card in obs.hand}
        assert SKILL_DRAIN in {
            card.code for card in env.engine.probe.observation(1).hand}
        pot_used = faith_set = book_set = drain_set = faith_flipped = False
        pot_targeted = drain_chained = book_chained = book_targeted = checked = False
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"faith_drain_book_{book_response}.json"
                write_trajectory(path, env.trajectory())
                trajectory = read_trajectory(path)
                assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) == len(
                    trajectory.decisions)
                audit_trajectory_visibility(trajectory)
                loaded = env.engine.probe.loaded_script_sha256.keys()
                assert scripts - ({f"official/c{BOOK_OF_MOON}.lua"}
                                  if not book_response else set()) <= loaded
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not pot_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == POT_OF_GREED), None)
                    pot_used |= action is not None
                elif not faith_set:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == MAGICIAN_OF_FAITH), None)
                    faith_set |= action is not None
                elif not book_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOOK_OF_MOON), None)
                    book_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not drain_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SKILL_DRAIN), None)
                drain_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not faith_flipped:
                action = next((a for a in actions if a.kind == "flip_summon"
                               and a.parameters.get("code") == MAGICIAN_OF_FAITH), None)
                faith_flipped |= action is not None
            if (faith_flipped and not pot_targeted and obs.acting_player == 0
                    and actions[0].kind == "select_card" and obs.chain
                    and obs.chain[-1].card_code == MAGICIAN_OF_FAITH):
                action = next((a for a in actions if a.parameters.get("code") == POT_OF_GREED
                               and a.parameters.get("location") == 16), None)
                assert action is not None
                pot_targeted = True
            if (pot_targeted and not drain_chained and obs.acting_player == 1
                    and [link.card_code for link in obs.chain] == [MAGICIAN_OF_FAITH]):
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SKILL_DRAIN), None)
                assert action is not None
                drain_chained = True
            if (drain_chained and obs.acting_player == 0 and not book_chained
                    and [link.card_code for link in obs.chain] == [
                        MAGICIAN_OF_FAITH, SKILL_DRAIN]):
                book = next((a for a in actions if a.kind == "chain"
                             and a.parameters.get("code") == BOOK_OF_MOON), None)
                assert book is not None
                if book_response:
                    action = book
                    book_chained = True
            if book_chained and not book_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == MAGICIAN_OF_FAITH and a.parameters.get("controller") == 0),
                              None)
                assert action is not None
                book_targeted = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if (drain_chained and not checked and obs.turn == 3
                    and obs.acting_player == 0 and obs.phase == "main1"
                    and not obs.chain and any(a.kind == "end_phase"
                                              for a in env.legal_actions())):
                own = env.engine.probe.observation(0)
                other = env.engine.probe.observation(1)
                faith = next(card for card in own.field if card.zone == "monster"
                             and card.controller == 0)
                assert any(card.code == SKILL_DRAIN and card.position == "faceup"
                           for card in own.field)
                assert own.life_points == (8000, 7000)
                if book_response:
                    assert book_chained and book_targeted
                    assert faith.position == "facedown"
                    assert POT_OF_GREED in {card.code for card in own.hand}
                    assert POT_OF_GREED not in {card.code for card in own.graveyards[0]}
                    assert other.known_opponent_hand_cards == (POT_OF_GREED,)
                    assert [[card.code for card in reveal.cards]
                            for reveal in other.private_reveals] == [[POT_OF_GREED]]
                    hidden = next(card for card in other.field if card.zone == "monster"
                                  and card.controller == 0)
                    assert hidden.code is None
                else:
                    assert faith.position == "faceup"
                    assert POT_OF_GREED in {card.code for card in own.graveyards[0]}
                    assert POT_OF_GREED not in {card.code for card in own.hand}
                    assert other.known_opponent_hand_cards == ()
                    assert not other.private_reveals
                checked = True
    pytest.fail("Faith / Skill Drain / Book chain did not resolve")
