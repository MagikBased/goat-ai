"""Contract checks for the optional PyTorch legal-action policy."""

from dataclasses import replace
from functools import partial

import pytest

torch = pytest.importorskip("torch")

from goat_ai.actions import Action
from goat_ai.observations import CardView, DisabledZoneView, KnownCardView, Observation
from goat_ai.replay import DecisionRecord, Trajectory, demonstrator_records
from goat_ai.training import (
    CardVocabulary,
    LegalActionPolicy,
    PolicyAgent,
    encode_decision,
    fit_behavioral_clone,
    load_policy_agent,
)
from goat_ai.training.policy import ACTION_KINDS
from goat_ai.training.self_play import (
    episode_schedule,
    policy_gradient_update,
    sample_legal_action,
)
from scripts.evaluate_policy import make_policy_agent, validate_heldout_seeds


def view() -> Observation:
    return Observation(
        viewer=0, acting_player=0, turn=3, phase="main1", life_points=(8000, 6500),
        hand=(CardView(0, "hand", "hidden", 10, 0),),
        field=(CardView(1, "monster", "facedown", None, 0, "defense"),),
        graveyards=((), ()), banished=((), ()), opponent_hand_count=4,
        deck_counts=(34, 33), extra_deck_counts=(0, 0),
    )


def actions() -> tuple[Action, ...]:
    return (Action("native-0", "normal_summon", 0, {"code": 10, "location": 2}),
            Action("native-1", "set_monster", 0, {"code": 10, "location": 2}),
            Action("native-2", "end_phase", 0))


def test_variable_legal_actions_and_permutation_equivariance():
    torch.manual_seed(5)
    vocabulary = CardVocabulary((10, 20))
    policy = LegalActionPolicy(vocabulary.size, width=16)
    first = policy(encode_decision(view(), actions(), vocabulary))
    reversed_actions = tuple(reversed(actions()))
    second = policy(encode_decision(view(), reversed_actions, vocabulary))
    assert first.shape == (3,)
    assert torch.allclose(first, second.flip(0))
    assert policy(encode_decision(view(), actions()[:1], vocabulary)).shape == (1,)
    assert PolicyAgent(policy, vocabulary).select_action(view(), actions()) in actions()


def test_feature_version_eight_uses_visible_monster_stats_and_counters():
    vocabulary = CardVocabulary((10, 20))
    visible = replace(view(), field=(CardView(
        0, "monster", "faceup", 20, 0, "attack", 1900, 1000, ((1, 1),)),))
    spent = replace(visible, field=(replace(visible.field[0], attack=1600, counters=()),))
    before = encode_decision(visible, actions(), vocabulary, feature_version=8)
    after = encode_decision(spent, actions(), vocabulary, feature_version=8)
    assert before.state_card_numbers.shape == (2, 5)
    assert before.state_card_numbers[1, 0].item() == pytest.approx(1900 / 8000)
    assert before.state_card_numbers[1, 3].item() == pytest.approx(0.1)
    assert after.state_card_numbers[1, 0].item() == pytest.approx(1600 / 8000)
    assert after.state_card_numbers[1, 3].item() == 0
    assert not torch.equal(before.state_card_numbers, after.state_card_numbers)
    assert LegalActionPolicy(vocabulary.size, width=16, feature_version=8)(before).shape == (3,)
    legacy_before = encode_decision(visible, actions(), vocabulary, feature_version=7)
    legacy_after = encode_decision(spent, actions(), vocabulary, feature_version=7)
    assert torch.equal(legacy_before.state_card_numbers, legacy_after.state_card_numbers)


def test_action_ids_are_not_features_but_public_card_and_controller_are():
    vocabulary = CardVocabulary((10, 20))
    original = encode_decision(view(), actions(), vocabulary)
    renamed = tuple(Action(f"different-{index}", action.kind, action.actor,
                           action.parameters) for index, action in enumerate(actions()))
    assert torch.equal(original.action_kinds,
                       encode_decision(view(), renamed, vocabulary).action_kinds)
    assert torch.equal(original.action_numbers,
                       encode_decision(view(), renamed, vocabulary).action_numbers)
    choices = (Action("a", "select_card", 0, {"code": 20, "controller": 0}),
               Action("b", "select_card", 0, {"code": 20, "controller": 1}))
    features = encode_decision(view(), choices, vocabulary)
    assert features.action_numbers[0, 0] != features.action_numbers[1, 0]
    assert vocabulary.index(None) == 0
    assert vocabulary.index(9999) == 1
    with pytest.raises(ValueError, match="actor"):
        encode_decision(view(), (Action("wrong", "pass", 1),), vocabulary)


