import os
from pathlib import Path

import pytest

from goat_ai.actions import Action
from goat_ai.agents import RandomAgent
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, write_trajectory


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_random_agent_completes_native_duel_and_records_visible_trajectory(tmp_path):
    deck = tmp_path / "vanilla.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, VANILLA_DECK)) + "\n")
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])

    def play():
        with GoatEnvironment(str(deck), str(deck), seed=42,
                             engine=RestrictedOcgcoreEngine(root)) as env:
            observation = env.reset()
            assert len(observation.hand) == 6
            with pytest.raises(ValueError, match="illegal"):
                env.step(Action("bad", "pass", 0))
            agent = RandomAgent(42)
            for _ in range(5000):
                action = agent.select_action(observation, env.legal_actions())
                observation = env.step(action)
                if env.is_terminal():
                    return env.trajectory()
            pytest.fail("native duel did not reach terminal within 5000 decisions")

    trajectory = play()
    assert trajectory == play()
    assert trajectory.winner == 1
    assert len(trajectory.decisions) > 100
    assert any(
        any(card.controller != record.observation.viewer and card.position == "facedown"
            for card in record.observation.field)
        and any(action.kind == "select_card" and "code" not in action.parameters
                for action in record.legal_actions)
        for record in trajectory.decisions
    )
    path = tmp_path / "duel.json"
    write_trajectory(path, trajectory)
    assert read_trajectory(path) == trajectory


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_pot_of_greed_resolves_draw_two_with_player_visible_actions():
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck = Path(__file__).resolve().parent.parent / "examples/decks/pot_probe.ydk"
    with GoatEnvironment(str(deck), str(deck), seed=42,
                         engine=RestrictedOcgcoreEngine(root)) as env:
        observation = env.reset()
        agents = (RandomAgent(42), RandomAgent(43))
        pending_draw: tuple[int, int] | None = None
        resolved = False
        for _ in range(5000):
            choices = env.legal_actions()
            action = next((choice for choice in choices if choice.kind == "activate"
                           and choice.parameters.get("code") == 55144522), None)
            if action is None:
                action = agents[observation.acting_player].select_action(observation, choices)
            elif pending_draw is None:
                pending_draw = (observation.acting_player,
                                observation.deck_counts[observation.acting_player])
            observation = env.step(action)
            if pending_draw is not None:
                player, deck_count = pending_draw
                if any(card.code == 55144522 for card in observation.graveyards[player]):
                    assert observation.deck_counts[player] == deck_count - 2
                    resolved = True
                    pending_draw = None
            if env.is_terminal():
                break
        else:
            pytest.fail("Pot fixture duel exceeded 5000 decisions")
        assert resolved
        assert any(record.selected_action.kind == "select_cards"
                   for record in env.trajectory().decisions)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_goat_nobleman_targets_hidden_monster_and_banishes_it():
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck = Path(__file__).resolve().parent.parent / "examples/decks/nobleman_probe.ydk"
    with GoatEnvironment(str(deck), str(deck), seed=42,
                         engine=RestrictedOcgcoreEngine(root)) as env:
        observation = env.reset()
        agents = (RandomAgent(42), RandomAgent(43))
        selected_hidden_target = False
        for _ in range(100):
            choices = env.legal_actions()
            action = next((choice for choice in choices if choice.kind == "activate"
                           and choice.parameters.get("code") == 504700116), None)
            if action is None:
                action = agents[observation.acting_player].select_action(observation, choices)
            if action.kind == "select_card" and "code" not in action.parameters:
                assert any(card.controller != observation.viewer
                           and card.position == "facedown" and card.code is None
                           for card in observation.field)
                selected_hidden_target = True
            observation = env.step(action)
            if selected_hidden_target and observation.banished[1]:
                assert observation.banished[1][0].code == 69140098
                return
        pytest.fail("Nobleman did not banish its hidden target")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_book_of_moon_chains_and_hides_turned_monster(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck = Path(__file__).resolve().parent.parent / "examples/decks/book_probe.ydk"
    with GoatEnvironment(str(deck), str(deck), seed=42,
                         engine=RestrictedOcgcoreEngine(root)) as env:
        observation = env.reset()
        agents = (RandomAgent(42), RandomAgent(43))
        chained = False
        target_selected = False
        saw_public_chain = False
        verified_hidden_target = False
        for _ in range(5000):
            if observation.chain:
                assert observation.chain[0].card_code == 14087893
                if observation.chain[0].controller == 0:
                    saw_public_chain = True
            choices = env.legal_actions()
            action = next((choice for choice in choices if choice.kind == "chain"
                           and choice.parameters.get("code") == 14087893), None)
            if action is None:
                action = agents[observation.acting_player].select_action(observation, choices)
            if action.kind == "chain" and action.parameters.get("code") == 14087893:
                chained = True
            if chained and action.kind == "select_card":
                target_selected = True
            observation = env.step(action)
            if target_selected and not verified_hidden_target and observation.viewer == 1:
                target = next((card for card in observation.field
                               if card.controller == 0 and card.sequence == 2), None)
                if target is not None and target.position == "facedown":
                    assert target.code is None
                    assert target.orientation == "defense"
                    assert saw_public_chain and not observation.chain
                    verified_hidden_target = True
            if env.is_terminal():
                assert verified_hidden_target
                trajectory = env.trajectory()
                assert any(record.observation.chain for record in trajectory.decisions)
                path = tmp_path / "book.json"
                write_trajectory(path, trajectory)
                assert read_trajectory(path) == trajectory
                return
        pytest.fail("Book of Moon fixture duel exceeded 5000 decisions")
