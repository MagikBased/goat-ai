import json
from dataclasses import replace

import pytest

from goat_ai.actions import Action
from goat_ai.agents import CombatHeuristicAgent, HeuristicAgent, HumanAgent, RandomAgent
from goat_ai.engine import Decision, RulesProfile, SimulatorUnavailable
from goat_ai.environments import GoatEnvironment
from goat_ai.observations import (
    CardView,
    ChainLinkView,
    DisabledZoneView,
    KnownCardView,
    Observation,
    PrivateRevealView,
    PublicRevealView,
    RevealedCardView,
    TargetSlotView,
)
from goat_ai.replay import (
    DecisionRecord,
    ReplayMismatch,
    Trajectory,
    read_trajectory,
    verify_trajectory,
    write_trajectory,
)


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

    ruleset = RulesProfile()

    def reset(self, deck1: str, deck2: str, seed: int) -> Decision:
        self.seed = seed
        self.steps = 0
        return Decision(view(), (Action("0", "pass", 0), Action("1", "attack", 0)))

    def step(self, action: Action) -> Decision:
        self.steps += 1
        return Decision(view(), (), terminal=True, winner=0)

    def replay_manifest(self) -> dict[str, str]:
        return {"fixture": "sha256-value"}


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
    with pytest.raises(ValueError, match="face-up monster"):
        replace(view(), field=(CardView(1, "monster", "facedown", None, 0,
                                        "defense", 1900, 1000),))


def test_schema_twelve_round_trips_visible_stats_and_legacy_reader_strips_them(tmp_path):
    observation = replace(view(), field=(CardView(
        0, "monster", "faceup", 71413901, 0, "attack", 1900, 1000, ((1, 1),)),))
    action = Action("0", "pass", 0)
    trajectory = Trajectory("goat", ("a", "b"), 7,
                            (DecisionRecord(observation, (action,), action),), 0)
    path = tmp_path / "stats.json"
    write_trajectory(path, trajectory)
    assert read_trajectory(path) == trajectory
    raw = json.loads(path.read_text())
    raw["schema_version"] = 11
    path.write_text(json.dumps(raw))
    old = read_trajectory(path)
    assert old.decisions[0].observation.field[0].attack is None
    assert old.decisions[0].observation.field[0].counters == ()
    with pytest.raises(ValueError, match="facedown"):
        replace(view(), field=(CardView(1, "monster", "facedown", 999),))
    with pytest.raises(ValueError, match="Extra Deck"):
        replace(view(), own_extra_deck=(CardView(1, "extra", "facedown", 999),))
    with pytest.raises(ValueError, match="face-down field slot"):
        replace(view(), known_opponent_field_cards=(KnownCardView(1, "monster", 2, 999),))


def test_publicly_seen_facedown_card_keeps_its_slot(tmp_path):
    observation = replace(
        view(), field=(CardView(1, "monster", "facedown", None, 2, "defense"),),
        known_opponent_cards=(123,),
        known_opponent_field_cards=(KnownCardView(1, "monster", 2, 123),),
    )
    action = Action("0", "pass", 0)
    trajectory = Trajectory("goat", ("a", "b"), 7,
                            (DecisionRecord(observation, (action,), action),), 0)
    path = tmp_path / "known.json"
    write_trajectory(path, trajectory)
    assert read_trajectory(path) == trajectory
    with pytest.raises(ValueError, match="face-down field slot"):
        replace(observation, known_opponent_field_cards=(
            KnownCardView(1, "monster", 2, 123), KnownCardView(1, "monster", 2, 456)))
    raw = json.loads(path.read_text())
    raw["schema_version"] = 5
    raw["decisions"][0]["observation"].pop("known_opponent_field_cards")
    path.write_text(json.dumps(raw))
    restored = read_trajectory(path)
    assert restored.decisions[0].observation.known_opponent_cards == (123,)
    assert restored.decisions[0].observation.known_opponent_field_cards == ()


def test_known_opponent_hand_multiset_round_trips_and_older_schema_reads(tmp_path):
    observation = replace(view(), known_opponent_hand_cards=(123, 456))
    action = Action("0", "pass", 0)
    trajectory = Trajectory("goat", ("a", "b"), 7,
                            (DecisionRecord(observation, (action,), action),), 0)
    path = tmp_path / "known_hand.json"
    write_trajectory(path, trajectory)
    assert read_trajectory(path) == trajectory
    with pytest.raises(ValueError, match="known opponent hand"):
        replace(observation, known_opponent_hand_cards=(123, 456, 789, 999, 1000, 1001))
    raw = json.loads(path.read_text())
    raw["schema_version"] = 16
    raw["decisions"][0]["observation"].pop("known_opponent_hand_cards")
    path.write_text(json.dumps(raw))
    assert read_trajectory(path).decisions[0].observation.known_opponent_hand_cards == ()