def test_announced_attribute_and_number_are_distinct_policy_features():
    vocabulary = CardVocabulary((10, 20))
    choices = (
        Action("a", "announce_attribute", 0, {"attribute": 1}),
        Action("b", "announce_attribute", 0, {"attribute": 32}),
        Action("c", "announce_number", 0, {"number": 1000}),
        Action("d", "announce_number", 0, {"number": 2000}),
        Action("e", "announce_card", 0, {"code": 10}),
    )
    features = encode_decision(view(), choices, vocabulary)
    assert features.action_numbers.shape == (5, 11)
    assert features.action_kinds[0] == features.action_kinds[1]
    assert features.action_kinds[0] != features.action_kinds[2]
    assert features.action_kinds[4] not in features.action_kinds[:4]
    assert features.action_cards[4] == vocabulary.index(10)
    assert not torch.equal(features.action_numbers[0], features.action_numbers[1])
    assert not torch.equal(features.action_numbers[2], features.action_numbers[3])
    assert LegalActionPolicy(vocabulary.size, width=16)(features).shape == (5,)
    legacy = encode_decision(view(), choices, vocabulary, feature_version=5)
    assert legacy.action_numbers.shape == (5, 8)
    assert legacy.action_kinds.tolist() == [0, 0, 0, 0, 0]


def test_version_seven_distinguishes_card_sort_order():
    vocabulary = CardVocabulary((10, 20))
    first = {"code": 10, "controller": 0, "location": 1, "sequence": 32}
    second = {"code": 20, "controller": 0, "location": 1, "sequence": 33}
    choices = (Action("a", "sort_cards", 0, {"cards": [first, second]}),
               Action("b", "sort_cards", 0, {"cards": [second, first]}))
    features = encode_decision(view(), choices, vocabulary)
    assert features.action_target_context.shape == (2, 2, 6)
    assert features.action_target_context[0, 0, -1] == 0
    assert features.action_target_context[0, 1, -1] == 1
    assert features.action_kinds[0] == features.action_kinds[1] != 0
    torch.manual_seed(24)
    model = LegalActionPolicy(vocabulary.size, width=16)
    scores = model(features)
    assert scores.shape == (2,)
    assert scores[0] != scores[1]
    previous = encode_decision(view(), choices, vocabulary, feature_version=6)
    assert previous.action_target_context.shape == (2, 2, 5)
    assert previous.action_kinds.tolist() == [0, 0]


def test_multi_target_features_preserve_visible_slots_without_hidden_codes():
    vocabulary = CardVocabulary((10, 20))
    choices = (
        Action("a", "select_cards", 0, {"cards": [
            {"controller": 1, "location": 8, "sequence": 0},
            {"controller": 1, "location": 8, "sequence": 3}]}),
        Action("b", "select_cards", 0, {"cards": [
            {"controller": 1, "location": 8, "sequence": 1},
            {"controller": 1, "location": 8, "sequence": 2}]}),
    )
    features = encode_decision(view(), choices, vocabulary)
    assert torch.equal(features.action_targets[0], features.action_targets[1])
    assert not torch.equal(features.action_target_context[0],
                           features.action_target_context[1])
    torch.manual_seed(19)
    model = LegalActionPolicy(vocabulary.size, width=16)
    scores = model(features)
    assert scores[0] != scores[1]
    reversed_cards = Action("renamed", "select_cards", 0,
                            {"cards": list(reversed(choices[0].parameters["cards"]))})
    reversed_score = model(encode_decision(view(), (reversed_cards,), vocabulary))
    assert torch.allclose(scores[:1], reversed_score)


