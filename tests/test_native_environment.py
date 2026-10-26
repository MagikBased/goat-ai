import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from goat_ai.actions import Action
from goat_ai.agents import RandomAgent
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory


def _old_position_actions(record):
    """Pre-v8 recordings used change_position for a Flip Summon."""
    def old(action):
        return replace(action, kind="change_position") if action.kind == "flip_summon" else action

    return replace(record, legal_actions=tuple(old(action) for action in record.legal_actions),
                   selected_action=old(record.selected_action))


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
    assert trajectory.schema_version == 25
    assert trajectory.rules_profile == vars(RestrictedOcgcoreEngine(root).ruleset)
    assert trajectory.deck_sha256 is not None
    assert trajectory.asset_sha256 is not None
    assert "build/libocgcore.so" in trajectory.asset_sha256
    assert "scripts/constant.lua" in trajectory.asset_sha256
    assert len(trajectory.decisions) > 100
    assert trajectory.decisions[0].observation.public_history[:2] == (
        "turn:1", "phase:draw")
    assert any("attack" in record.observation.public_history
               for record in trajectory.decisions)
    target_prompts = [record for record in trajectory.decisions
                      if record.observation.pending_attack is not None]
    assert target_prompts
    for record in target_prompts:
        view = record.observation
        assert view.viewer == view.acting_player == view.pending_attack.controller
        assert any(card.controller == view.viewer and card.zone == "monster"
                   and card.sequence == view.pending_attack.sequence
                   and card.position == "faceup" for card in view.field)
        assert any(action.kind == "select_card" for action in record.legal_actions)
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
    assert verify_trajectory(read_trajectory(path), RestrictedOcgcoreEngine(root)) == len(
        trajectory.decisions)
    older = json.loads(path.read_text())
    older["schema_version"] = 21
    for view in [*(row["observation"] for row in older["decisions"]),
                 older["terminal_observation"]]:
        view.pop("pending_attack")
    older_path = tmp_path / "duel_v21.json"
    older_path.write_text(json.dumps(older))
    assert verify_trajectory(read_trajectory(older_path),
                             RestrictedOcgcoreEngine(root)) == len(trajectory.decisions)
    previous = replace(trajectory, schema_version=4, terminal_observation=None,
                       decisions=tuple(_old_position_actions(replace(record, observation=replace(
                           record.observation, known_opponent_cards=(),
                           known_opponent_field_cards=(), own_main_deck=(),
                           pending_attack=None, turn_player=None)))
                                       for record in trajectory.decisions))
    assert verify_trajectory(previous, RestrictedOcgcoreEngine(root)) == len(
        previous.decisions)
    legacy = replace(previous, schema_version=3,
                     decisions=tuple(replace(record, observation=replace(
                         record.observation, public_history=())) for record in previous.decisions))
    assert verify_trajectory(legacy, RestrictedOcgcoreEngine(root)) == len(legacy.decisions)


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
        known_target_code = None
        for _ in range(5000):
            visible_target = next((card.code for card in observation.field
                                   if card.controller == 0 and card.sequence == 2
                                   and card.position == "faceup"), None)
            if visible_target is not None:
                known_target_code = visible_target
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
                    assert known_target_code in observation.known_opponent_cards
                    assert any(card.controller == 0 and card.zone == "monster"
                               and card.sequence == 2 and card.code == known_target_code
                               for card in observation.known_opponent_field_cards)
                    verified_hidden_target = True
            if env.is_terminal():
                assert verified_hidden_target
                trajectory = env.trajectory()
                assert any(record.observation.chain for record in trajectory.decisions)
                assert any("chain:1:start" in record.observation.public_history
                           for record in trajectory.decisions)
                assert any("chain:end" in record.observation.public_history
                           for record in trajectory.decisions)
                path = tmp_path / "book.json"
                write_trajectory(path, trajectory)
                assert read_trajectory(path) == trajectory
                old_json = json.loads(path.read_text())
                old_json["schema_version"] = 5
                old_json.pop("terminal_observation", None)
                for record in old_json["decisions"]:
                    for action in [*record["legal_actions"], record["selected_action"]]:
                        if action["kind"] == "flip_summon":
                            action["kind"] = "change_position"
                path.write_text(json.dumps(old_json))
                previous = read_trajectory(path)
                assert verify_trajectory(previous, RestrictedOcgcoreEngine(root)) == len(
                    previous.decisions)
                return
        pytest.fail("Book of Moon fixture duel exceeded 5000 decisions")
