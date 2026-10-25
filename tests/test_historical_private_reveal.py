"""Nobleman deck verification and recipient-scoped native reveal regression."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

NOBLEMAN = 504700116
DEKOICHI = 87621407
MAGICIAN_OF_FAITH = 31560081


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_nobleman_deck_checks_go_only_to_their_recipients(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{DEKOICHI}.lua").is_file():
        pytest.skip("Dekoichi script not installed")
    opponent = tmp_path / "dekoichi.ydk"
    opponent.write_text("#main\n" + "\n".join(map(str,
                        (DEKOICHI, *VANILLA_DECK[1:]))) + "\n")
    with GoatEnvironment("examples/decks/nobleman_probe.ydk", str(opponent), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        set_done = activated = False
        for _ in range(55):
            actions = env.legal_actions()
            action = None
            if observation.turn == 2 and observation.acting_player == 1 and not set_done:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == DEKOICHI), None)
                set_done |= action is not None
            if observation.turn == 3 and observation.acting_player == 0 and not activated:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == NOBLEMAN), None)
                activated |= action is not None
            if action is None and observation.turn in (1, 2):
                action = next((a for a in actions if a.kind == "end_phase"), None)
            if action is None and activated:
                action = next((a for a in actions if a.kind == "select_card"), None)
            if action is None:
                action = next((a for a in actions if a.kind == "pass"), actions[0])
            observation = env.step(action)
            if any(card.code == DEKOICHI for pile in observation.banished for card in pile):
                assert set_done and activated
                probe = env.engine.probe
                own_view = probe.observation(0)
                opposing_view = probe.observation(1)
                assert [(event.recipient, len(event.cards))
                        for event in own_view.private_reveals] == [(0, 34)]
                assert [(event.recipient, len(event.cards))
                        for event in opposing_view.private_reveals] == [(1, 33)]
                assert all(card.controller == 1
                           for event in own_view.private_reveals for card in event.cards)
                assert all(card.controller == 0
                           for event in opposing_view.private_reveals for card in event.cards)
                assert all(card.location == 1 for view in (own_view, opposing_view)
                           for event in view.private_reveals for card in event.cards)
                break
        else:
            pytest.fail("Nobleman did not reach the Flip monster deck checks")
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(5000):
            action = agents[observation.acting_player].select_action(
                observation, env.legal_actions())
            observation = env.step(action)
            if env.is_terminal():
                trajectory = env.trajectory()
                break
        else:
            pytest.fail("Nobleman duel did not reach a terminal state")
    assert {record.observation.viewer for record in trajectory.decisions
            if record.observation.private_reveals} == {0, 1}
    path = tmp_path / "nobleman.json"
    write_trajectory(path, trajectory)
    assert verify_trajectory(read_trajectory(path), ExperimentalOcgcoreEngine(root)) == len(
        trajectory.decisions)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_nobleman_removes_matching_flip_monsters_only_from_decks(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{NOBLEMAN}.lua",
                     f"official/c{MAGICIAN_OF_FAITH}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    attacker = tmp_path / "attacker.ydk"
    defender = tmp_path / "defender.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        NOBLEMAN, *([MAGICIAN_OF_FAITH] * 3), *VANILLA_DECK[4:])))
        + "\n#extra\n!side\n")
    defender.write_text("#main\n" + "\n".join(map(str, (
        *([MAGICIAN_OF_FAITH] * 3), *VANILLA_DECK[3:])))
        + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert sum(c.code == MAGICIAN_OF_FAITH for c in observation.hand) == 1
        assert sum(c.code == MAGICIAN_OF_FAITH
                   for c in env.engine.probe.observation(1).hand) == 1
        set_done = activated = targeted = False
        for _ in range(55):
            actions = env.legal_actions()
            action = None
            if observation.turn == 2 and observation.acting_player == 1 \
                    and not set_done:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == MAGICIAN_OF_FAITH), None)
                set_done |= action is not None
            if observation.turn == 3 and observation.acting_player == 0 \
                    and not activated:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == NOBLEMAN), None)
                activated |= action is not None
            if activated and not targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("controller") == 1
                               and "code" not in a.parameters), None)
                targeted |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind == "end_phase"), None)
            if action is None:
                action = next((a for a in actions if a.kind == "pass"), actions[0])
            observation = env.step(action)
            if targeted and sum(c.code == MAGICIAN_OF_FAITH
                                for c in observation.banished[1]) == 3:
                assert sum(c.code == MAGICIAN_OF_FAITH
                           for c in observation.banished[0]) == 2
                assert sum(c.code == MAGICIAN_OF_FAITH
                           for c in observation.hand) == 1
                assert not any(c.code == MAGICIAN_OF_FAITH
                               for pile in observation.graveyards for c in pile)
                assert observation.deck_counts == (31, 32)
                assert f"goat/c{NOBLEMAN}.lua" in env.engine.probe.loaded_script_sha256
                return
    pytest.fail("Nobleman did not banish all matching Deck copies")