def test_feature_version_three_uses_only_publicly_known_facedown_id():
    vocabulary = CardVocabulary((10, 20))
    observation = replace(
        view(),
        field=(CardView(1, "monster", "facedown", None, 0, "defense"),
               CardView(1, "monster", "facedown", None, 1, "defense")),
        known_opponent_field_cards=(KnownCardView(1, "monster", 0, 20),),
    )
    choices = (
        Action("known", "select_card", 0,
               {"controller": 1, "location": 4, "sequence": 0}),
        Action("unknown", "select_card", 0,
               {"controller": 1, "location": 4, "sequence": 1}),
        Action("multi", "select_cards", 0, {"cards": [
            {"controller": 1, "location": 4, "sequence": 0},
            {"controller": 1, "location": 4, "sequence": 1}]}),
    )
    current = encode_decision(observation, choices, vocabulary, feature_version=3)
    assert current.state_cards[1, 0].item() == vocabulary.index(20)
    assert current.state_cards[2, 0].item() == 0
    assert current.action_cards.tolist() == [vocabulary.index(20), 0, 0]
    assert current.action_targets[2].tolist() == [vocabulary.index(20), 0]
    legacy = encode_decision(observation, choices, vocabulary, feature_version=2)
    assert legacy.state_cards[1:3, 0].tolist() == [0, 0]
    assert legacy.action_cards.tolist() == [0, 0, 0]
    assert legacy.action_targets[2].tolist() == [0, 0]


def test_feature_version_four_represents_zone_choices_and_disabled_slots():
    vocabulary = CardVocabulary((10, 20))
    zones = [
        {"controller": 0, "location": 4, "sequence": 0},
        {"controller": 1, "location": 4, "sequence": 2},
    ]
    choices = (
        Action("a", "disable_zones", 0, {"zones": zones}),
        Action("b", "disable_zones", 0, {"zones": [zones[0],
               {"controller": 1, "location": 4, "sequence": 3}]}),
    )
    observation = replace(view(), disabled_zones=(DisabledZoneView(0, "monster", 1),))
    features = encode_decision(observation, choices, vocabulary, feature_version=4)
    assert features.state_numbers.shape == (42,)
    assert features.state_numbers[11].item() == 1  # own Monster Zone 1
    assert features.action_kinds.tolist() == [len(ACTION_KINDS) + 2] * 2
    assert not torch.equal(features.action_target_context[0],
                           features.action_target_context[1])
    torch.manual_seed(19)
    model = LegalActionPolicy(vocabulary.size, width=16, feature_version=4)
    scores = model(features)
    assert scores[0] != scores[1]
    reversed_zones = Action("c", "disable_zones", 0, {"zones": list(reversed(zones))})
    reversed_score = model(encode_decision(observation, (reversed_zones,), vocabulary,
                                           feature_version=4))
    assert torch.allclose(scores[:1], reversed_score)
    clear = encode_decision(view(), choices, vocabulary, feature_version=4)
    assert not torch.equal(features.state_numbers, clear.state_numbers)


def test_feature_version_five_sees_own_deck_composition_without_order():
    vocabulary = CardVocabulary((10, 20))
    first = replace(view(), own_main_deck=(10, 10, 20))
    second = replace(view(), own_main_deck=(10, 20, 20))
    first_features = encode_decision(first, actions(), vocabulary, feature_version=5)
    second_features = encode_decision(second, actions(), vocabulary, feature_version=5)
    assert first_features.deck_cards.tolist() == [2, 2, 3]
    assert second_features.deck_cards.tolist() == [2, 3, 3]
    assert torch.equal(first_features.state_cards, second_features.state_cards)
    torch.manual_seed(19)
    model = LegalActionPolicy(vocabulary.size, width=16, feature_version=5)
    assert not torch.allclose(model(first_features), model(second_features))
    legacy = encode_decision(first, actions(), vocabulary, feature_version=4)
    assert legacy.deck_cards.tolist() == [0]