def test_public_deck_reveal_round_trip_and_legacy_reader(tmp_path):
    observation = replace(view(), public_reveals=(
        PublicRevealView(3, 0, "deck_top", (123, 456)),
        PublicRevealView(3, 1, "deck_top", (789,)),
    ))
    action = Action("0", "pass", 0)
    path = tmp_path / "reveal.json"
    write_trajectory(path, Trajectory("goat", ("a", "b"), 7,
                                      (DecisionRecord(observation, (action,), action),), 0))
    assert read_trajectory(path).decisions[0].observation.public_reveals == observation.public_reveals
    raw = json.loads(path.read_text())
    raw["schema_version"] = 7
    raw["decisions"][0]["observation"].pop("public_reveals")
    path.write_text(json.dumps(raw))
    assert read_trajectory(path).decisions[0].observation.public_reveals == ()


def test_disabled_zone_round_trip_and_legacy_reader(tmp_path):
    observation = replace(view(), disabled_zones=(DisabledZoneView(1, "monster", 2),))
    action = Action("0", "pass", 0)
    path = tmp_path / "disabled.json"
    write_trajectory(path, Trajectory("goat", ("a", "b"), 7,
                                      (DecisionRecord(observation, (action,), action),), 0))
    assert read_trajectory(path).decisions[0].observation.disabled_zones == observation.disabled_zones
    raw = json.loads(path.read_text())
    raw["schema_version"] = 8
    raw["decisions"][0]["observation"].pop("disabled_zones")
    path.write_text(json.dumps(raw))
    assert read_trajectory(path).decisions[0].observation.disabled_zones == ()


def test_private_reveal_round_trip_and_cross_player_rejection(tmp_path):
    reveal = PrivateRevealView(3, 0, (RevealedCardView(456, 1, 1),))
    observation = replace(view(), private_reveals=(reveal,))
    action = Action("0", "pass", 0)
    path = tmp_path / "private.json"
    write_trajectory(path, Trajectory("goat", ("a", "b"), 7,
                                      (DecisionRecord(observation, (action,), action),), 0))
    assert read_trajectory(path).decisions[0].observation.private_reveals == (reveal,)
    with pytest.raises(ValueError, match="observation viewer"):
        replace(observation, private_reveals=(replace(reveal, recipient=1),))
    raw = json.loads(path.read_text())
    raw["schema_version"] = 9
    raw["decisions"][0]["observation"].pop("private_reveals")
    path.write_text(json.dumps(raw))
    assert read_trajectory(path).decisions[0].observation.private_reveals == ()


def test_own_deck_composition_round_trip_without_deck_order(tmp_path):
    observation = replace(view(), own_main_deck=(10, 10, 20))
    with pytest.raises(ValueError, match="unordered card multiset"):
        replace(view(), own_main_deck=(20, 10, 10))
    action = Action("0", "pass", 0)
    path = tmp_path / "own_deck.json"
    write_trajectory(path, Trajectory("goat", ("a", "b"), 7,
                                      (DecisionRecord(observation, (action,), action),), 0))
    assert read_trajectory(path).decisions[0].observation.own_main_deck == (10, 10, 20)
    raw = json.loads(path.read_text())
    raw["schema_version"] = 10
    raw["decisions"][0]["observation"].pop("own_main_deck")
    path.write_text(json.dumps(raw))
    assert read_trajectory(path).decisions[0].observation.own_main_deck == ()


def test_agents_use_same_contract():
    actions = (Action("0", "pass", 0), Action("1", "attack", 0))
    assert RandomAgent(5).select_action(view(), actions) in actions
    assert HeuristicAgent().select_action(view(), actions) == actions[1]
    assert HumanAgent(input_fn=lambda _: "1", output_fn=lambda _: None).select_action(view(), actions) == actions[1]


def test_flip_type_metadata_changes_generic_summon_preference():
    flip_code, ordinary_code = 87621407, 49881766
    flip_actions = (Action("0", "normal_summon", 0, {"code": flip_code}),
                    Action("1", "set_monster", 0, {"code": flip_code}))
    ordinary_actions = (Action("0", "normal_summon", 0, {"code": ordinary_code}),
                        Action("1", "set_monster", 0, {"code": ordinary_code}))
    assert HeuristicAgent().select_action(view(), flip_actions) == flip_actions[0]
    agent = HeuristicAgent(flip_monster_codes={flip_code})
    assert agent.select_action(view(), flip_actions) == flip_actions[1]
    assert agent.select_action(view(), ordinary_actions) == ordinary_actions[0]


