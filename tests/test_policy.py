"""Contract checks for the optional PyTorch legal-action policy."""

import pytest

torch = pytest.importorskip("torch")

from goat_ai.actions import Action
from goat_ai.observations import CardView, Observation
from goat_ai.replay import DecisionRecord
from goat_ai.training import (
    CardVocabulary,
    LegalActionPolicy,
    PolicyAgent,
    encode_decision,
    fit_behavioral_clone,
    load_policy_agent,
)
from scripts.evaluate_policy import validate_heldout_seeds


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
                "vocabulary_codes": vocabulary.codes, "width": 16}, checkpoint)
    restored = load_policy_agent(checkpoint)
    assert restored.select_action(view(), actions()) == actions()[1]
    with pytest.raises(ValueError, match="training needs records"):
        fit_behavioral_clone(policy, vocabulary, [])


def test_evaluation_rejects_training_seed_overlap():
    checkpoint = {"training_games": [{"seed": 42}]}
    validate_heldout_seeds(checkpoint, [43, 44])
    with pytest.raises(ValueError, match="overlap"):
        validate_heldout_seeds(checkpoint, [42, 43])
    with pytest.raises(ValueError, match="provenance"):
        validate_heldout_seeds({}, [43])