def test_supervised_update_reduces_loss_for_visible_decision():
    torch.manual_seed(6)
    torch.set_num_threads(1)
    vocabulary = CardVocabulary((10, 20))
    policy = LegalActionPolicy(vocabulary.size, width=16)
    features = encode_decision(view(), actions(), vocabulary)
    optimizer = torch.optim.Adam(policy.parameters(), lr=0.03)
    target = torch.tensor([1])
    first = torch.nn.functional.cross_entropy(policy(features).unsqueeze(0), target)
    for _ in range(20):
        optimizer.zero_grad()
        loss = torch.nn.functional.cross_entropy(policy(features).unsqueeze(0), target)
        loss.backward()
        optimizer.step()
    last = torch.nn.functional.cross_entropy(policy(features).unsqueeze(0), target)
    assert last.item() < first.item() * 0.1


def test_behavioral_clone_records_and_checkpoint_round_trip(tmp_path):
    torch.manual_seed(7)
    vocabulary = CardVocabulary((10, 20))
    policy = LegalActionPolicy(vocabulary.size, width=16)
    record = DecisionRecord(view(), actions(), actions()[1])
    losses = fit_behavioral_clone(policy, vocabulary, [record], epochs=8,
                                  learning_rate=0.03, seed=7)
    assert losses[-1] < losses[0]
    checkpoint = tmp_path / "policy.pt"
    torch.save({"schema_version": 1, "model_state": policy.state_dict(),
                "vocabulary_codes": vocabulary.codes, "width": 16,
                "feature_version": policy.feature_version}, checkpoint)
    restored = load_policy_agent(checkpoint)
    assert restored.select_action(view(), actions()) == actions()[1]
    with pytest.raises(ValueError, match="training needs records"):
        fit_behavioral_clone(policy, vocabulary, [])


def test_legacy_policy_checkpoint_loads_with_original_feature_encoder(tmp_path):
    vocabulary = CardVocabulary((10, 20))
    legacy = LegalActionPolicy(vocabulary.size, width=16, feature_version=1)
    checkpoint = tmp_path / "legacy.pt"
    torch.save({"schema_version": 1, "model_state": legacy.state_dict(),
                "vocabulary_codes": vocabulary.codes, "width": 16}, checkpoint)
    restored = load_policy_agent(checkpoint)
    assert restored.model.feature_version == 1
    legacy_choices = (Action("multi", "select_cards", 0, {"cards": [
        {"controller": 1, "location": 8, "sequence": 0},
        {"controller": 0, "location": 4, "sequence": 1, "code": 20}]}),)
    features = encode_decision(view(), legacy_choices, vocabulary, feature_version=1)
    assert torch.allclose(legacy(features), restored.model(features))
    assert restored.select_action(view(), actions()) in actions()


def test_version_two_checkpoint_ignores_new_known_card_memory(tmp_path):
    vocabulary = CardVocabulary((10, 20))
    model = LegalActionPolicy(vocabulary.size, width=16, feature_version=2)
    checkpoint = tmp_path / "v2.pt"
    torch.save({"schema_version": 1, "model_state": model.state_dict(),
                "vocabulary_codes": vocabulary.codes, "width": 16,
                "feature_version": 2}, checkpoint)
    restored = load_policy_agent(checkpoint)
    assert restored.model.feature_version == 2
    observation = replace(view(), known_opponent_field_cards=(
        KnownCardView(1, "monster", 0, 20),))
    without_memory = replace(observation, known_opponent_field_cards=())
    before = encode_decision(observation, actions(), vocabulary, feature_version=2)
    after = encode_decision(without_memory, actions(), vocabulary, feature_version=2)
    assert torch.equal(restored.model(before), restored.model(after))
    assert restored.select_action(observation, actions()) in actions()


def test_evaluation_rejects_training_seed_overlap():
    checkpoint = {"training_games": [{"seed": 42}]}
    validate_heldout_seeds(checkpoint, [43, 44])
    with pytest.raises(ValueError, match="overlap"):
        validate_heldout_seeds(checkpoint, [42, 43])
    with pytest.raises(ValueError, match="provenance"):
        validate_heldout_seeds({}, [43])


def test_checkpoint_opponent_uses_common_agent_contract(tmp_path):
    vocabulary = CardVocabulary((10, 20))
    model = LegalActionPolicy(vocabulary.size, width=16)
    path = tmp_path / "opponent.pt"
    torch.save({"schema_version": 1, "model_state": model.state_dict(),
                "vocabulary_codes": vocabulary.codes, "width": 16,
                "feature_version": model.feature_version}, path)
    factory = partial(make_policy_agent, checkpoint=str(path))
    assert factory(42).select_action(view(), actions()) in actions()