def test_combat_heuristic_uses_only_visible_battle_stats():
    weak = Action("0", "attack", 0, {"sequence": 0})
    strong = Action("1", "attack", 0, {"sequence": 1})
    main2 = Action("2", "main2", 0)
    field = (
        CardView(0, "monster", "faceup", 1, 0, "attack", 1200, 800),
        CardView(0, "monster", "faceup", 2, 1, "attack", 1900, 1200),
        CardView(1, "monster", "faceup", 3, 0, "attack", 1700, 1000),
    )
    agent = CombatHeuristicAgent()
    battle = replace(view(), phase="battle_start", field=field)
    assert agent.select_action(battle, (weak, strong, main2)) == strong
    target = Action("3", "select_card", 0, {"controller": 1, "location": 4,
                                             "sequence": 0, "code": 3})
    bigger = Action("4", "select_card", 0, {"controller": 1, "location": 4,
                                             "sequence": 2, "code": 4})
    target_view = replace(battle, phase="battle_step", field=field + (
        CardView(1, "monster", "faceup", 4, 2, "attack", 2100, 900),))
    assert agent.select_action(target_view, (bigger, target)) == target
    current_target = replace(target_view, phase="battle_start",
                             pending_attack=TargetSlotView(0, "monster", 1))
    assert CombatHeuristicAgent().select_action(current_target, (bigger, target)) == target
    hidden_target = Action("5", "select_card", 0, {"controller": 1, "location": 4,
                                                    "sequence": 3})
    mixed = replace(battle, phase="battle_step", field=field[:2] + (
        CardView(1, "monster", "faceup", 3, 0, "attack", 2200, 1000),
        CardView(1, "monster", "facedown", None, 3, "defense")))
    assert agent.select_action(mixed, (target, hidden_target)) == target
    assert agent.select_action(mixed, (weak, strong, main2)) == strong
    assert agent.select_action(mixed, (target, hidden_target)) == hidden_target
    blocked = replace(battle, field=field[:2] + (
        CardView(1, "monster", "faceup", 3, 0, "attack", 2200, 1000),))
    assert agent.select_action(blocked, (weak, strong, main2)) == main2
    hidden = replace(battle, field=field[:2] + (
        CardView(1, "monster", "facedown", None, 0, "defense"),))
    assert agent.select_action(hidden, (weak, strong, main2)) == strong


def test_trajectory_round_trip_and_legality(tmp_path):
    action = Action("1", "attack", 0, {"target": "direct"})
    observation = replace(view(), chain=(ChainLinkView(1, 123, 0, 4, 2),),
                          public_history=("turn:1", "phase:main1"),
                          field=(CardView(1, "monster", "facedown", None, 2, "defense"),),
                          own_extra_deck=(CardView(0, "extra", "facedown", 504700102),))
    record = DecisionRecord(observation, (action,), action)
    trajectory = Trajectory("tcg-goat-2005-08-17", ("a", "b"), 42, (record,), 0)
    path = tmp_path / "game.json"
    write_trajectory(path, trajectory)
    assert read_trajectory(path) == trajectory
    assert read_trajectory(path).decisions[0].observation.chain[0].card_code == 123
    assert read_trajectory(path).decisions[0].observation.own_extra_deck[0].code == 504700102
    assert "999" not in path.read_text()
    with pytest.raises(ValueError, match="legal"):
        DecisionRecord(view(), (), action)


def test_replay_verifier_detects_changed_decision_and_outcome():
    action = Action("0", "pass", 0)
    legal = (action, Action("1", "attack", 0))
    trajectory = Trajectory(RulesProfile().name, ("a", "b"), 42,
                            (DecisionRecord(view(), legal, action),), 0)
    assert verify_trajectory(trajectory, ContractEngine()) == 1
    with pytest.raises(ReplayMismatch, match="ruleset"):
        verify_trajectory(replace(trajectory, ruleset="other"), ContractEngine())
    with pytest.raises(ReplayMismatch, match="observation"):
        changed = replace(trajectory.decisions[0],
                          observation=replace(view(), life_points=(7000, 8000)))
        verify_trajectory(replace(trajectory, decisions=(changed,)), ContractEngine())
    with pytest.raises(ReplayMismatch, match="legal actions"):
        changed = replace(trajectory.decisions[0], legal_actions=(action,))
        verify_trajectory(replace(trajectory, decisions=(changed,)), ContractEngine())
    with pytest.raises(ReplayMismatch, match="winner"):
        verify_trajectory(replace(trajectory, winner=1), ContractEngine())
    with pytest.raises(ReplayMismatch, match="rules profile"):
        verify_trajectory(replace(trajectory, rules_profile={"side_deck_policy": "community"}),
                          ContractEngine())
    with pytest.raises(ReplayMismatch, match="native assets"):
        verify_trajectory(replace(trajectory, asset_sha256={"fixture": "wrong"}),
                          ContractEngine())


