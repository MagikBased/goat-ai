"""Skilled Dark Magician's three-counter effect and empty search."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SKILLED = 504700122
DARK_MAGICIAN = 46986414
UPSTART = 70368879
POT = 55144522


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("has_dark_magician", [True, False])
def test_skilled_tributes_itself_after_three_spells(tmp_path, has_dark_magician):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if any(not (root / "scripts" / script).is_file() for script in
           (f"goat/c{SKILLED}.lua", f"official/c{UPSTART}.lua",
            f"official/c{POT}.lua")):
        pytest.skip("required pinned card scripts not installed")
    cards = list(VANILLA_DECK)
    for index, code in ((0, SKILLED), (1, UPSTART), (2, UPSTART), (13, POT)):
        cards[index] = code
    if has_dark_magician:
        cards[39] = DARK_MAGICIAN
    own = tmp_path / "skilled.ydk"
    own.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    other = tmp_path / "opponent.ydk"
    other.write_text("#main\n" + "\n".join(map(str, VANILLA_DECK))
                     + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(other), 100,
                         ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert [card.code for card in obs.hand].count(UPSTART) == 2
        assert {SKILLED, POT} <= {card.code for card in obs.hand}
        summoned = activated = checked = False
        spells = 0
        checked_at = 0
        checked_observation = None
        checked_opponent = None
        agents = (RandomAgent(718), RandomAgent(719))
        for decision_number in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"skilled_summon_{has_dark_magician}.json"
                write_trajectory(path, env.trajectory())
                replay = read_trajectory(path)
                assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(
                    replay.decisions)
                audit_trajectory_visibility(replay)
                if not has_dark_magician:
                    swapped = cards.copy()
                    swapped[4], swapped[5] = swapped[5], swapped[4]
                    assert swapped != cards
                    reordered = tmp_path / "reordered.ydk"
                    reordered.write_text("#main\n" + "\n".join(map(str, swapped))
                                         + "\n#extra\n!side\n")
                    with GoatEnvironment(str(reordered), str(other), 100,
                                         ExperimentalOcgcoreEngine(root)) as alternate:
                        current = alternate.reset()
                        for record in replay.decisions[:checked_at]:
                            assert current == record.observation
                            assert alternate.legal_actions() == record.legal_actions
                            current = alternate.step(record.selected_action)
                        assert current == checked_observation
                        assert alternate.engine.probe.observation(1) == checked_opponent
                return
            actions = env.legal_actions()
            action = None
            if not checked and obs.turn == 1 and obs.acting_player == 0:
                if not summoned:
                    action = next((choice for choice in actions
                                   if choice.kind == "normal_summon"
                                   and choice.parameters.get("code") == SKILLED), None)
                    summoned |= action is not None
                if action is None and summoned and spells < 3:
                    code = UPSTART if spells < 2 else POT
                    action = next((choice for choice in actions
                                   if choice.kind == "activate"
                                   and choice.parameters.get("code") == code), None)
                    spells += action is not None
                if action is None and spells == 3 and not activated:
                    skilled = next(card for card in obs.field if card.code == SKILLED)
                    if sum(amount for _, amount in skilled.counters) == 3:
                        action = next((choice for choice in actions
                                       if choice.kind == "activate"
                                       and choice.parameters.get("code") == SKILLED), None)
                        activated |= action is not None
            if not checked and activated and actions[0].kind == "select_card":
                assert has_dark_magician
                assert [choice.parameters for choice in actions] == [
                    {"code": DARK_MAGICIAN, "location": 1, "controller": 0}]
                action = actions[0]
            if action is None and not checked:
                action = next((choice for choice in actions if choice.kind in
                               ("place", "select_position", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if activated and not checked and SKILLED in {
                    card.code for card in obs.graveyards[0]} and not obs.chain:
                opponent = env.engine.probe.observation(1)
                assert any(card.code == DARK_MAGICIAN for card in obs.field) == has_dark_magician
                assert all(event.recipient == 1 for event in opponent.private_reveals)
                if has_dark_magician:
                    assert obs.deck_counts[0] == 29
                    assert not opponent.private_reveals
                else:
                    assert obs.deck_counts[0] == 30
                    assert len(opponent.private_reveals) == 2
                    assert not obs.private_reveals
                assert f"goat/c{SKILLED}.lua" in env.engine.probe.loaded_script_sha256
                checked_at = decision_number + 1
                checked_observation = obs
                checked_opponent = opponent
                checked = True
    pytest.fail("Skilled Dark Magician fixture exceeded decision budget")