def test_terminal_reward_moves_selected_action_probability():
    vocabulary = CardVocabulary((10, 20))
    record = DecisionRecord(view(), actions(), actions()[1])
    features = encode_decision(view(), actions(), vocabulary)
    for reward, direction in ((1.0, 1), (-1.0, -1)):
        torch.manual_seed(8)
        model = LegalActionPolicy(vocabulary.size, width=16)
        optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
        before = torch.softmax(model(features), 0)[1].item()
        policy_gradient_update(model, vocabulary, [record], reward, 0.0, optimizer)
        after = torch.softmax(model(features), 0)[1].item()
        assert (after - before) * direction > 0
    generator = torch.Generator().manual_seed(9)
    assert sample_legal_action(model, vocabulary, view(), actions(), generator) in actions()


def test_self_play_schedule_covers_each_deck_in_both_seats():
    matchups = (("goat", "chaos"), ("chaos", "goat"))
    schedule = episode_schedule(matchups, (100, 101, 102, 103))
    assert schedule == (
        (100, ("goat", "chaos"), 0),
        (101, ("chaos", "goat"), 1),
        (102, ("chaos", "goat"), 0),
        (103, ("goat", "chaos"), 1),
    )
    assert [(decks[seat], seat) for _, decks, seat in schedule] == [
        ("goat", 0), ("goat", 1), ("chaos", 0), ("chaos", 1)]
    with pytest.raises(ValueError, match="matchup"):
        episode_schedule((), (100,))


def test_demonstration_seat_filters_verified_duel_labels():
    first = DecisionRecord(view(), actions(), actions()[1])
    second_view = replace(
        view(), viewer=1, acting_player=1,
        hand=(CardView(1, "hand", "hidden", 20, 0),),
        field=(CardView(0, "monster", "facedown", None, 0, "defense"),),
    )
    second_action = Action("opponent", "pass", 1)
    second = DecisionRecord(second_view, (second_action,), second_action)
    trajectory = Trajectory("goat", ("a", "b"), 1, (first, second), 0,
                            source="heuristic", skill_metadata={"demonstrator_seat": 0})
    assert demonstrator_records(trajectory) == (first,)
    assert demonstrator_records(replace(
        trajectory, skill_metadata={"demonstrator_seat": 1})) == (second,)
    assert demonstrator_records(replace(
        trajectory, source="self_play", skill_metadata=None)) == (first, second)
    with pytest.raises(ValueError, match="demonstrator_seat"):
        demonstrator_records(replace(trajectory, skill_metadata=None))
    with pytest.raises(ValueError, match="demonstrator_seat"):
        demonstrator_records(replace(trajectory, skill_metadata={"demonstrator_seat": True}))


def test_policy_agent_progresses_multi_card_selection():
    class FavorUnselect(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.dummy = torch.nn.Parameter(torch.zeros(1))

        def forward(self, features):
            return (features.action_kinds == ACTION_KINDS.index("unselect_card") + 1
                    ).float() * 10 + self.dummy

    agent = PolicyAgent(FavorUnselect(), CardVocabulary((10, 20)))
    first = Action("first", "select_card", 0, {"code": 10, "sequence": 0})
    assert agent.select_action(view(), (first,)) == first
    toggle = Action("toggle", "unselect_card", 0, {"code": 10, "sequence": 0})
    other = Action("other", "select_card", 0, {"code": 20, "sequence": 1})
    assert agent.select_action(view(), (toggle, other)) == other
    finish = Action("finish", "finish_selection", 0)
    assert agent.select_action(view(), (toggle, finish)) == finish

    class FavorCancel(FavorUnselect):
        def forward(self, features):
            return (features.action_kinds == ACTION_KINDS.index("cancel") + 1
                    ).float() * 10 + self.dummy

    cancel_agent = PolicyAgent(FavorCancel(), CardVocabulary((10, 20)))
    cancel = Action("cancel", "cancel", 0)
    assert cancel_agent.select_action(view(), (cancel, first)) == first
