from dataclasses import replace

import pytest

from goat_ai.actions import Action
from goat_ai.agents import HeuristicAgent, HumanAgent, RandomAgent
from goat_ai.engine import Decision, SimulatorUnavailable
from goat_ai.environments import GoatEnvironment
from goat_ai.observations import CardView, Observation
from goat_ai.replay import DecisionRecord, Trajectory, read_trajectory, write_trajectory


def view(hidden_code: int = 1) -> Observation:
    # hidden_code intentionally does not enter the player-visible schema.
    _ = hidden_code
    return Observation(
        viewer=0, acting_player=0, turn=1, phase="main1", life_points=(8000, 8000),
        hand=(CardView(0, "hand", "hidden", 123),),
        field=(CardView(1, "monster", "facedown", None),),
        graveyards=((), ()), banished=((), ()), opponent_hand_count=5,
        deck_counts=(35, 35), extra_deck_counts=(0, 0),
    )


class ContractEngine:
    """Test double for boundary behavior only; it does not model Yu-Gi-Oh!."""

    def reset(self, deck1: str, deck2: str, seed: int) -> Decision:
        self.seed = seed
        self.steps = 0
        return Decision(view(), (Action("0", "pass", 0), Action("1", "attack", 0)))

    def step(self, action: Action) -> Decision:
        self.steps += 1
        return Decision(view(), (), terminal=True, winner=0)


def test_default_engine_fails_explicitly():
    with pytest.raises(SimulatorUnavailable, match="unfinished"):
        GoatEnvironment("a.ydk", "b.ydk").reset()


def test_environment_contract_and_illegal_action():
    engine = ContractEngine()
    env = GoatEnvironment("a.ydk", "b.ydk", engine=engine)
    env.reset(seed=42)
    assert engine.seed == 42
    assert len(env.legal_actions()) == 2
    with pytest.raises(ValueError, match="illegal"):
        env.step(Action("bad", "attack", 0))
    assert engine.steps == 0
    env.step(env.legal_actions()[0])
    assert env.is_terminal() and env.result() == 0
    with pytest.raises(RuntimeError, match="terminal"):
        env.step(Action("0", "pass", 0))


def test_visible_schema_excludes_hidden_opponent_cards():
    assert view(100) == view(200)
    assert view().field[0].code is None
    assert all(card.controller == 0 for card in view().hand)
    with pytest.raises(ValueError, match="viewer"):
        replace(view(), hand=(CardView(1, "hand", "hidden", 999),))
    with pytest.raises(ValueError, match="facedown"):
        replace(view(), field=(CardView(1, "monster", "facedown", 999),))


def test_agents_use_same_contract():
    actions = (Action("0", "pass", 0), Action("1", "attack", 0))
    assert RandomAgent(5).select_action(view(), actions) in actions
    assert HeuristicAgent().select_action(view(), actions) == actions[1]
    assert HumanAgent(input_fn=lambda _: "1", output_fn=lambda _: None).select_action(view(), actions) == actions[1]


def test_trajectory_round_trip_and_legality(tmp_path):
    action = Action("1", "attack", 0, {"target": "direct"})
    record = DecisionRecord(view(), (action,), action)
    trajectory = Trajectory("tcg-goat-2005-08-17", ("a", "b"), 42, (record,), 0)
    path = tmp_path / "game.json"
    write_trajectory(path, trajectory)
    assert read_trajectory(path) == trajectory
    assert "999" not in path.read_text()
    with pytest.raises(ValueError, match="legal"):
        DecisionRecord(view(), (), action)


def test_decision_rejects_wrong_actor_and_empty_nonterminal():
    with pytest.raises(ValueError, match="actor"):
        Decision(view(), (Action("0", "pass", 1),))
    with pytest.raises(ValueError, match="legal actions"):
        Decision(view(), ())