def test_schema_twenty_two_terminal_observation_round_trip_and_verification(tmp_path):
    with GoatEnvironment("a", "b", seed=42, engine=ContractEngine()) as env:
        env.reset()
        final = env.step(env.legal_actions()[0])
        assert env.is_terminal()
        trajectory = env.trajectory()
    assert trajectory.schema_version == 22
    assert trajectory.terminal_observation == final
    path = tmp_path / "terminal.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    assert verify_trajectory(loaded, ContractEngine()) == 1
    with pytest.raises(ReplayMismatch, match="requires a terminal observation"):
        verify_trajectory(replace(loaded, terminal_observation=None), ContractEngine())
    changed = replace(loaded, terminal_observation=replace(
        final, life_points=(100, 200)))
    with pytest.raises(ReplayMismatch, match="terminal observation"):
        verify_trajectory(changed, ContractEngine())
    raw = json.loads(path.read_text())
    raw.pop("terminal_observation")
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="requires a terminal observation"):
        read_trajectory(path)


def test_old_position_action_replays_as_flip_summon():
    class FlipEngine(ContractEngine):
        def reset(self, deck1, deck2, seed):
            return Decision(view(), (Action("0", "flip_summon", 0),))

        def step(self, action):
            assert action.kind == "flip_summon"
            return Decision(view(), (), terminal=True, winner=0)

    old_action = Action("0", "change_position", 0)
    old = Trajectory(RulesProfile().name, ("a", "b"), 42,
                     (DecisionRecord(view(), (old_action,), old_action),), 0,
                     schema_version=7)
    assert verify_trajectory(old, FlipEngine()) == 1
    with pytest.raises(ReplayMismatch, match="legal actions"):
        verify_trajectory(replace(old, schema_version=8), FlipEngine())


def test_replay_verifier_detects_changed_deck_contents(tmp_path):
    paths = (tmp_path / "a.ydk", tmp_path / "b.ydk")
    for path in paths:
        path.write_text("#main\n123\n")
    action = Action("0", "pass", 0)
    from goat_ai.replay.fingerprint import sha256_file

    trajectory = Trajectory(
        RulesProfile().name, tuple(str(path) for path in paths), 42,
        (DecisionRecord(view(), (action, Action("1", "attack", 0)), action),), 0,
        deck_sha256=tuple(sha256_file(path) for path in paths),
    )
    assert verify_trajectory(trajectory, ContractEngine()) == 1
    paths[1].write_text("#main\n456\n")
    with pytest.raises(ReplayMismatch, match="deck contents"):
        verify_trajectory(trajectory, ContractEngine())


def test_schema_one_trajectory_remains_readable(tmp_path):
    action = Action("0", "pass", 0)
    trajectory = Trajectory("goat", ("a", "b"), 7,
                            (DecisionRecord(view(), (action,), action),), 0)
    path = tmp_path / "old.json"
    write_trajectory(path, trajectory)
    raw = json.loads(path.read_text())
    raw["schema_version"] = 1
    raw["decisions"][0]["observation"]["hand"][0].pop("orientation")
    raw["decisions"][0]["observation"]["field"][0].pop("orientation")
    raw["decisions"][0]["observation"].pop("own_extra_deck")
    path.write_text(json.dumps(raw))
    restored = read_trajectory(path)
    assert restored.schema_version == 1
    assert restored.decisions[0].observation.field[0].orientation is None


def test_schema_two_trajectory_remains_readable(tmp_path):
    action = Action("0", "pass", 0)
    observation = replace(view(), chain=(ChainLinkView(1, 123, 0, 4, 2),))
    trajectory = Trajectory("goat", ("a", "b"), 7,
                            (DecisionRecord(observation, (action,), action),), 0)
    path = tmp_path / "old_v2.json"
    write_trajectory(path, trajectory)
    raw = json.loads(path.read_text())
    raw["schema_version"] = 2
    raw["decisions"][0]["observation"].pop("own_extra_deck")
    for key in ("rules_profile", "deck_sha256", "asset_sha256"):
        raw.pop(key)
    path.write_text(json.dumps(raw))
    restored = read_trajectory(path)
    assert restored.schema_version == 2
    assert restored.rules_profile is None
    assert restored.decisions[0].observation.chain == observation.chain


def test_decision_rejects_wrong_actor_and_empty_nonterminal():
    with pytest.raises(ValueError, match="actor"):
        Decision(view(), (Action("0", "pass", 1),))
    with pytest.raises(ValueError, match="legal actions"):
        Decision(view(), ())

