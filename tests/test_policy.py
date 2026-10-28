"""Contract checks for the optional PyTorch legal-action policy."""

import copy
import math
import pickle
import random
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from functools import partial
from multiprocessing import get_context
from pathlib import Path
from types import SimpleNamespace

import pytest

torch = pytest.importorskip("torch")

from goat_ai.actions import Action
from goat_ai.agents.tactical_guard import HEAVY_STORM, SCAPEGOAT
from goat_ai.engine.decks import read_ydk
from goat_ai.engine.protocol import SimulatorUnavailable
from goat_ai.observations import (
    CardView,
    ChainLinkView,
    DisabledZoneView,
    KnownCardView,
    Observation,
    TargetSlotView,
)
from goat_ai.replay import (
    DecisionRecord,
    ReviewedPreference,
    Trajectory,
    demonstrator_records,
    demonstrator_seat,
    training_demonstrator_records,
)
from goat_ai.training import (
    CardVocabulary,
    LegalActionPolicy,
    PolicyAgent,
    encode_decision,
    fit_behavioral_clone,
    fit_preferences_with_parent_kl,
    fit_with_parent_kl,
    load_policy_agent,
)
from goat_ai.training.on_policy_teacher import (
    filter_activation_opportunities,
    label_policy_trajectory,
    teacher_disagreement_flags,
)
from goat_ai.training.policy import ACTION_KINDS
from goat_ai.training.self_play import (
    EpisodeDecisionLimit,
    TracedRolloutScorer,
    VisibleStateValue,
    _sample_legal_action_with_features,
    _selection_progress_actions,
    clipped_surrogate,
    episode_schedule,
    policy_gradient_update,
    ppo_clipped_update,
    predict_state_values,
    sample_legal_action,
    state_value_update,
    terminal_gae_advantages,
    train_against_snapshot_pool,
)
from scripts.audit_policy_agreement import (
    STAPLES,
    decision_deck,
    decision_fingerprint,
    decision_scopes,
    staple_context,
)
from scripts.compare_value_architectures import selected_records
from scripts.evaluate_policy import (
    make_policy_agent,
    validate_heldout_seeds,
    validate_unseen_deck_hashes,
    validate_unseen_main_decks,
)
from scripts.train_behavioral_clone import (
    annotation_paths,
    decision_sampling_weights,
    focus_opportunity,
    load_parent_checkpoint,
    parse_source_weights,
    restrict_trainable_modules,
)


def _raise_capped_episode_for_worker_test():
    raise EpisodeDecisionLimit(21211, 3000)


def test_clone_sampling_composes_source_focus_and_selected_kind_weights():
    base = view()
    set_action = Action("set", "set_monster", 0,
                        {"code": 10, "location": 2})
    other = Action("end", "end_phase", 0)
    records = (DecisionRecord(base, (set_action, other), set_action),
               DecisionRecord(base, (set_action, other), other))
    assert decision_sampling_weights(records, ("teacher", "teacher"), {},
                                     set(), 1.0, {}) is None
    assert decision_sampling_weights(records, ("teacher", "teacher"),
                                     {"teacher": 2.0}, {10}, 3.0,
                                     {"set_monster": 5.0}) == [30.0, 6.0]
    assert decision_sampling_weights(records, ("teacher", "teacher"), {},
                                     set(), 1.0, {}, (True, False), 4.0) == [4.0, 1.0]
    with pytest.raises(ValueError, match="source"):
        decision_sampling_weights(records, ("teacher",), {}, set(), 1.0, {})
    with pytest.raises(ValueError, match="source"):
        decision_sampling_weights(records, ("teacher", "teacher"), {}, set(),
                                  1.0, {}, (True,), 4.0)


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


def test_traced_rollout_scores_varying_legal_action_counts_exactly():
    vocabulary = CardVocabulary((10,), ((10, 1, 300),))
    model = LegalActionPolicy(vocabulary.size, width=8, feature_version=23).eval()
    scorer = TracedRolloutScorer(model)
    with torch.inference_mode():
        for legal in (actions(), actions()[:2], actions()[1:]):
            features = encode_decision(view(), legal, vocabulary, 23)
            assert torch.equal(scorer(features), model(features))
    with pytest.raises(ValueError, match="eval-mode v23"):
        TracedRolloutScorer(LegalActionPolicy(vocabulary.size, width=8,
                                              feature_version=23))


def test_traced_rollout_scores_changing_chain_and_field_sizes():
    vocabulary = CardVocabulary((10, 20, 30), ((10, 1, 300),))
    model = LegalActionPolicy(vocabulary.size, width=8, feature_version=23).eval()
    scorer = TracedRolloutScorer(model)
    base = view()
    open_monster = CardView(0, "monster", "faceup", 20, 0, "attack",
                            attack=1800, defense=1000)
    chain = (ChainLinkView(1, 20, 0, 8, 0),
             ChainLinkView(2, 30, 1, 8, 0))
    observations = (
        base,
        replace(base, field=base.field + (open_monster,), chain=chain[:1]),
        replace(base, field=(open_monster,), chain=chain),
        base,
    )
    with torch.inference_mode():
        for observation, legal in zip(
                observations, (actions(), actions()[:2], actions()[1:], actions()),
                strict=True):
            features = encode_decision(observation, legal, vocabulary, 23)
            assert torch.allclose(scorer(features), model(features),
                                  atol=1e-6, rtol=1e-6)


def test_traced_rollout_requires_supported_training_schedule():
    vocabulary = CardVocabulary((10,), ((10, 1, 300),))
    policy = LegalActionPolicy(vocabulary.size, width=8, feature_version=23)
    with pytest.raises(ValueError, match="single-process v23 multi-duel PPO"):
        train_against_snapshot_pool(
            policy, vocabulary, (("a", "b"),), (1,), lambda: None,
            trace_rollout_inference=True)


def test_on_policy_teacher_labels_only_checkpoint_policy_seat():
    own = DecisionRecord(view(), actions(), actions()[0])
    opponent_view = replace(view(), viewer=1, acting_player=1,
                            hand=(CardView(1, "hand", "hidden", 20, 0),))
    opponent_action = Action("opponent", "pass", 1)
    other = DecisionRecord(opponent_view, (opponent_action,), opponent_action)
    parent_hash = "a" * 64
    trajectory = Trajectory("goat", ("a", "b"), 7, (own, other), 0,
                            source="policy_evaluation",
                            skill_metadata={"demonstrator_seat": 0,
                                            "policy_checkpoint_sha256": parent_hash})

    class Teacher:
        def select_action(self, observation, legal_actions):
            assert observation.acting_player == 0
            return legal_actions[1]

    labeled, disagreements = label_policy_trajectory(trajectory, Teacher(), parent_hash)
    assert len(labeled) == 1
    assert labeled[0].selected_action == actions()[1]
    assert disagreements == 1
    assert teacher_disagreement_flags(trajectory, labeled) == (True,)
    with pytest.raises(ValueError, match="aligned"):
        teacher_disagreement_flags(trajectory, ())
    assert trajectory.decisions[0].selected_action == actions()[0]
    with pytest.raises(ValueError, match="matching checkpoint"):
        label_policy_trajectory(trajectory, Teacher(), "b" * 64)
    with pytest.raises(ValueError, match="matching checkpoint"):
        label_policy_trajectory(replace(trajectory, source="self_play_rl"),
                                Teacher(), parent_hash)


def test_on_policy_teacher_rejects_illegal_label():
    record = DecisionRecord(view(), actions(), actions()[0])
    trajectory = Trajectory("goat", ("a", "b"), 7, (record,), 0,
                            source="policy_evaluation",
                            skill_metadata={"demonstrator_seat": 0,
                                            "policy_checkpoint_sha256": "a" * 64})

    class BadTeacher:
        def select_action(self, observation, legal_actions):
            return Action("illegal", "pass", 0)

    with pytest.raises(ValueError, match="illegal action"):
        label_policy_trajectory(trajectory, BadTeacher(), "a" * 64)


def test_activation_focus_keeps_both_good_and_bad_trade_opportunities():
    storm = Action("storm", "activate", 0, {"code": HEAVY_STORM})
    end = Action("end", "end_phase", 0)
    summon, set_monster = actions()[:2]
    records = (DecisionRecord(view(), (storm, end), storm),
               DecisionRecord(view(), (summon, set_monster), summon),
               DecisionRecord(view(), (storm, end), end))
    trajectory = Trajectory("goat", ("a", "b"), 7, records, 0,
                            source="policy_evaluation",
                            skill_metadata={"demonstrator_seat": 0,
                                            "policy_checkpoint_sha256": "a" * 64})

    class Teacher:
        def select_action(self, observation, legal_actions):
            return legal_actions[-1]

    labeled, disagreements = label_policy_trajectory(trajectory, Teacher(), "a" * 64)
    assert disagreements == 2
    focused, focused_disagreements = filter_activation_opportunities(
        trajectory, labeled, {HEAVY_STORM})
    assert len(focused) == 2
    assert focused_disagreements == 1
    assert focused[0].selected_action == focused[1].selected_action == end
    with pytest.raises(ValueError, match="aligned"):
        filter_activation_opportunities(trajectory, labeled[:1], {HEAVY_STORM})
    with pytest.raises(ValueError, match="card IDs"):
        filter_activation_opportunities(trajectory, labeled, set())


def test_position_action_features_bind_visible_stats_without_hidden_enemy_stats():
    vocabulary = CardVocabulary((10, 20, 30), ((10, 0, 0), (20, 0, 1900),
                                               (30, 0, 1800)))
    token = CardView(0, "monster", "faceup", 10, 0, "defense",
                     attack=0, defense=0)
    strong = CardView(0, "monster", "faceup", 20, 1, "defense",
                      attack=1900, defense=1400)
    hidden = CardView(1, "monster", "facedown", None, 0, "defense")
    observation = replace(view(), field=(token, strong, hidden))
    options = (Action("token", "change_position", 0,
                      {"code": 10, "controller": 0, "location": 4, "sequence": 0}),
               Action("strong", "change_position", 0,
                      {"code": 20, "controller": 0, "location": 4, "sequence": 1}),
               Action("end", "end_phase", 0))
    features = encode_decision(observation, options, vocabulary, feature_version=23)
    assert features.action_numbers.shape == (3, 101)
    assert features.action_numbers[0, -6] == 0
    assert features.action_numbers[1, -6] == pytest.approx(1900 / 8000)
    assert features.action_numbers[0, -1] == 0  # Opponent face-down stat is unknown.
    changed_hidden = replace(observation, field=(token, strong,
                                                   replace(hidden, sequence=2)))
    assert torch.equal(features.action_numbers,
                       encode_decision(changed_hidden, options, vocabulary,
                                       feature_version=23).action_numbers)
    stronger_token = replace(observation, field=(replace(token, attack=1600),
                                                  strong, hidden))
    assert torch.equal(
        encode_decision(observation, options, vocabulary,
                        feature_version=22).action_numbers,
        encode_decision(stronger_token, options, vocabulary,
                        feature_version=22).action_numbers)
    assert not torch.equal(
        features.action_numbers[0],
        encode_decision(stronger_token, options, vocabulary,
                        feature_version=23).action_numbers[0])
    assert torch.isfinite(LegalActionPolicy(vocabulary.size, width=8,
                                             feature_version=23)(features)).all()


def test_resource_trade_features_count_only_visible_collateral():
    codes = tuple(sorted((10, 20, 19613556, 504700116, 504700044)))
    vocabulary = CardVocabulary(codes, tuple((code, 0, 0) for code in codes))
    source = CardView(0, "spell_trap", "facedown", 19613556, 0)
    collateral = CardView(0, "spell_trap", "facedown", 20, 1)
    enemy = CardView(1, "spell_trap", "facedown", None, 0)
    own_spy = CardView(0, "monster", "facedown", 504700044, 0)
    storm = Action("storm", "activate", 0,
                   {"code": 19613556, "location": 8, "sequence": 0})
    nobleman = Action("nobleman", "activate", 0,
                      {"code": 504700116, "location": 2})
    end = Action("end", "end_phase", 0)
    observation = replace(view(), field=(source, collateral, enemy, own_spy))
    features = encode_decision(observation, (storm, nobleman, end),
                               vocabulary, feature_version=24)
    assert features.action_numbers.shape == (3, 104)
    assert features.action_numbers[0, -3:].tolist() == pytest.approx((-0.2, 0.2, 1))
    assert features.action_numbers[1, -3:].tolist() == pytest.approx((-0.4, 0.2, 1))
    assert features.action_numbers[2, -3:].tolist() == [0, 0, 0]
    # Moving an unknown opposing Set card does not change the trade count.
    changed = replace(observation, field=(source, collateral,
                                          replace(enemy, sequence=3), own_spy))
    assert torch.equal(features.action_numbers,
                       encode_decision(changed, (storm, nobleman, end),
                                       vocabulary, feature_version=24).action_numbers)
    with_target = replace(observation, field=(*observation.field,
                          CardView(1, "monster", "facedown", None, 1)))
    with_target_features = encode_decision(with_target, (storm, nobleman, end),
                                           vocabulary, feature_version=24)
    assert with_target_features.action_numbers[1, -3:].tolist() == [0, 0, 1]
    assert torch.isfinite(LegalActionPolicy(vocabulary.size, width=8,
                                            feature_version=24)(features)).all()


def test_staple_audit_distinguishes_played_cards_from_target_codes():
    played = Action("play", "activate", 0, {"code": 10})
    target = Action("target", "select_card", 0, {"code": 20})
    end = Action("end", "end_phase", 0)
    active_chain = replace(view(), chain=(ChainLinkView(1, 30, 1, 8, 0),))
    selected_play = DecisionRecord(view(), (played, end), played)
    selected_target = DecisionRecord(active_chain, (target,), target)
    assert staple_context(selected_play, {10, 20, 30}) == {
        "offered": {10}, "teacher_selected": {10}, "chain_prompt": set()}
    assert staple_context(selected_target, {10, 20, 30}) == {
        "offered": set(), "teacher_selected": set(), "chain_prompt": {30}}


def test_policy_audit_attributes_each_decision_to_its_acting_deck():
    left = DecisionRecord(view(), (actions()[0],), actions()[0])
    right_view = replace(view(), viewer=1, acting_player=1, hand=(
        CardView(1, "hand", "hidden", 20, 0),))
    right_action = Action("right", "end_phase", 1)
    right = DecisionRecord(right_view, (right_action,), right_action)
    trajectory = Trajectory("goat", ("left.ydk", "right.ydk"), 7,
                            (left, right), 0)
    assert decision_deck(trajectory, left) == "left.ydk"
    assert decision_deck(trajectory, right) == "right.ydk"


def test_mixed_annotation_mapping_rejects_misassigned_or_duplicate_labels(tmp_path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    label = tmp_path / "labels.json"
    assert annotation_paths([first, second], [], [f"{second}={label}"]) == {
        second.resolve(): label}
    with pytest.raises(ValueError, match="not supplied"):
        annotation_paths([first], [], [f"{second}={label}"])
    with pytest.raises(ValueError, match="duplicate"):
        annotation_paths([first], [], [f"{first}={label}", f"{first}={label}"])
    with pytest.raises(ValueError, match="not both"):
        annotation_paths([first], [label], [f"{first}={label}"])
    with pytest.raises(ValueError, match="duplicate trajectory"):
        annotation_paths([first, first], [], [])


def test_source_weights_require_finite_positive_unique_values():
    assert parse_source_weights(["synthetic_annotation=200"]) == {
        "synthetic_annotation": 200.0}
    for assignments in (["synthetic_annotation=nan"],
                        ["synthetic_annotation=0"],
                        ["synthetic_annotation=2", "synthetic_annotation=3"]):
        with pytest.raises(ValueError):
            parse_source_weights(assignments)


def test_restricted_warm_start_updates_only_selected_modules():
    model = LegalActionPolicy(8, width=16, feature_version=19)
    restrict_trainable_modules(model, ["state_numbers", "score"])
    assert all(parameter.requires_grad == name.startswith(("state_numbers.", "score."))
               for name, parameter in model.named_parameters())
    with pytest.raises(ValueError, match="unknown trainable"):
        restrict_trainable_modules(model, ["missing"])


def test_parent_kl_fits_labels_while_keeps_reference_frozen():
    torch.manual_seed(7)
    vocabulary = CardVocabulary((10, 20))
    student = LegalActionPolicy(vocabulary.size, width=16, feature_version=19)
    parent = copy.deepcopy(student)
    repeat = copy.deepcopy(student)
    legal = actions()[:2]
    labeled = DecisionRecord(replace(view(), turn_player=1), legal, legal[1])
    preservation = DecisionRecord(replace(view(), turn_player=0), legal, legal[0])
    before = {name: parameter.detach().clone()
              for name, parameter in parent.named_parameters()}
    labeled_losses, kl_losses = fit_with_parent_kl(
        student, parent, vocabulary, (labeled,), (preservation,),
        steps=8, preservation_batch=1, preservation_weight=1.0,
        learning_rate=0.001, rng=random.Random(19))
    assert len(labeled_losses) == len(kl_losses) == 8
    assert labeled_losses[-1] < labeled_losses[0]
    assert abs(kl_losses[0]) < 1e-6
    assert all(torch.equal(parameter, before[name])
               for name, parameter in parent.named_parameters())
    repeated_losses = fit_with_parent_kl(
        repeat, parent, vocabulary, (labeled,), (preservation,),
        steps=8, preservation_batch=1, preservation_weight=1.0,
        learning_rate=0.001, rng=random.Random(19))
    assert repeated_losses == (labeled_losses, kl_losses)
    assert all(torch.equal(parameter, dict(repeat.named_parameters())[name])
               for name, parameter in student.named_parameters())
    with pytest.raises(ValueError, match="labeled weights"):
        fit_with_parent_kl(student, parent, vocabulary, (labeled,), (preservation,),
                           steps=1, preservation_batch=1, preservation_weight=1.0,
                           learning_rate=0.001, rng=random.Random(19),
                           labeled_weights=(0.0,))


def test_preference_kl_raises_a_reviewed_set_without_forcing_one_target():
    torch.manual_seed(7)
    vocabulary = CardVocabulary((10, 20))
    student = LegalActionPolicy(vocabulary.size, width=16, feature_version=19)
    parent = copy.deepcopy(student)
    legal = actions()
    record = DecisionRecord(replace(view(), turn_player=0), legal, legal[0])
    preference = ReviewedPreference(0, (1, 2), (0,))
    preservation = DecisionRecord(replace(view(), turn_player=1), legal, legal[0])
    features = encode_decision(record.observation, legal, vocabulary, 19)

    def set_margin():
        with torch.no_grad():
            logits = student(features)
            return float(torch.logsumexp(logits[[1, 2]], dim=0)
                         - torch.log(torch.tensor(2.0)) - logits[0])

    before = set_margin()
    frozen = {name: parameter.detach().clone()
              for name, parameter in parent.named_parameters()}
    losses, kl = fit_preferences_with_parent_kl(
        student, parent, vocabulary, ((record, preference),), (preservation,),
        steps=8, preservation_batch=1, preservation_weight=1.0,
        learning_rate=0.001, rng=random.Random(19))
    assert len(losses) == len(kl) == 8
    assert losses[-1] < losses[0]
    assert set_margin() > before
    assert all(torch.equal(parameter, frozen[name])
               for name, parameter in parent.named_parameters())
    with pytest.raises(ValueError, match="disjoint legal sets"):
        fit_preferences_with_parent_kl(
            student, parent, vocabulary,
            ((record, ReviewedPreference(0, (0, 1), (0,))),), (preservation,),
            steps=1, preservation_batch=1, preservation_weight=1.0,
            learning_rate=0.001, rng=random.Random(19))


def test_counterfactual_preference_can_rank_recorded_safe_action_above_bad_option():
    torch.manual_seed(71)
    vocabulary = CardVocabulary((10, 20))
    student = LegalActionPolicy(vocabulary.size, width=8, feature_version=19)
    parent = copy.deepcopy(student)
    legal = actions()
    record = DecisionRecord(replace(view(), turn_player=0), legal, legal[0])
    preference = ReviewedPreference(0, (0,), (1,))
    preservation = DecisionRecord(replace(view(), turn_player=1), legal, legal[0])
    features = encode_decision(record.observation, legal, vocabulary, 19)
    with torch.no_grad():
        before = float(student(features)[0] - student(features)[1])
    losses, _ = fit_preferences_with_parent_kl(
        student, parent, vocabulary, ((record, preference),), (preservation,),
        steps=4, preservation_batch=1, preservation_weight=1.0,
        learning_rate=0.001, rng=random.Random(71))
    with torch.no_grad():
        after = float(student(features)[0] - student(features)[1])
    assert losses[-1] < losses[0]
    assert after > before


def test_recorded_bad_weight_changes_conflicting_preference_update():
    torch.manual_seed(72)
    vocabulary = CardVocabulary((10, 20))
    initial = LegalActionPolicy(vocabulary.size, width=8, feature_version=19)
    legal = actions()[:2]
    observation = replace(view(), turn_player=0)
    recorded_bad = DecisionRecord(observation, legal, legal[0])
    recorded_safe = DecisionRecord(observation, legal, legal[0])
    comparisons = (
        (recorded_bad, ReviewedPreference(0, (1,), (0,))),
        (recorded_safe, ReviewedPreference(0, (0,), (1,))),
    )
    preservation = (recorded_safe,)
    margins = []
    for weight in (1.0, 8.0):
        child = copy.deepcopy(initial)
        fit_preferences_with_parent_kl(
            child, copy.deepcopy(initial), vocabulary, comparisons,
            preservation, steps=2, preservation_batch=1,
            preservation_weight=1.0, learning_rate=0.001,
            rng=random.Random(72), recorded_bad_weight=weight)
        features = encode_decision(observation, legal, vocabulary, 19)
        with torch.no_grad():
            logits = child(features)
            margins.append(float(logits[1] - logits[0]))
    assert margins[1] > margins[0]
    with pytest.raises(ValueError, match="bad-choice weight"):
        fit_preferences_with_parent_kl(
            copy.deepcopy(initial), copy.deepcopy(initial), vocabulary,
            comparisons, preservation, steps=1, preservation_batch=1,
            preservation_weight=1.0, learning_rate=0.001,
            rng=random.Random(72), recorded_bad_weight=0)


def test_policy_audit_fingerprint_identifies_visible_decision_and_choice():
    observation = view()
    legal = actions()
    first = DecisionRecord(observation, legal, legal[0])
    second = DecisionRecord(observation, legal, legal[1])
    assert decision_fingerprint(first) == decision_fingerprint(
        DecisionRecord(observation, legal, legal[0]))
    assert decision_fingerprint(first) != decision_fingerprint(second)


def test_focus_opportunity_uses_card_source_or_public_chain():
    played = Action("play", "activate", 0, {"code": 10})
    target = Action("target", "select_card", 0, {"code": 10})
    end = Action("end", "end_phase", 0)
    assert focus_opportunity(DecisionRecord(view(), (played, end), end), {10})
    assert not focus_opportunity(DecisionRecord(view(), (target, end), end), {10})
    assert not focus_opportunity(DecisionRecord(view(), (played,), played), {10})
    active_chain = replace(view(), chain=(ChainLinkView(1, 10, 1, 8, 0),))
    assert focus_opportunity(DecisionRecord(active_chain, (target, end), end), {10})


def test_audit_scopes_isolate_public_target_decisions():
    untargeted = replace(view(), chain=(ChainLinkView(1, 30, 1, 8, 0),))
    targeted = replace(view(), chain=(ChainLinkView(
        1, 30, 1, 8, 0, (TargetSlotView(0, "monster", 0),)),))
    single = (Action("pass", "pass", 0),)
    multiple = (single[0], Action("chain", "chain", 0, {"code": 10}))
    assert "chain_target" not in decision_scopes(DecisionRecord(
        untargeted, multiple, multiple[0]))
    assert "chain_target" in decision_scopes(DecisionRecord(
        targeted, single, single[0]))
    assert "chain_target_multi_option" not in decision_scopes(DecisionRecord(
        targeted, single, single[0]))
    assert "chain_target_multi_option" in decision_scopes(DecisionRecord(
        targeted, multiple, multiple[0]))


def test_audit_scopes_separate_turn_owner_and_end_phase():
    action = Action("pass", "pass", 0)
    record = lambda observation: DecisionRecord(observation, (action,), action)
    assert "own_turn" in decision_scopes(record(replace(view(), turn_player=0)))
    assert "opponent_turn" in decision_scopes(record(replace(view(), turn_player=1)))
    own_end = decision_scopes(record(replace(view(), turn_player=0, phase="end")))
    opponent_end = decision_scopes(record(replace(view(), turn_player=1, phase="end")))
    assert "own_end" in own_end and "opponent_end" not in own_end
    assert "opponent_end" in opponent_end and "own_end" not in opponent_end
    assert "own_turn" not in decision_scopes(record(view()))


def test_staple_audit_matches_shared_tournament_main_deck_cards():
    root = Path(__file__).resolve().parents[1] / "examples" / "decks"
    names = ("goat_control_lolmarcus_2020.ydk", "chaos_turbo_riclar_2020.ydk",
             "warrior_montague_clash.ydk", "chaos_control_insids_worlds_2022.ydk",
             "chaos_return_dingosig_worlds_2022.ydk")
    shared = set.intersection(*(set(read_ydk(root / name).main) for name in names))
    assert set(STAPLES) == shared


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


def test_feature_version_twenty_nine_encodes_only_public_faceup_age():
    vocabulary = CardVocabulary((10, 20), ((10, 0, 1000), (20, 0, 2000)))
    base = replace(view(), field=(CardView(
        0, "monster", "faceup", 20, 0, "attack", 1900, 1000,
        faceup_turns=0),))
    older = replace(base, field=(replace(base.field[0], faceup_turns=2),))
    first = encode_decision(base, actions(), vocabulary, 29)
    second = encode_decision(older, actions(), vocabulary, 29)
    assert first.state_card_numbers.shape == (2, 6)
    assert first.state_card_numbers[1, -1] == 0
    assert second.state_card_numbers[1, -1] == pytest.approx(0.1)
    assert torch.equal(encode_decision(base, actions(), vocabulary, 23).state_card_numbers,
                       encode_decision(older, actions(), vocabulary, 23).state_card_numbers)
    assert LegalActionPolicy(vocabulary.size, width=8, feature_version=29)(first).shape == (3,)
    value = VisibleStateValue(vocabulary.size, first.state_numbers.numel(),
                              width=8, architecture="v2", card_number_width=6)
    assert value(first).numel() == 1


def test_feature_version_fifteen_counts_public_occupancy_without_card_identity():
    vocabulary = CardVocabulary((10, 20))
    original = view()
    crowded = replace(original, field=(
        CardView(0, "monster", "faceup", 20, 0, "attack", 1900, 1000),
        CardView(1, "monster", "facedown", None, 0, "defense"),
        CardView(1, "spell_trap", "facedown", None, 1),
    ))
    first = encode_decision(original, actions(), vocabulary, feature_version=15)
    second = encode_decision(crowded, actions(), vocabulary, feature_version=15)
    assert first.state_numbers.shape == (54,)
    assert second.state_numbers[-12:].tolist() == pytest.approx(
        [0.2, 0, 0, 0, 0, 0.2, 0, 0.2, 0, 0, 0, 0])
    assert not torch.equal(first.state_numbers, second.state_numbers)
    assert torch.equal(encode_decision(original, actions(), vocabulary,
                                       feature_version=14).state_numbers,
                       encode_decision(crowded, actions(), vocabulary,
                                       feature_version=14).state_numbers)
    assert LegalActionPolicy(vocabulary.size, width=16, feature_version=15)(
        second).shape == (3,)


def test_feature_version_sixteen_exposes_visible_attack_margin():
    vocabulary = CardVocabulary((10, 20))
    own = CardView(0, "monster", "faceup", 20, 0, "attack", 1500, 1000)
    strong = CardView(1, "monster", "faceup", 10, 0, "attack", 1900, 1000)
    weak = replace(strong, attack=1000)
    hidden = CardView(1, "monster", "facedown", None, 0, "defense")
    attack = Action("attack", "attack", 0, {"code": 20, "controller": 0,
                                              "location": 4, "sequence": 0})
    choices = (attack, Action("main2", "main2", 0))
    views = [replace(view(), field=(own, opposing))
             for opposing in (strong, weak, hidden)]
    views.append(replace(view(), field=(own,)))
    encoded = [encode_decision(state, choices, vocabulary, feature_version=16)
               for state in views]
    assert encoded[0].action_numbers.shape == (2, 15)
    assert torch.allclose(torch.stack([features.action_numbers[0, -4:]
                                       for features in encoded]), torch.tensor([
        [1500 / 8000, -400 / 8000, 1, 0],
        [1500 / 8000, 500 / 8000, 1, 0],
        [1500 / 8000, 0, 0, 0],
        [1500 / 8000, 0, 1, 1],
    ]))
    assert encoded[0].action_numbers[1, -4:].tolist() == [0, 0, 0, 0]
    assert torch.equal(encode_decision(views[0], choices, vocabulary,
                                       feature_version=12).action_numbers,
                       encode_decision(views[1], choices, vocabulary,
                                       feature_version=12).action_numbers)
    assert LegalActionPolicy(vocabulary.size, width=16, feature_version=16)(
        encoded[0]).shape == (2,)


def test_feature_version_seventeen_scores_attack_targets_from_visible_stats():
    vocabulary = CardVocabulary((10, 20, 30))
    attacker = CardView(0, "monster", "faceup", 20, 2, "attack", 1500, 1000)
    stronger = CardView(1, "monster", "faceup", 10, 0, "attack", 1900, 1000)
    weaker = CardView(1, "monster", "faceup", 30, 1, "defense", 1000, 1200)
    hidden = CardView(1, "monster", "facedown", None, 3, "defense")
    state = replace(view(), phase="battle_start", field=(attacker, stronger, weaker, hidden),
                    pending_attack=TargetSlotView(0, "monster", 2))
    choices = tuple(Action(str(index), "select_card", 0,
                           {"code": card.code, "controller": 1,
                            "location": 4, "sequence": card.sequence}
                           if card.code is not None else
                           {"controller": 1, "location": 4, "sequence": card.sequence})
                    for index, card in enumerate((stronger, weaker, hidden)))
    features = encode_decision(state, choices, vocabulary, feature_version=17)
    assert features.action_numbers.shape == (3, 19)
    assert torch.allclose(features.action_numbers[:, -4:], torch.tensor([
        [1500 / 8000, 1900 / 8000, -400 / 8000, 1],
        [1500 / 8000, 1200 / 8000, 300 / 8000, 1],
        [1500 / 8000, 0, 0, 0],
    ]))
    assert LegalActionPolicy(vocabulary.size, width=16, feature_version=17)(
        features).shape == (3,)
    with pytest.raises(ValueError, match="pending attack"):
        replace(state, pending_attack=TargetSlotView(1, "monster", 0))


def test_feature_version_eighteen_binds_public_chain_source_to_target():
    vocabulary = CardVocabulary((10, 20, 30, 40))
    state = replace(view(), field=(
        CardView(1, "monster", "faceup", 20, 0, "attack", 1600, 1000),
        CardView(1, "monster", "faceup", 30, 1, "attack", 1900, 1000),
    ), chain=(ChainLinkView(1, 40, 0, 8, 0),))
    choices = tuple(Action(str(index), "select_card", 0,
                           {"code": code, "controller": 1, "location": 4,
                            "sequence": index}) for index, code in enumerate((20, 30)))
    with_chain = encode_decision(state, choices, vocabulary, feature_version=18)
    without_chain = encode_decision(replace(state, chain=()), choices, vocabulary,
                                    feature_version=18)
    assert with_chain.chain_cards[-1, 0].item() == vocabulary.index(40)
    assert with_chain.action_cards.tolist() == [vocabulary.index(20),
                                                vocabulary.index(30)]
    assert with_chain.action_numbers.shape == (2, 19)
    model = LegalActionPolicy(vocabulary.size, width=16, feature_version=18)
    plain_before = model(without_chain).detach().clone()
    chained_before = model(with_chain).detach().clone()
    with torch.no_grad():
        model.source_target_pair[-1].bias.add_(1)
    assert torch.allclose(model(without_chain), plain_before)
    assert not torch.allclose(model(with_chain), chained_before)


def test_feature_version_nineteen_distinguishes_turn_owner_from_actor():
    vocabulary = CardVocabulary((10, 20))
    action = (Action("pass", "pass", 0),)
    base = view()
    own_turn = encode_decision(replace(base, turn_player=0), action,
                               vocabulary, feature_version=19)
    opponent_turn = encode_decision(replace(base, turn_player=1), action,
                                    vocabulary, feature_version=19)
    legacy = encode_decision(base, action, vocabulary, feature_version=19)
    assert own_turn.state_numbers.shape == (44,)
    assert own_turn.state_numbers[-2:].tolist() == [1.0, 1.0]
    assert opponent_turn.state_numbers[-2:].tolist() == [0.0, 1.0]
    assert legacy.state_numbers[-2:].tolist() == [0.0, 0.0]
    assert torch.equal(encode_decision(replace(base, turn_player=0), action,
                                       vocabulary, feature_version=18).state_numbers,
                       encode_decision(replace(base, turn_player=1), action,
                                       vocabulary, feature_version=18).state_numbers)
    assert LegalActionPolicy(vocabulary.size, width=16, feature_version=19)(
        own_turn).shape == (1,)


def test_feature_version_twenty_preserves_distinct_tribe_type_choices():
    vocabulary = CardVocabulary((33184167,))
    choices = tuple(Action(str(race), "announce_race", 0, {"race": race})
                    for race in (2, 64, 16384, 2 | 16384))
    current = encode_decision(view(), choices, vocabulary, feature_version=20)
    legacy = encode_decision(view(), choices, vocabulary, feature_version=19)
    assert current.action_numbers.shape == (4, 81)
    assert current.action_numbers[:, 4:68].sum(1).tolist() == [1, 1, 1, 2]
    assert current.action_numbers[0, 5] == 1
    assert current.action_numbers[1, 10] == 1
    assert current.action_numbers[2, 18] == 1
    assert torch.equal(current.action_numbers[3, 4:68],
                       current.action_numbers[0, 4:68]
                       + current.action_numbers[2, 4:68])
    assert torch.dist(legacy.action_numbers[0], legacy.action_numbers[2]) < 1e-5
    assert torch.dist(current.action_numbers[0], current.action_numbers[2]) > 1
    assert LegalActionPolicy(vocabulary.size, width=16, feature_version=20)(
        current).shape == (4,)


def test_feature_version_twenty_one_relates_choice_to_current_public_type():
    vocabulary = CardVocabulary((10, 20))
    choices = (Action("warrior", "announce_race", 0, {"race": 2}),
               Action("aqua", "announce_race", 0, {"race": 64}))
    own = CardView(0, "monster", "faceup", 10, 0, "attack",
                   1200, 1000, race=2)
    enemy = CardView(1, "monster", "faceup", 20, 0, "attack",
                     1800, 1000, race=64)
    hidden = CardView(1, "monster", "facedown", None, 1, "defense")
    first = replace(view(), field=(own, enemy, hidden), turn_player=0)
    changed = replace(first, field=(replace(own, race=64),
                                    replace(enemy, race=2), hidden))
    previous = encode_decision(first, choices, vocabulary, feature_version=20)
    previous_changed = encode_decision(changed, choices, vocabulary,
                                       feature_version=20)
    current = encode_decision(first, choices, vocabulary, feature_version=21)
    current_changed = encode_decision(changed, choices, vocabulary,
                                      feature_version=21)
    assert torch.equal(previous.action_numbers, previous_changed.action_numbers)
    assert current.action_numbers.shape == (2, 85)
    assert torch.allclose(current.action_numbers[:, -4:], torch.tensor([
        [0.0, 0.2, 0.0, 0.15], [0.2, 0.0, 0.225, 0.0]]))
    assert torch.allclose(current_changed.action_numbers[:, -4:], torch.tensor([
        [0.2, 0.0, 0.225, 0.0], [0.0, 0.2, 0.0, 0.15]]))
    assert LegalActionPolicy(vocabulary.size, width=16, feature_version=21)(
        current).shape == (2,)


def test_feature_version_twenty_two_uses_printed_flip_and_public_resources():
    faith, storm, pot, vanilla = 31560081, 19613556, 55144522, 10
    vocabulary = CardVocabulary(
        tuple(sorted((faith, storm, pot, vanilla))),
        tuple(sorted(((faith, 0x200021, 300), (storm, 2, 0),
                      (pot, 2, 0), (vanilla, 0x21, 1400)))),
    )
    choices = (Action("summon", "normal_summon", 0, {"code": faith}),
               Action("set", "set_monster", 0, {"code": faith}),
               Action("storm", "activate", 0, {"code": storm}),
               Action("end", "end_phase", 0))
    own_set = CardView(0, "spell_trap", "facedown", storm, 0)
    opponent_set = CardView(1, "spell_trap", "facedown", None, 1)
    with_spell = replace(view(), hand=(CardView(0, "hand", "hidden", faith, 0),),
                         field=(own_set, opponent_set),
                         graveyards=((CardView(0, "graveyard", "faceup", pot, 0),), ()))
    without_spell = replace(with_spell, graveyards=(
        (CardView(0, "graveyard", "faceup", vanilla, 0),), ()))
    old = encode_decision(with_spell, choices, vocabulary, feature_version=21)
    old_other = encode_decision(without_spell, choices, vocabulary, feature_version=21)
    new = encode_decision(with_spell, choices, vocabulary, feature_version=22)
    new_other = encode_decision(without_spell, choices, vocabulary, feature_version=22)
    assert torch.equal(old.action_numbers, old_other.action_numbers)
    assert new.action_numbers.shape == (4, 93)
    assert torch.allclose(new.action_numbers[0, -8:], torch.tensor([
        1.0, 300 / 8000, 0.2, 0.2, 0.2, 0.0, 0.0, 0.0]))
    assert torch.equal(new.action_numbers[0, -8:], new.action_numbers[1, -8:])
    assert new_other.action_numbers[0, -6] == 0
    assert LegalActionPolicy(vocabulary.size, width=16, feature_version=22)(
        new).shape == (4,)
    with pytest.raises(ValueError, match="printed card properties"):
        encode_decision(with_spell, choices, CardVocabulary(vocabulary.codes),
                        feature_version=22)


def test_feature_version_twenty_two_checkpoint_requires_printed_metadata(tmp_path):
    vocabulary = CardVocabulary((10,), ((10, 0x200021, 300),))
    model = LegalActionPolicy(vocabulary.size, width=16, feature_version=22)
    path = tmp_path / "policy.pt"
    checkpoint = {"schema_version": 1, "model_state": model.state_dict(),
                  "vocabulary_codes": vocabulary.codes,
                  "vocabulary_card_properties": vocabulary.card_properties,
                  "width": 16, "feature_version": 22}
    torch.save(checkpoint, path)
    assert load_policy_agent(path).vocabulary.properties(10) == (0x200021, 300)
    torch.save({key: value for key, value in checkpoint.items()
                if key != "vocabulary_card_properties"}, path)
    with pytest.raises(ValueError, match="lacks printed card properties"):
        load_policy_agent(path)


def test_feature_version_twenty_two_cannot_see_hidden_target_properties():
    choices = (Action("target", "select_card", 0,
                      {"controller": 1, "location": 4, "sequence": 0}),
               Action("pass", "pass", 0))
    first = CardVocabulary((10, 20), ((10, 2, 0), (20, 0x200021, 300)))
    changed = CardVocabulary((10, 20), ((10, 2, 0), (20, 2, 0)))
    hidden = view()  # Opponent's face-down monster has no visible identity.
    encoded = encode_decision(hidden, choices, first, feature_version=22)
    other = encode_decision(hidden, choices, changed, feature_version=22)
    assert torch.equal(encoded.action_cards, other.action_cards)
    assert torch.equal(encoded.action_numbers, other.action_numbers)
    assert torch.equal(encoded.state_cards, other.state_cards)


def test_feature_version_nine_uses_only_publicly_known_opponent_hand_cards():
    vocabulary = CardVocabulary((10, 20, 30))
    known = replace(view(), known_opponent_hand_cards=(20,))
    unknown = replace(view(), known_opponent_hand_cards=())
    same_multiset = replace(view(), known_opponent_hand_cards=(20, 30))
    first = encode_decision(known, actions(), vocabulary, feature_version=9)
    second = encode_decision(unknown, actions(), vocabulary, feature_version=9)
    assert first.known_hand_cards.tolist() == [vocabulary.index(20)]
    assert second.known_hand_cards.tolist() == [0]
    assert encode_decision(same_multiset, actions(), vocabulary,
                           feature_version=9).known_hand_cards.tolist() == [
                               vocabulary.index(20), vocabulary.index(30)]
    assert torch.equal(first.state_cards, second.state_cards)
    torch.manual_seed(29)
    model = LegalActionPolicy(vocabulary.size, width=16, feature_version=9)
    assert model(first).shape == (3,)
    assert not torch.allclose(model(first), model(second))
    legacy_known = encode_decision(known, actions(), vocabulary, feature_version=8)
    legacy_unknown = encode_decision(unknown, actions(), vocabulary, feature_version=8)
    assert legacy_known.known_hand_cards.tolist() == [0]
    assert torch.equal(legacy_known.known_hand_cards, legacy_unknown.known_hand_cards)


def test_feature_version_ten_distinguishes_public_chain_order():
    vocabulary = CardVocabulary((10, 20))
    first = replace(view(), chain=(ChainLinkView(1, 10, 0, 8, 0),
                                   ChainLinkView(2, 20, 1, 8, 0)))
    reversed_chain = replace(view(), chain=(ChainLinkView(1, 20, 1, 8, 0),
                                            ChainLinkView(2, 10, 0, 8, 0)))
    first_features = encode_decision(first, actions(), vocabulary, feature_version=10)
    second_features = encode_decision(reversed_chain, actions(), vocabulary,
                                      feature_version=10)
    assert first_features.chain_cards.tolist() == [
        [vocabulary.index(10), 1], [vocabulary.index(20), 2]]
    assert second_features.chain_cards.tolist() == [
        [vocabulary.index(20), 2], [vocabulary.index(10), 1]]
    assert encode_decision(view(), actions(), vocabulary,
                           feature_version=10).chain_cards.tolist() == [[0, 0]]
    torch.manual_seed(41)
    model = LegalActionPolicy(vocabulary.size, width=16, feature_version=10)
    assert not torch.allclose(model(first_features), model(second_features))
    legacy_model = LegalActionPolicy(vocabulary.size, width=16, feature_version=9)
    legacy_first = encode_decision(first, actions(), vocabulary, feature_version=9)
    legacy_second = encode_decision(reversed_chain, actions(), vocabulary,
                                    feature_version=9)
    assert torch.allclose(legacy_model(legacy_first), legacy_model(legacy_second))


def test_feature_version_eleven_keeps_chain_capacity_without_order():
    vocabulary = CardVocabulary((10, 20))
    first = replace(view(), chain=(ChainLinkView(1, 10, 0, 8, 0),
                                   ChainLinkView(2, 20, 1, 8, 0)))
    reversed_chain = replace(view(), chain=(ChainLinkView(1, 20, 1, 8, 0),
                                            ChainLinkView(2, 10, 0, 8, 0)))
    first_features = encode_decision(first, actions(), vocabulary, feature_version=11)
    second_features = encode_decision(reversed_chain, actions(), vocabulary,
                                      feature_version=11)
    assert torch.equal(first_features.chain_cards, second_features.chain_cards)
    torch.manual_seed(41)
    ordered = LegalActionPolicy(vocabulary.size, width=16, feature_version=10)
    torch.manual_seed(41)
    unordered = LegalActionPolicy(vocabulary.size, width=16, feature_version=11)
    assert sum(p.numel() for p in ordered.parameters()) == sum(
        p.numel() for p in unordered.parameters())
    assert all(torch.equal(left, right) for left, right in zip(
        ordered.parameters(), unordered.parameters(), strict=True))
    assert torch.allclose(unordered(first_features), unordered(second_features))


def test_feature_version_twelve_binds_visible_stats_to_selected_field_slot():
    vocabulary = CardVocabulary((10, 20))
    first = replace(view(), field=(
        CardView(1, "monster", "faceup", 20, 0, "attack", 1600, 1000),
        CardView(1, "monster", "faceup", 20, 1, "attack", 1900, 1000),
    ))
    swapped = replace(first, field=(
        replace(first.field[0], attack=1900),
        replace(first.field[1], attack=1600),
    ))
    choices = (
        Action("slot-0", "select_card", 0,
               {"code": 20, "controller": 1, "location": 4, "sequence": 0}),
        Action("slot-1", "select_card", 0,
               {"code": 20, "controller": 1, "location": 4, "sequence": 1}),
    )
    torch.manual_seed(12)
    old_model = LegalActionPolicy(vocabulary.size, width=16, feature_version=10)
    torch.manual_seed(12)
    model = LegalActionPolicy(vocabulary.size, width=16, feature_version=12)
    assert all(torch.equal(left, right) for left, right in zip(
        old_model.parameters(), model.parameters(), strict=True))
    before = encode_decision(first, choices, vocabulary, feature_version=12)
    after = encode_decision(swapped, choices, vocabulary, feature_version=12)
    assert before.action_field_slots.tolist() == [[2, 2, 0], [2, 2, 1]]
    assert before.state_card_sequences.tolist() == [-1, 0, 1]
    assert torch.allclose(old_model(before), old_model(after))
    assert not torch.allclose(model(before), model(after))
    selected = (Action("multi-slot", "select_cards", 0, {"cards": [
        {"code": 20, "controller": 1, "location": 4, "sequence": 0}]}),)
    multi_before = encode_decision(first, selected, vocabulary, feature_version=12)
    multi_after = encode_decision(swapped, selected, vocabulary, feature_version=12)
    assert multi_before.action_field_slots.tolist() == [[0, 0, -1]]
    assert multi_before.action_multi_field_slots.tolist() == [[[2, 2, 0]]]
    assert torch.allclose(old_model(multi_before), old_model(multi_after))
    assert not torch.allclose(model(multi_before), model(multi_after))


def test_feature_version_twelve_uses_only_visible_field_cards():
    vocabulary = CardVocabulary((10, 20))
    observation = replace(view(), field=(
        CardView(1, "monster", "facedown", None, 0, "defense"),
        CardView(1, "monster", "facedown", None, 1, "defense"),
    ))
    choices = (Action("a", "select_card", 0,
                      {"controller": 1, "location": 4, "sequence": 0}),)
    features = encode_decision(observation, choices, vocabulary, feature_version=12)
    assert features.state_cards[1:3, 0].tolist() == [0, 0]
    assert features.action_cards.tolist() == [0]
    assert features.action_field_slots.tolist() == [[2, 2, 0]]
    known = replace(observation, known_opponent_field_cards=(
        KnownCardView(1, "monster", 0, 20),))
    known_features = encode_decision(known, choices, vocabulary, feature_version=12)
    assert known_features.state_cards[1:3, 0].tolist() == [vocabulary.index(20), 0]
    assert known_features.action_cards.tolist() == [vocabulary.index(20)]
    assert LegalActionPolicy(vocabulary.size, width=16, feature_version=12)(features).shape == (1,)


def test_feature_version_thirteen_binds_public_equip_to_monster_slot():
    vocabulary = CardVocabulary((10, 20, 30, 40))
    first = replace(view(), field=(
        CardView(0, "monster", "faceup", 20, 0, "attack", 1600, 1000),
        CardView(0, "monster", "faceup", 30, 1, "attack", 1900, 1000),
        CardView(0, "spell_trap", "faceup", 40, 0, equipped_to=(0, 0)),
    ))
    moved = replace(first, field=(*first.field[:2],
                                  replace(first.field[2], equipped_to=(0, 1))))
    choices = (Action("end", "end_phase", 0),)
    old_first = encode_decision(first, choices, vocabulary, feature_version=12)
    old_moved = encode_decision(moved, choices, vocabulary, feature_version=12)
    assert all(torch.equal(a, b) for a, b in zip(
        old_first.__dict__.values(), old_moved.__dict__.values(), strict=True))
    current_first = encode_decision(first, choices, vocabulary, feature_version=13)
    current_moved = encode_decision(moved, choices, vocabulary, feature_version=13)
    assert current_first.state_equip_slots.tolist() == [
        [0, 0, -1], [0, 0, -1], [0, 0, -1], [1, 2, 0]]
    assert current_moved.state_equip_slots[-1].tolist() == [1, 2, 1]
    torch.manual_seed(13)
    old_model = LegalActionPolicy(vocabulary.size, width=16, feature_version=12)
    torch.manual_seed(13)
    model = LegalActionPolicy(vocabulary.size, width=16, feature_version=13)
    for name, parameter in old_model.named_parameters():
        assert torch.equal(parameter, dict(model.named_parameters())[name])
    assert not torch.allclose(model(current_first), model(current_moved))
    model(current_first).sum().backward()
    assert any(parameter.grad is not None and parameter.grad.abs().sum() > 0
               for parameter in model.equip_pair.parameters())
    assert torch.allclose(old_model(old_first), old_model(old_moved))


def test_feature_version_fourteen_binds_public_chain_target_to_visible_slot():
    vocabulary = CardVocabulary((10, 20, 30))
    base = replace(view(), field=(
        CardView(1, "monster", "facedown", None, 0, "defense"),
        CardView(1, "monster", "faceup", 20, 1, "attack", 1600, 1000),
    ))
    first = replace(base, chain=(ChainLinkView(
        1, 30, 0, 8, 0, (TargetSlotView(1, "monster", 0),)),))
    second = replace(base, chain=(ChainLinkView(
        1, 30, 0, 8, 0, (TargetSlotView(1, "monster", 1),)),))
    choices = (Action("pass", "pass", 0),)
    older_first = encode_decision(first, choices, vocabulary, feature_version=13)
    older_second = encode_decision(second, choices, vocabulary, feature_version=13)
    assert torch.equal(older_first.chain_target_slots, older_second.chain_target_slots)
    current_first = encode_decision(first, choices, vocabulary, feature_version=14)
    current_second = encode_decision(second, choices, vocabulary, feature_version=14)
    empty_chain = encode_decision(base, choices, vocabulary, feature_version=14)
    assert empty_chain.chain_target_slots.tolist() == [[[0, 0, -1]]]
    untargeted = encode_decision(replace(base, chain=(ChainLinkView(1, 30, 0, 8, 0),)),
                                 choices, vocabulary, feature_version=14)
    assert untargeted.chain_target_slots.tolist() == [[[0, 0, -1]]]
    assert current_first.chain_target_slots.tolist() == [[[2, 2, 0]]]
    assert current_second.chain_target_slots.tolist() == [[[2, 2, 1]]]
    assert current_first.state_cards[1, 0].item() == 0  # Hidden opponent monster.
    torch.manual_seed(14)
    old_model = LegalActionPolicy(vocabulary.size, width=16, feature_version=13)
    torch.manual_seed(14)
    model = LegalActionPolicy(vocabulary.size, width=16, feature_version=14)
    for name, parameter in old_model.named_parameters():
        assert torch.equal(parameter, dict(model.named_parameters())[name])
    assert torch.allclose(old_model(older_first), old_model(older_second))
    assert not torch.allclose(model(current_first), model(current_second))
    assert model(empty_chain).shape == (1,)
    assert model(untargeted).shape == (1,)
    model(current_first).sum().backward()
    assert any(parameter.grad is not None and parameter.grad.abs().sum() > 0
               for parameter in model.chain_target_pair.parameters())


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


def test_behavioral_clone_minibatch_matches_mean_gradient():
    vocabulary = CardVocabulary((10, 20))
    records = (DecisionRecord(view(), actions(), actions()[0]),
               DecisionRecord(view(), actions(), actions()[1]))
    torch.manual_seed(72)
    expected = LegalActionPolicy(vocabulary.size, width=8)
    torch.manual_seed(72)
    actual = LegalActionPolicy(vocabulary.size, width=8)
    optimizer = torch.optim.Adam(expected.parameters(), lr=0.01)
    losses = []
    for record in records:
        features = encode_decision(record.observation, record.legal_actions,
                                   vocabulary, expected.feature_version)
        logits = expected(features).unsqueeze(0)
        target = torch.tensor([record.legal_actions.index(record.selected_action)])
        losses.append(torch.nn.functional.cross_entropy(logits, target))
    optimizer.zero_grad()
    torch.stack(losses).mean().backward()
    optimizer.step()
    reported = fit_behavioral_clone(actual, vocabulary, records, epochs=1,
                                    learning_rate=0.01, seed=72, batch_size=2)
    assert reported[0] == pytest.approx(torch.stack(losses).detach().mean().item())
    assert all(torch.allclose(a, b, atol=1e-6, rtol=1e-6)
               for a, b in zip(actual.parameters(), expected.parameters(), strict=True))
    with pytest.raises(ValueError, match="batch size"):
        fit_behavioral_clone(actual, vocabulary, records, batch_size=0)


def test_behavioral_clone_can_skip_forced_choices_without_changing_choice_updates():
    vocabulary = CardVocabulary((10, 20), ((10, 0x21, 300), (20, 0x21, 1000)))
    choices = actions()
    forced = DecisionRecord(view(), choices[:1], choices[0])
    selected = DecisionRecord(view(), choices, choices[1])
    torch.manual_seed(82)
    filtered = LegalActionPolicy(vocabulary.size, width=8, feature_version=23)
    torch.manual_seed(82)
    reference = LegalActionPolicy(vocabulary.size, width=8, feature_version=23)
    filtered_losses = fit_behavioral_clone(
        filtered, vocabulary, (forced, selected), epochs=2, learning_rate=0.01,
        batch_size=2, batched_forward=True, sampling_weights=(100.0, 1.0),
        skip_forced=True)
    reference_losses = fit_behavioral_clone(
        reference, vocabulary, (selected,), epochs=2, learning_rate=0.01,
        batch_size=2, batched_forward=True, sampling_weights=(1.0,))
    assert filtered_losses == reference_losses
    assert all(torch.equal(left, right) for left, right in zip(
        filtered.parameters(), reference.parameters(), strict=True))
    with pytest.raises(ValueError, match="multi-option decision"):
        fit_behavioral_clone(filtered, vocabulary, (forced,), skip_forced=True)


def test_behavioral_clone_omits_forced_forward_preserving_update_schedule(monkeypatch):
    vocabulary = CardVocabulary((10, 20), ((10, 0x21, 300), (20, 0x21, 1000)))
    choices = actions()
    forced = DecisionRecord(view(), choices[:1], choices[0])
    selected = DecisionRecord(view(), choices, choices[1])
    records = (forced, selected, forced, forced, selected, forced)
    torch.manual_seed(87)
    reference = LegalActionPolicy(vocabulary.size, width=8, feature_version=23)
    torch.manual_seed(87)
    optimized = LegalActionPolicy(vocabulary.size, width=8, feature_version=23)
    settings = {"epochs": 3, "learning_rate": 0.01, "seed": 87,
                "batch_size": 3, "batched_forward": True}
    adam = torch.optim.Adam
    updates = []

    class CountingAdam(adam):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            updates.append(0)

        def step(self, *args, **kwargs):
            updates[-1] += 1
            return super().step(*args, **kwargs)

    monkeypatch.setattr(torch.optim, "Adam", CountingAdam)
    reference_losses = fit_behavioral_clone(reference, vocabulary, records, **settings)
    optimized_losses = fit_behavioral_clone(
        optimized, vocabulary, records, omit_forced_forward=True, **settings)
    assert updates == [6, 6]
    assert optimized_losses == pytest.approx(reference_losses, abs=1e-6)
    # Batched floating-point order changes when forced rows leave the forward,
    # so equal updates and losses do not imply bit-identical Adam parameters.
    assert any(not torch.equal(left, right) for left, right in zip(
        reference.parameters(), optimized.parameters(), strict=True))
    with pytest.raises(ValueError, match="requires batched forward"):
        fit_behavioral_clone(optimized, vocabulary, records,
                             omit_forced_forward=True)
    with pytest.raises(ValueError, match="requires batched forward"):
        fit_behavioral_clone(optimized, vocabulary, records,
                             batched_forward=True, skip_forced=True,
                             omit_forced_forward=True)
    torch.manual_seed(88)
    forced_reference = LegalActionPolicy(vocabulary.size, width=8, feature_version=23)
    torch.manual_seed(88)
    forced_optimized = LegalActionPolicy(vocabulary.size, width=8, feature_version=23)
    assert fit_behavioral_clone(forced_reference, vocabulary, (forced,) * 3,
                                batch_size=3, batched_forward=True) == (0.0,)
    assert fit_behavioral_clone(forced_optimized, vocabulary, (forced,) * 3,
                                batch_size=3, batched_forward=True,
                                omit_forced_forward=True) == (0.0,)
    assert all(torch.equal(left, right) for left, right in zip(
        forced_reference.parameters(), forced_optimized.parameters(), strict=True))


@pytest.mark.parametrize("version", (10, 13, 23, 25))
def test_padded_forward_matches_variable_length_single_decisions(version):
    vocabulary = CardVocabulary((10, 20), ((10, 0x21, 300), (20, 0x21, 1000)))
    first = encode_decision(view(), actions(), vocabulary, version)
    second_view = replace(
        view(), hand=(CardView(0, "hand", "hidden", 10, 0),
                      CardView(0, "hand", "hidden", 20, 1)),
        chain=(ChainLinkView(1, 20, 1, 8, 0),
               ChainLinkView(2, 10, 0, 8, 0)))
    second_actions = actions()[:2]
    second = encode_decision(second_view, second_actions, vocabulary, version)
    torch.manual_seed(79)
    model = LegalActionPolicy(vocabulary.size, width=8, feature_version=version)
    batched, mask = model.forward_batch((first, second))
    assert mask.tolist() == [[True, True, True], [True, True, False]]
    assert torch.allclose(batched[0, :3], model(first), atol=1e-6, rtol=1e-6)
    assert torch.allclose(batched[1, :2], model(second), atol=1e-6, rtol=1e-6)
    assert batched[1, 2] < -1e8


def test_batched_forward_clone_matches_single_forward_update():
    vocabulary = CardVocabulary((10, 20), ((10, 0x21, 300), (20, 0x21, 1000)))
    records = (
        DecisionRecord(view(), actions(), actions()[0]),
        DecisionRecord(replace(view(), chain=(ChainLinkView(1, 20, 1, 8, 0),)),
                       actions()[:2], actions()[1]),
    )
    torch.manual_seed(91)
    baseline = LegalActionPolicy(vocabulary.size, width=8, feature_version=23)
    torch.manual_seed(91)
    batched = LegalActionPolicy(vocabulary.size, width=8, feature_version=23)
    features = [encode_decision(record.observation, record.legal_actions,
                                vocabulary, 23) for record in records]
    single_losses = [torch.nn.functional.cross_entropy(
        baseline(feature).unsqueeze(0), torch.tensor([target]))
        for feature, target in zip(features, (0, 1), strict=True)]
    torch.stack(single_losses).mean().backward()
    batch_logits, _ = batched.forward_batch(features)
    torch.nn.functional.cross_entropy(batch_logits, torch.tensor([0, 1])).backward()
    assert all(torch.allclose(left.grad, right.grad, atol=1e-6, rtol=1e-5)
               for left, right in zip(baseline.parameters(), batched.parameters(),
                                      strict=True))
    original_loss = fit_behavioral_clone(baseline, vocabulary, records,
                                         batch_size=2, learning_rate=0.01, seed=91)
    batched_loss = fit_behavioral_clone(batched, vocabulary, records,
                                        batch_size=2, batched_forward=True,
                                        learning_rate=0.01, seed=91)
    assert batched_loss == pytest.approx(original_loss, abs=1e-6)


def test_behavioral_clone_weighted_sampling_keeps_update_count_and_is_reproducible():
    vocabulary = CardVocabulary((10, 20))
    records = (DecisionRecord(view(), actions(), actions()[0]),
               DecisionRecord(view(), actions(), actions()[1]))
    torch.manual_seed(72)
    weighted = LegalActionPolicy(vocabulary.size, width=8)
    torch.manual_seed(72)
    expected = LegalActionPolicy(vocabulary.size, width=8)
    sampled = (records[1], records[1])
    weighted_loss = fit_behavioral_clone(weighted, vocabulary, records, epochs=1,
                                         learning_rate=0.01, seed=72, batch_size=2,
                                         sampling_weights=(1.0, 100.0))
    expected_loss = fit_behavioral_clone(expected, vocabulary, sampled, epochs=1,
                                         learning_rate=0.01, seed=72, batch_size=2)
    assert weighted_loss == expected_loss
    assert all(torch.equal(a, b) for a, b in zip(
        weighted.parameters(), expected.parameters(), strict=True))
    for bad_weights in ((1.0,), (1.0, float("nan")), (1.0, 0.0)):
        with pytest.raises(ValueError, match="sampling weights"):
            fit_behavioral_clone(weighted, vocabulary, records,
                                 sampling_weights=bad_weights)


def test_warm_start_restores_weights_and_requires_heldout_provenance(tmp_path):
    vocabulary = CardVocabulary((10, 20))
    parent_model = LegalActionPolicy(vocabulary.size, width=16, feature_version=17)
    checkpoint = {
        "schema_version": 1, "model_state": parent_model.state_dict(),
        "vocabulary_codes": vocabulary.codes, "width": 16, "feature_version": 17,
        "trajectory_sha256": {"training.json": "a" * 64},
        "training_games": [{"seed": 42, "deck_sha256": ("a", "b"),
                            "main_deck_composition_sha256": ("c", "d")}],
    }
    path = tmp_path / "parent.pt"
    torch.save(checkpoint, path)
    child = LegalActionPolicy(vocabulary.size, width=16, feature_version=17)
    with torch.no_grad():
        child.card.weight.fill_(0)
    assert not torch.equal(child.card.weight, parent_model.card.weight)
    loaded = load_parent_checkpoint(path, child, vocabulary)
    assert loaded["training_games"] == checkpoint["training_games"]
    assert torch.equal(child.card.weight, parent_model.card.weight)

    for model, codes in (
        (LegalActionPolicy(vocabulary.size, width=8, feature_version=17), vocabulary),
        (LegalActionPolicy(vocabulary.size, width=16, feature_version=16), vocabulary),
        (LegalActionPolicy(4, width=16, feature_version=17), CardVocabulary((10, 30))),
    ):
        with pytest.raises(ValueError, match="architecture or vocabulary"):
            load_parent_checkpoint(path, model, codes)

    checkpoint["training_games"] = [{"seed": 42}]
    torch.save(checkpoint, path)
    with pytest.raises(ValueError, match="held-out training provenance"):
        load_parent_checkpoint(path, child, vocabulary)
    checkpoint["training_games"] = loaded["training_games"]
    checkpoint.pop("trajectory_sha256")
    torch.save(checkpoint, path)
    with pytest.raises(TypeError, match="trajectory hashes"):
        load_parent_checkpoint(path, child, vocabulary)


def test_v23_to_v24_upgrade_zero_extends_only_trade_feature_weights(tmp_path):
    vocabulary = CardVocabulary((10,), ((10, 0, 0),))
    parent = LegalActionPolicy(vocabulary.size, width=8, feature_version=23)
    checkpoint = {
        "schema_version": 1, "model_state": parent.state_dict(),
        "vocabulary_codes": vocabulary.codes,
        "vocabulary_card_properties": vocabulary.card_properties,
        "width": 8, "feature_version": 23,
        "trajectory_sha256": {"training.json": "a" * 64},
        "training_games": [{"seed": 42, "deck_sha256": ("a", "b"),
                            "main_deck_composition_sha256": ("c", "d")}],
    }
    path = tmp_path / "parent.pt"
    torch.save(checkpoint, path)
    child = LegalActionPolicy(vocabulary.size, width=8, feature_version=24)
    with pytest.raises(ValueError, match="architecture or vocabulary"):
        load_parent_checkpoint(path, child, vocabulary)
    load_parent_checkpoint(path, child, vocabulary, allow_v23_to_v24=True)
    assert torch.equal(child.action_numbers[0].weight[:, :101],
                       parent.action_numbers[0].weight)
    assert torch.count_nonzero(child.action_numbers[0].weight[:, 101:]) == 0
    for key, tensor in parent.state_dict().items():
        if key != "action_numbers.0.weight":
            assert torch.equal(child.state_dict()[key], tensor)
    with torch.no_grad():
        old_logits = parent(encode_decision(view(), actions(), vocabulary,
                                            feature_version=23))
        upgraded_logits = child(encode_decision(view(), actions(), vocabulary,
                                                feature_version=24))
    assert torch.allclose(old_logits, upgraded_logits, atol=1e-6)


def test_v25_trade_head_starts_at_parent_logits_and_can_price_visible_trade(tmp_path):
    codes = tuple(sorted((10, HEAVY_STORM)))
    vocabulary = CardVocabulary(codes, tuple((code, 0, 0) for code in codes))
    parent = LegalActionPolicy(vocabulary.size, width=8, feature_version=23)
    checkpoint = {
        "schema_version": 1, "model_state": parent.state_dict(),
        "vocabulary_codes": vocabulary.codes,
        "vocabulary_card_properties": vocabulary.card_properties,
        "width": 8, "feature_version": 23,
        "trajectory_sha256": {"training.json": "a" * 64},
        "training_games": [{"seed": 42, "deck_sha256": ("a", "b"),
                            "main_deck_composition_sha256": ("c", "d")}],
    }
    path = tmp_path / "parent.pt"
    torch.save(checkpoint, path)
    child = LegalActionPolicy(vocabulary.size, width=8, feature_version=25)
    with pytest.raises(ValueError, match="architecture or vocabulary"):
        load_parent_checkpoint(path, child, vocabulary)
    load_parent_checkpoint(path, child, vocabulary, allow_v23_to_v25=True)
    assert torch.count_nonzero(child.trade_head.weight) == 0
    storm = Action("storm", "activate", 0, {"code": HEAVY_STORM})
    end = Action("end", "end_phase", 0)
    enemy = CardView(1, "spell_trap", "facedown", None, 0)
    own = CardView(0, "spell_trap", "facedown", 10, 0)
    good = replace(view(), field=(enemy, replace(enemy, sequence=1)))
    bad = replace(view(), field=(own,))
    for observation, margin in ((good, 1), (bad, -2)):
        old = encode_decision(observation, (storm, end), vocabulary, 23)
        new = encode_decision(observation, (storm, end), vocabulary, 25)
        with torch.no_grad():
            baseline = child(new)
            assert torch.allclose(parent(old), baseline, atol=1e-6)
            child.trade_head.weight[0, 0] = 1
            adjusted = child(new)
            child.trade_head.weight.zero_()
        assert (adjusted - baseline).tolist() == pytest.approx((margin, 0))
    checkpoint["feature_version"] = 25
    checkpoint["model_state"] = child.state_dict()
    torch.save(checkpoint, path)
    with pytest.raises(ValueError, match="feature-v23 parent"):
        load_parent_checkpoint(path, LegalActionPolicy(vocabulary.size, width=8,
                                                      feature_version=25), vocabulary,
                               allow_v23_to_v25=True)


def test_v26_separate_player_pool_loads_exact_v23_logits_and_batches(tmp_path):
    vocabulary = CardVocabulary((10, 20), ((10, 33, 300), (20, 33, 2000)))
    parent = LegalActionPolicy(vocabulary.size, width=8, feature_version=23)
    checkpoint = {
        "schema_version": 1, "model_state": parent.state_dict(),
        "vocabulary_codes": vocabulary.codes,
        "vocabulary_card_properties": vocabulary.card_properties,
        "width": 8, "feature_version": 23,
        "trajectory_sha256": {"training.json": "a" * 64},
        "training_games": [{"seed": 42, "deck_sha256": ("a", "b"),
                            "main_deck_composition_sha256": ("c", "d")}],
    }
    path = tmp_path / "parent.pt"
    torch.save(checkpoint, path)
    child = LegalActionPolicy(vocabulary.size, width=8, feature_version=26)
    with pytest.raises(ValueError, match="architecture or vocabulary"):
        load_parent_checkpoint(path, child, vocabulary)
    load_parent_checkpoint(path, child, vocabulary, allow_v23_to_v26=True)
    assert torch.count_nonzero(child.player_pool.weight) == 0
    assert all(torch.equal(child.state_dict()[key], value)
               for key, value in parent.state_dict().items())
    observation = replace(view(), field=(
        CardView(0, "monster", "faceup", 10, 0),
        CardView(1, "monster", "faceup", 20, 0),
    ))
    old = encode_decision(observation, actions(), vocabulary, 23)
    new = encode_decision(observation, actions(), vocabulary, 26)
    with torch.no_grad():
        expected = parent(old)
        actual = child(new)
        batched, mask = child.forward_batch((new, new))
    assert torch.allclose(actual, expected, atol=1e-6)
    assert torch.allclose(batched[0, mask[0]], actual, atol=1e-6)
    assert torch.allclose(batched[1, mask[1]], actual, atol=1e-6)
    checkpoint["feature_version"] = 26
    checkpoint["model_state"] = child.state_dict()
    torch.save(checkpoint, path)
    with pytest.raises(ValueError, match="feature-v23 parent"):
        load_parent_checkpoint(path, LegalActionPolicy(vocabulary.size, width=8,
                                                      feature_version=26), vocabulary,
                               allow_v23_to_v26=True)


def test_v27_action_attention_preserves_parent_logits_and_batches(tmp_path):
    vocabulary = CardVocabulary((10, 20), ((10, 33, 300), (20, 33, 2000)))
    parent = LegalActionPolicy(vocabulary.size, width=8, feature_version=23)
    checkpoint = {
        "schema_version": 1, "model_state": parent.state_dict(),
        "vocabulary_codes": vocabulary.codes,
        "vocabulary_card_properties": vocabulary.card_properties,
        "width": 8, "feature_version": 23,
        "trajectory_sha256": {"training.json": "a" * 64},
        "training_games": [{"seed": 42, "deck_sha256": ("a", "b"),
                            "main_deck_composition_sha256": ("c", "d")}],
    }
    path = tmp_path / "parent.pt"
    torch.save(checkpoint, path)
    child = LegalActionPolicy(vocabulary.size, width=8, feature_version=27)
    with pytest.raises(ValueError, match="architecture or vocabulary"):
        load_parent_checkpoint(path, child, vocabulary)
    load_parent_checkpoint(path, child, vocabulary, allow_v23_to_v27=True)
    assert torch.count_nonzero(child.attended_card.weight) == 0
    assert all(torch.equal(child.state_dict()[key], value)
               for key, value in parent.state_dict().items())
    observation = replace(view(), field=(
        CardView(0, "monster", "faceup", 10, 0),
        CardView(1, "monster", "faceup", 20, 0),
    ))
    old = encode_decision(observation, actions(), vocabulary, 23)
    new = encode_decision(observation, actions(), vocabulary, 27)
    with torch.no_grad():
        expected = parent(old)
        actual = child(new)
        batched, mask = child.forward_batch((new, new))
    assert torch.allclose(actual, expected, atol=1e-6)
    assert torch.allclose(batched[0, mask[0]], actual, atol=1e-6)
    assert torch.allclose(batched[1, mask[1]], actual, atol=1e-6)
    shorter = encode_decision(view(), actions()[:2], vocabulary, 27)
    with torch.no_grad():
        child.attended_card.weight.copy_(torch.eye(8))
        full_logits = child(new)
        short_logits = child(shorter)
        padded, padded_mask = child.forward_batch((new, shorter))
    assert torch.allclose(padded[0, padded_mask[0]], full_logits, atol=1e-6)
    assert torch.allclose(padded[1, padded_mask[1]], short_logits, atol=1e-6)
    assert not padded_mask[1, -1]
    empty = encode_decision(replace(view(), hand=(), field=()),
                            actions()[-1:], vocabulary, 27)
    with torch.no_grad():
        assert torch.isfinite(child(empty)).all()
        padded_empty, empty_mask = child.forward_batch((new, empty))
    assert torch.allclose(padded_empty[1, empty_mask[1]], child(empty), atol=1e-6)
    checkpoint["feature_version"] = 27
    checkpoint["model_state"] = child.state_dict()
    torch.save(checkpoint, path)
    with pytest.raises(ValueError, match="feature-v23 parent"):
        load_parent_checkpoint(path, LegalActionPolicy(vocabulary.size, width=8,
                                                      feature_version=27), vocabulary,
                               allow_v23_to_v27=True)


def test_v28_counter_amounts_are_distinct_and_v23_warm_start_preserves_logits(tmp_path):
    vocabulary = CardVocabulary((10, 20), ((10, 4, 0), (20, 33, 2000)))
    observation = replace(view(), field=(
        CardView(0, "spell_trap", "faceup", 10, 0, counters=((1, 3),)),
        CardView(0, "spell_trap", "faceup", 10, 1, counters=((1, 3),)),
    ))
    first = {"controller": 0, "location": 8, "sequence": 0, "code": 10}
    second = {**first, "sequence": 1}
    choices = (Action("a", "select_counters", 0, {
        "cards": [{**first, "amount": 1}, {**second, "amount": 2}],
        "counter_type": 1, "counter_total": 3}),
        Action("b", "select_counters", 0, {
            "cards": [{**first, "amount": 2}, {**second, "amount": 1}],
            "counter_type": 1, "counter_total": 3}))
    old = encode_decision(observation, choices, vocabulary, 23)
    new = encode_decision(observation, choices, vocabulary, 28)
    assert torch.equal(old.action_target_context[0], old.action_target_context[1])
    assert new.action_target_context.shape == (2, 2, 7)
    assert new.action_target_context[0, :, -1].tolist() == pytest.approx([
        math.log1p(1) / math.log1p(32767), math.log1p(2) / math.log1p(32767)])
    assert not torch.equal(new.action_target_context[0], new.action_target_context[1])
    assert new.action_numbers.shape == (2, 103)
    assert new.action_numbers[0, -2:].tolist() == pytest.approx(
        [1 / 65535, math.log1p(3) / math.log1p(32767)])
    assert new.action_kinds.tolist() == [new.action_kinds[0].item()] * 2
    assert new.action_kinds[0] > 0

    staged = (Action("zero", "select_counters", 0, {
        "cards": [{**first, "amount": 0}], "counter_type": 1,
        "counter_total": 3, "counter_stage": True, "counter_index": 0,
        "counter_card_count": 2, "counter_remaining": 3}),
        Action("one", "select_counters", 0, {
            "cards": [{**first, "amount": 1}], "counter_type": 1,
            "counter_total": 3, "counter_stage": True, "counter_index": 0,
            "counter_card_count": 2, "counter_remaining": 2}))
    staged_features = encode_decision(observation, staged, vocabulary, 28)
    assert staged_features.action_target_context[0, 0, -1] == 0
    assert staged_features.action_target_context[1, 0, -1] > 0

    parent = LegalActionPolicy(vocabulary.size, width=8, feature_version=23)
    checkpoint = {"schema_version": 1, "model_state": parent.state_dict(),
                  "vocabulary_codes": vocabulary.codes,
                  "vocabulary_card_properties": vocabulary.card_properties,
                  "width": 8, "feature_version": 23,
                  "trajectory_sha256": {"training.json": "a" * 64},
                  "training_games": [{"seed": 42, "deck_sha256": ("a", "b"),
                                      "main_deck_composition_sha256": ("c", "d")}]}
    path = tmp_path / "parent.pt"
    torch.save(checkpoint, path)
    child = LegalActionPolicy(vocabulary.size, width=8, feature_version=28)
    with pytest.raises(ValueError, match="architecture or vocabulary"):
        load_parent_checkpoint(path, child, vocabulary)
    load_parent_checkpoint(path, child, vocabulary, allow_v23_to_v28=True)
    assert torch.count_nonzero(child.kind.weight[-1]) == 0
    assert torch.count_nonzero(child.target_context[0].weight[:, -1]) == 0
    assert torch.count_nonzero(child.action_numbers[0].weight[:, -2:]) == 0
    old_ordinary = encode_decision(observation, actions(), vocabulary, 23)
    new_ordinary = encode_decision(observation, actions(), vocabulary, 28)
    with torch.no_grad():
        expected = parent(old_ordinary)
        actual = child(new_ordinary)
        batched, mask = child.forward_batch((new_ordinary, new))
    assert torch.allclose(actual, expected, atol=1e-6)
    assert torch.allclose(batched[0, mask[0]], actual, atol=1e-6)
    assert torch.allclose(batched[1, mask[1]], child(new), atol=1e-6)


def test_v29_warm_start_preserves_v23_logits_and_zeros_age_weight(tmp_path):
    vocabulary = CardVocabulary((10, 20), ((10, 0, 1000), (20, 0, 2000)))
    parent = LegalActionPolicy(vocabulary.size, width=8, feature_version=23)
    path = tmp_path / "parent.pt"
    torch.save({"schema_version": 1, "model_state": parent.state_dict(),
                "vocabulary_codes": vocabulary.codes,
                "vocabulary_card_properties": vocabulary.card_properties,
                "width": 8, "feature_version": 23,
                "trajectory_sha256": {"training.json": "a" * 64},
                "training_games": [{"seed": 42, "deck_sha256": ("a", "b"),
                                    "main_deck_composition_sha256": ("c", "d")}]}, path)
    child = LegalActionPolicy(vocabulary.size, width=8, feature_version=29)
    load_parent_checkpoint(path, child, vocabulary, allow_v23_to_v29=True)
    assert torch.count_nonzero(child.card_numbers[0].weight[:, -1]) == 0
    visible = replace(view(), field=(CardView(
        0, "monster", "faceup", 20, 0, "attack", 1900, 1000,
        faceup_turns=2),))
    with torch.no_grad():
        expected = parent(encode_decision(visible, actions(), vocabulary, 23))
        actual = child(encode_decision(visible, actions(), vocabulary, 29))
    assert torch.allclose(actual, expected, atol=1e-6)


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


def test_version_eight_checkpoint_ignores_known_opponent_hand(tmp_path):
    vocabulary = CardVocabulary((10, 20))
    model = LegalActionPolicy(vocabulary.size, width=16, feature_version=8)
    checkpoint = tmp_path / "v8.pt"
    torch.save({"schema_version": 1, "model_state": model.state_dict(),
                "vocabulary_codes": vocabulary.codes, "width": 16,
                "feature_version": 8}, checkpoint)
    restored = load_policy_agent(checkpoint)
    known = replace(view(), known_opponent_hand_cards=(20,))
    unknown = replace(view(), known_opponent_hand_cards=())
    assert restored.model.feature_version == 8
    assert torch.equal(
        restored.model(encode_decision(known, actions(), vocabulary, 8)),
        restored.model(encode_decision(unknown, actions(), vocabulary, 8)))


def test_evaluation_rejects_training_seed_overlap():
    checkpoint = {"training_games": [{"seed": 42}]}
    validate_heldout_seeds(checkpoint, [43, 44])
    with pytest.raises(ValueError, match="overlap"):
        validate_heldout_seeds(checkpoint, [42, 43])
    with pytest.raises(ValueError, match="provenance"):
        validate_heldout_seeds({}, [43])


def test_evaluation_deck_hash_gate_rejects_training_file_bytes(tmp_path):
    training = tmp_path / "training.ydk"
    identical = tmp_path / "same_cards_elsewhere.ydk"
    unseen = tmp_path / "unseen.ydk"
    training.write_text("#main\n123\n")
    identical.write_bytes(training.read_bytes())
    unseen.write_text("#main\n456\n")
    from scripts.evaluate_policy import sha256

    checkpoint = {"training_games": [{"deck_sha256": (sha256(training), sha256(unseen))}]}
    with pytest.raises(ValueError, match="overlaps training"):
        validate_unseen_deck_hashes(checkpoint, [[str(identical), str(unseen)]])
    another = tmp_path / "another.ydk"
    another.write_text("#main\n789\n")
    validate_unseen_deck_hashes(checkpoint, [[str(another), str(another)]])
    with pytest.raises(ValueError, match="provenance"):
        validate_unseen_deck_hashes({"training_games": [{"seed": 1}]},
                                    [[str(another), str(another)]])


def test_evaluation_main_deck_gate_rejects_reordered_list(tmp_path):
    from goat_ai.engine.decks import main_deck_composition_sha256, read_ydk

    training = tmp_path / "training.ydk"
    reordered = tmp_path / "reordered.ydk"
    unseen = tmp_path / "unseen.ydk"
    training.write_text("#main\n123\n456\n123\n")
    reordered.write_text("#new comment\n#main\n456\n123\n123\n")
    unseen.write_text("#main\n123\n456\n456\n")
    checkpoint = {"training_games": [{"main_deck_composition_sha256": (
        main_deck_composition_sha256(read_ydk(training)), "other")}]}
    with pytest.raises(ValueError, match="overlaps training"):
        validate_unseen_main_decks(checkpoint, [[str(reordered), str(unseen)]])
    validate_unseen_main_decks(checkpoint, [[str(unseen), str(unseen)]])
    with pytest.raises(ValueError, match="provenance"):
        validate_unseen_main_decks({"training_games": [{"deck_sha256": ("a", "b")}]},
                                   [[str(unseen), str(unseen)]])


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
    for temperature in (1.0, 2.0):
        for reward, direction in ((1.0, 1), (-1.0, -1)):
            torch.manual_seed(8)
            model = LegalActionPolicy(vocabulary.size, width=16)
            optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
            before = torch.softmax(model(features) / temperature, 0)[1].item()
            policy_gradient_update(model, vocabulary, [record], reward, 0.0,
                                   optimizer, temperature=temperature)
            after = torch.softmax(model(features) / temperature, 0)[1].item()
            assert (after - before) * direction > 0
    with pytest.raises(ValueError, match="temperature"):
        policy_gradient_update(model, vocabulary, [record], 1.0, 0.0,
                               optimizer, temperature=0)
    generator = torch.Generator().manual_seed(9)
    assert sample_legal_action(model, vocabulary, view(), actions(), generator) in actions()


def test_forced_self_play_action_skips_inference_and_sampling(monkeypatch):
    vocabulary = CardVocabulary((10, 20))
    model = LegalActionPolicy(vocabulary.size, width=16)
    forced = actions()[:1]
    generator = torch.Generator().manual_seed(9)
    before = generator.get_state().clone()

    def unexpected_forward(*_args, **_kwargs):
        pytest.fail("forced action should not run the policy")

    monkeypatch.setattr(model, "forward", unexpected_forward)
    assert sample_legal_action(model, vocabulary, view(), forced, generator) == forced[0]
    assert torch.equal(generator.get_state(), before)
    with pytest.raises(ValueError, match="temperature"):
        sample_legal_action(model, vocabulary, view(), forced, generator, temperature=0)


def test_sampled_selection_uses_same_progress_mask_as_training_features():
    vocabulary = CardVocabulary((10, 20))
    model = LegalActionPolicy(vocabulary.size, width=16)
    selected = Action("undo", "unselect_card", 0, {"code": 10, "sequence": 0})
    add = Action("add", "select_card", 0, {"code": 20, "sequence": 1})
    finish = Action("finish", "finish_selection", 0)
    legal = (selected, add, finish)
    assert _selection_progress_actions(legal) == (add, finish)
    assert _selection_progress_actions((selected,)) == (selected,)
    for seed in range(20):
        action, features, policy_actions = _sample_legal_action_with_features(
            model, vocabulary, view(), legal, torch.Generator().manual_seed(seed))
        assert action in (add, finish)
        assert policy_actions == (add, finish)
        assert features is not None and len(features.action_kinds) == 2
        assert DecisionRecord(view(), policy_actions, action).selected_action == action


def test_forced_greedy_action_skips_inference(monkeypatch):
    vocabulary = CardVocabulary((10, 20))
    model = LegalActionPolicy(vocabulary.size, width=16)
    forced = actions()[:1]

    def unexpected_forward(*_args, **_kwargs):
        pytest.fail("forced action should not run the policy")

    monkeypatch.setattr(model, "forward", unexpected_forward)
    assert PolicyAgent(model, vocabulary).select_action(view(), forced) == forced[0]


def test_ppo_clipped_surrogate_handles_both_advantage_signs():
    ratio = torch.tensor([1.5, 0.5])
    advantage = torch.tensor([1.0, -1.0])
    assert torch.allclose(clipped_surrogate(ratio, advantage, 0.2),
                          torch.tensor([1.2, -0.8]))
    with pytest.raises(ValueError, match="clip epsilon"):
        clipped_surrogate(ratio, advantage, 0)


def test_ppo_update_uses_visible_variable_action_sets_and_terminal_reward():
    vocabulary = CardVocabulary((10, 20))
    choices = actions()
    records = (
        DecisionRecord(view(), choices, choices[1]),
        DecisionRecord(replace(view(), chain=(ChainLinkView(1, 20, 1, 8, 0),)),
                       choices[:2], choices[1]),
    )
    for reward, direction in ((1.0, 1), (-1.0, -1)):
        torch.manual_seed(44)
        policy = LegalActionPolicy(vocabulary.size, width=8, feature_version=10)
        features = encode_decision(view(), choices, vocabulary, 10)
        before = torch.softmax(policy(features), 0)[1].item()
        optimizer = torch.optim.SGD(policy.parameters(), lr=0.01)
        loss = ppo_clipped_update(policy, vocabulary, records, reward, 0.0,
                                  optimizer, epochs=2, batch_size=2,
                                  entropy_coefficient=0, random_seed=44)
        after = torch.softmax(policy(features), 0)[1].item()
        assert isinstance(loss, float)
        assert (after - before) * direction > 0
    with pytest.raises(ValueError, match="state baselines"):
        ppo_clipped_update(policy, vocabulary, records, 1.0, 0.0,
                           optimizer, state_baselines=(0.0,))
    with pytest.raises(ValueError, match="advantages"):
        ppo_clipped_update(policy, vocabulary, records, 0.0, 0.0,
                           optimizer, advantages=(1.0,))
    with pytest.raises(ValueError, match="sample weights"):
        ppo_clipped_update(policy, vocabulary, records, 0.0, 0.0,
                           optimizer, sample_weights=(1.0, 0.0))


def test_ppo_update_accepts_mixed_rollout_advantages():
    vocabulary = CardVocabulary((10, 20))
    choices = actions()
    records = (DecisionRecord(view(), choices, choices[1]),
               DecisionRecord(view(), choices, choices[0]))
    torch.manual_seed(31)
    policy = LegalActionPolicy(vocabulary.size, width=8, feature_version=10)
    features = encode_decision(view(), choices, vocabulary, 10)
    before = torch.softmax(policy(features), 0)[1].item()
    optimizer = torch.optim.SGD(policy.parameters(), lr=0.01)
    ppo_clipped_update(policy, vocabulary, records, 0.0, 0.0, optimizer,
                       epochs=2, batch_size=2, advantages=(1.0, -1.0))
    assert torch.softmax(policy(features), 0)[1].item() > before


def test_ppo_update_reuses_identical_visible_rollout_features(monkeypatch):
    vocabulary = CardVocabulary((10, 20))
    choices = actions()
    records = (DecisionRecord(view(), choices, choices[1]),
               DecisionRecord(replace(view(), chain=(ChainLinkView(1, 20, 1, 8, 0),)),
                              choices[:2], choices[0]))
    features = tuple(encode_decision(record.observation, record.legal_actions,
                                     vocabulary, 10) for record in records)
    torch.manual_seed(91)
    original = LegalActionPolicy(vocabulary.size, width=8, feature_version=10)
    reference = copy.deepcopy(original)
    candidate = copy.deepcopy(original)
    baseline_loss = ppo_clipped_update(
        reference, vocabulary, records, 1.0, 0.0,
        torch.optim.SGD(reference.parameters(), lr=0.01),
        epochs=2, batch_size=2, random_seed=91)

    def unexpected_encode(*_args, **_kwargs):
        pytest.fail("PPO update rebuilt a cached decision")

    monkeypatch.setattr("goat_ai.training.self_play.encode_decision", unexpected_encode)
    cached_loss = ppo_clipped_update(
        candidate, vocabulary, records, 1.0, 0.0,
        torch.optim.SGD(candidate.parameters(), lr=0.01),
        epochs=2, batch_size=2, random_seed=91, encoded_features=features)
    assert cached_loss == baseline_loss
    assert all(torch.equal(reference.state_dict()[key], candidate.state_dict()[key])
               for key in reference.state_dict())
    with pytest.raises(ValueError, match="encoded features"):
        ppo_clipped_update(candidate, vocabulary, records, 1.0, 0.0,
                           torch.optim.SGD(candidate.parameters(), lr=0.01),
                           encoded_features=features[:1])


def test_rollout_feature_reuse_rejects_incompatible_update_modes():
    vocabulary = CardVocabulary((10, 20))
    policy = LegalActionPolicy(vocabulary.size, width=8, feature_version=10)
    with pytest.raises(ValueError, match="single-process PPO"):
        train_against_snapshot_pool(policy, vocabulary, (("a", "b"),), (100,),
                                    lambda: None, reuse_rollout_features=True)
    with pytest.raises(ValueError, match="single-process PPO"):
        train_against_snapshot_pool(policy, vocabulary, (("a", "b"),), (100, 101),
                                    lambda: None, policy_update="clipped_ppo",
                                    ppo_rollout_games=2, rollout_workers=2,
                                    reuse_rollout_features=True)


def test_ppo_decision_weights_change_conflicting_updates():
    vocabulary = CardVocabulary((10, 20))
    choices = actions()
    records = (DecisionRecord(view(), choices, choices[1]),
               DecisionRecord(view(), choices, choices[0]))
    torch.manual_seed(36)
    initial = LegalActionPolicy(vocabulary.size, width=8, feature_version=10)
    probabilities = []
    for weights in ((3.0, 1.0), (1.0, 3.0)):
        policy = copy.deepcopy(initial)
        optimizer = torch.optim.SGD(policy.parameters(), lr=0.01)
        ppo_clipped_update(policy, vocabulary, records, 1.0, 0.0, optimizer,
                           epochs=1, batch_size=2, sample_weights=weights)
        features = encode_decision(view(), choices, vocabulary, 10)
        probabilities.append(torch.softmax(policy(features), 0)[1].item())
    assert probabilities[0] > probabilities[1]


def test_ppo_caches_frozen_parent_scores_across_epochs(monkeypatch):
    vocabulary = CardVocabulary((10, 20))
    choices = actions()
    records = tuple(DecisionRecord(view(), choices[:2 + index % 2],
                                   choices[index % 2]) for index in range(5))
    torch.manual_seed(85)
    policy = LegalActionPolicy(vocabulary.size, width=8, feature_version=10)
    parent = copy.deepcopy(policy).eval().requires_grad_(False)
    calls = 0
    original = parent.forward_batch

    def counted(features):
        nonlocal calls
        calls += 1
        return original(features)

    monkeypatch.setattr(parent, "forward_batch", counted)
    optimizer = torch.optim.SGD(policy.parameters(), lr=0.001)
    ppo_clipped_update(policy, vocabulary, records, 1.0, 0.0, optimizer,
                       epochs=3, batch_size=2, parent_model=parent,
                       parent_kl_weight=0.1)
    assert calls == 3  # one pass over five records, independent of PPO epochs


def test_policy_gradient_uses_sampling_temperature_in_log_probability():
    class TwoLogitPolicy(torch.nn.Module):
        feature_version = 1

        def __init__(self):
            super().__init__()
            self.logits = torch.nn.Parameter(torch.zeros(2))

        def forward(self, _features):
            return self.logits

    model = TwoLogitPolicy()
    optimizer = torch.optim.SGD(model.parameters(), lr=1.0)
    record = DecisionRecord(view(), actions(), actions()[1])
    policy_gradient_update(model, CardVocabulary((10, 20)), [record], 1.0, 0.0,
                           optimizer, temperature=2.0, max_gradient_norm=10.0)
    assert torch.allclose(model.logits.detach(), torch.tensor([-0.25, 0.25]))


def test_mean_policy_gradient_is_invariant_to_duplicate_decisions():
    class TwoLogitPolicy(torch.nn.Module):
        feature_version = 1

        def __init__(self):
            super().__init__()
            self.logits = torch.nn.Parameter(torch.zeros(2))

        def forward(self, _features):
            return self.logits

    record = DecisionRecord(view(), actions(), actions()[1])
    vocabulary = CardVocabulary((10, 20))
    results = {}
    for reduction, count in (("mean", 1), ("mean", 2), ("sum", 2)):
        model = TwoLogitPolicy()
        optimizer = torch.optim.SGD(model.parameters(), lr=1.0)
        policy_gradient_update(model, vocabulary, (record,) * count, 1.0, 0.0,
                               optimizer, max_gradient_norm=10.0,
                               reduction=reduction)
        results[(reduction, count)] = model.logits.detach().clone()
    assert torch.allclose(results[("mean", 1)], results[("mean", 2)])
    assert torch.allclose(results[("sum", 2)], 2 * results[("mean", 1)])
    with pytest.raises(ValueError, match="regularization"):
        policy_gradient_update(TwoLogitPolicy(), vocabulary, (record,), 1.0,
                               0.0, optimizer, reduction="unknown")


@pytest.mark.parametrize("reduction", ("sum", "mean"))
def test_batched_reinforce_matches_scalar_variable_action_update(reduction):
    vocabulary = CardVocabulary((10, 20))
    choices = actions()
    records = (DecisionRecord(view(), choices, choices[1]),
               DecisionRecord(view(), choices[:2], choices[0]),
               DecisionRecord(view(), choices, choices[2]),
               DecisionRecord(view(), choices[:1], choices[0]))
    torch.manual_seed(71)
    initial = LegalActionPolicy(vocabulary.size, width=8, feature_version=10)
    parent = copy.deepcopy(initial).eval().requires_grad_(False)
    with torch.no_grad():
        next(parent.parameters()).add_(0.1)
    results = []
    for batch_size in (1, 3):
        model = copy.deepcopy(initial)
        optimizer = torch.optim.SGD(model.parameters(), lr=0.001)
        loss = policy_gradient_update(
            model, vocabulary, records, 1.0, 0.0, optimizer,
            entropy_coefficient=0.02, max_gradient_norm=100,
            temperature=1.3, state_baselines=(0.1, 0.2, -0.1, 0.0),
            reduction=reduction, parent_model=parent,
            parent_kl_weight=0.1, batch_size=batch_size)
        results.append((loss, tuple(p.detach().clone() for p in model.parameters())))
    assert results[0][0] == pytest.approx(results[1][0], abs=1e-5)
    assert all(torch.allclose(left, right, atol=1e-5, rtol=1e-5)
               for left, right in zip(results[0][1], results[1][1]))


def test_batched_reinforce_rejects_unsupported_feature_version():
    vocabulary = CardVocabulary((10, 20))
    model = LegalActionPolicy(vocabulary.size, width=8, feature_version=1)
    optimizer = torch.optim.SGD(model.parameters(), lr=0.001)
    record = DecisionRecord(view(), actions(), actions()[0])
    with pytest.raises(ValueError, match="batched REINFORCE"):
        policy_gradient_update(model, vocabulary, (record,), 1.0, 0.0,
                               optimizer, batch_size=2)

    with pytest.raises(ValueError, match="batched REINFORCE"):
        train_against_snapshot_pool(model, vocabulary, (("a", "b"),), (1,),
                                    lambda: None, reinforce_batch_size=2)
    supported = LegalActionPolicy(vocabulary.size, width=8, feature_version=10)
    with pytest.raises(ValueError, match="batched REINFORCE"):
        train_against_snapshot_pool(supported, vocabulary, (("a", "b"),), (1,),
                                    lambda: None, policy_update="clipped_ppo",
                                    reinforce_batch_size=2)


def test_self_play_parent_kl_pulls_policy_toward_frozen_visible_teacher():
    class TwoLogitPolicy(torch.nn.Module):
        feature_version = 1

        def __init__(self, logits):
            super().__init__()
            self.logits = torch.nn.Parameter(torch.tensor(logits, dtype=torch.float32))

        def forward(self, _features):
            return self.logits

    vocabulary = CardVocabulary((10, 20))
    record = DecisionRecord(view(), actions(), actions()[1])
    policy = TwoLogitPolicy([2.0, 0.0])
    parent = TwoLogitPolicy([0.0, 0.0]).eval().requires_grad_(False)
    before = torch.softmax(policy.logits.detach(), 0)[0].item()
    optimizer = torch.optim.SGD(policy.parameters(), lr=1.0)
    policy_gradient_update(policy, vocabulary, (record,), 0.0, 0.0, optimizer,
                           max_gradient_norm=10.0, parent_model=parent,
                           parent_kl_weight=1.0)
    after = torch.softmax(policy.logits.detach(), 0)[0].item()
    assert 0.5 < after < before
    assert torch.allclose(parent.logits.detach(), torch.zeros(2))
    with pytest.raises(ValueError, match="parent KL"):
        policy_gradient_update(policy, vocabulary, (record,), 0.0, 0.0, optimizer,
                               parent_kl_weight=1.0)


def test_visible_value_baseline_scales_policy_gradient_and_ignores_action_order():
    class TwoLogitPolicy(torch.nn.Module):
        feature_version = 1

        def __init__(self):
            super().__init__()
            self.logits = torch.nn.Parameter(torch.zeros(2))

        def forward(self, _features):
            return self.logits

    vocabulary = CardVocabulary((10, 20))
    record = DecisionRecord(view(), actions(), actions()[1])
    policy = TwoLogitPolicy()
    optimizer = torch.optim.SGD(policy.parameters(), lr=1.0)
    policy_gradient_update(policy, vocabulary, [record], 1.0, 0.0, optimizer,
                           max_gradient_norm=10.0, state_baselines=(0.5,))
    assert torch.allclose(policy.logits.detach(), torch.tensor([-0.25, 0.25]))
    with pytest.raises(ValueError, match="state baselines"):
        policy_gradient_update(policy, vocabulary, [record], 1.0, 0.0, optimizer,
                               state_baselines=(float("nan"),))

    torch.manual_seed(42)
    value = VisibleStateValue(vocabulary.size, state_number_width=10, width=16)
    reversed_record = DecisionRecord(view(), actions()[::-1], actions()[1])
    before, reordered = predict_state_values(
        value, vocabulary, (record, reversed_record), feature_version=1)
    assert before == pytest.approx(reordered)
    assert -1 <= before <= 1
    value_optimizer = torch.optim.Adam(value.parameters(), lr=0.01)
    value_loss = state_value_update(value, vocabulary, (record,), 1.0, 1,
                                    value_optimizer)
    after = predict_state_values(value, vocabulary, (record,), 1)[0]
    assert value_loss >= 0
    assert after > before


def test_value_v2_uses_visible_stats_and_own_deck_without_action_order():
    vocabulary = CardVocabulary((10, 20), ((10, 0, 1000), (20, 0, 2000)))
    base = replace(view(),
                   field=(CardView(0, "monster", "faceup", 10, 0, "attack",
                                   attack=1000, defense=1000),),
                   own_main_deck=(10, 20))
    stronger = replace(base, field=(replace(base.field[0], attack=3000),))
    changed_deck = replace(base, own_main_deck=(10, 10))
    features = [encode_decision(observation, actions(), vocabulary, 23)
                for observation in (base, stronger, changed_deck)]
    torch.manual_seed(171)
    old = VisibleStateValue(vocabulary.size, features[0].state_numbers.numel(),
                            width=16)
    new = VisibleStateValue(vocabulary.size, features[0].state_numbers.numel(),
                            width=16, architecture="v2")
    with torch.no_grad():
        old_scores = [float(old(item)) for item in features]
        new_scores = [float(new(item)) for item in features]
        reversed_actions = encode_decision(base, actions()[::-1], vocabulary, 23)
        reversed_score = float(new(reversed_actions))
    assert old_scores[0] == pytest.approx(old_scores[1])
    assert old_scores[0] == pytest.approx(old_scores[2])
    assert new_scores[0] != pytest.approx(new_scores[1])
    assert new_scores[0] != pytest.approx(new_scores[2])
    assert new_scores[0] == pytest.approx(reversed_score)
    with pytest.raises(ValueError, match="architecture"):
        VisibleStateValue(vocabulary.size, features[0].state_numbers.numel(),
                          architecture="unsupported")


@pytest.mark.parametrize("architecture,feature_version", [("v1", 1), ("v2", 23)])
def test_critic_batch_matches_scalar_predictions_and_update(architecture, feature_version):
    vocabulary = CardVocabulary((10, 20), ((10, 0, 1000), (20, 0, 2000)))
    base = view()
    observations = (
        replace(base, own_main_deck=(10,)),
        replace(base, own_main_deck=(10, 20, 20),
                field=(CardView(0, "monster", "faceup", 10, 0, "attack",
                                attack=1000, defense=1000),)),
        replace(base, own_main_deck=(10, 20),
                hand=(*base.hand, CardView(0, "hand", "hidden", 20, 1))),
    )
    records = tuple(DecisionRecord(observation, actions(), actions()[0])
                    for observation in observations)
    features = [encode_decision(observation, actions(), vocabulary, feature_version)
                for observation in observations]
    torch.manual_seed(173)
    scalar = VisibleStateValue(vocabulary.size, features[0].state_numbers.numel(),
                               width=16, architecture=architecture)
    batched = copy.deepcopy(scalar)
    with torch.no_grad():
        expected = torch.stack([scalar(item) for item in features])
        actual = batched.forward_batch(features)
    assert torch.allclose(actual, expected, atol=1e-6)
    assert predict_state_values(batched, vocabulary, records, feature_version,
                                batch_size=2) == pytest.approx(expected.tolist(), abs=1e-6)
    scalar_optimizer = torch.optim.SGD(scalar.parameters(), lr=0.01)
    batched_optimizer = torch.optim.SGD(batched.parameters(), lr=0.01)
    scalar_optimizer.zero_grad()
    scalar_losses = torch.stack([(scalar(item) - 1.0).square() for item in features])
    scalar_losses.mean().backward()
    torch.nn.utils.clip_grad_norm_(scalar.parameters(), 1.0)
    scalar_optimizer.step()
    batch_loss = state_value_update(batched, vocabulary, records, 1.0,
                                    feature_version, batched_optimizer, batch_size=2)
    assert batch_loss == pytest.approx(float(scalar_losses.detach().mean()), abs=1e-6)
    for left, right in zip(scalar.parameters(), batched.parameters(), strict=True):
        assert torch.allclose(left, right, atol=1e-6)
    with pytest.raises(ValueError, match="batch size"):
        predict_state_values(batched, vocabulary, records, feature_version, batch_size=0)


def test_critic_corpus_selects_only_learner_visible_decisions():
    learner = DecisionRecord(view(), actions(), actions()[0])
    opponent_view = replace(view(), viewer=1, acting_player=1,
                            hand=(CardView(1, "hand", "hidden", 20, 0),))
    opponent_actions = (Action("a", "pass", 1), Action("b", "chain", 1))
    opponent = DecisionRecord(opponent_view, opponent_actions, opponent_actions[0])
    trajectory = Trajectory("goat", ("a", "b"), 4,
                            (learner, opponent, learner), 0,
                            source="self_play_rl", skill_metadata={"learner_seat": 0})
    selected, reward = selected_records(trajectory, 1)
    assert selected == (learner,)
    assert reward == 1.0
    with pytest.raises(ValueError, match="learner-seat"):
        selected_records(replace(trajectory, source="policy_evaluation"), 1)


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


def test_four_role_self_play_schedule_covers_both_decks_per_matchup():
    schedule = episode_schedule(
        (("goat", "chaos"), ("warrior", "return")), tuple(range(100, 108)),
        mode="four_roles")
    assert schedule == (
        (100, ("goat", "chaos"), 0),
        (101, ("chaos", "goat"), 1),
        (102, ("chaos", "goat"), 0),
        (103, ("goat", "chaos"), 1),
        (104, ("warrior", "return"), 0),
        (105, ("return", "warrior"), 1),
        (106, ("return", "warrior"), 0),
        (107, ("warrior", "return"), 1),
    )
    assert [(decks[seat], seat) for _, decks, seat in schedule] == [
        ("goat", 0), ("goat", 1), ("chaos", 0), ("chaos", 1),
        ("warrior", 0), ("warrior", 1), ("return", 0), ("return", 1),
    ]
    with pytest.raises(ValueError, match="schedule mode"):
        episode_schedule((("goat", "chaos"),), (100,), mode="unknown")


def test_self_play_can_track_terminal_baseline_by_learner_deck(monkeypatch):
    vocabulary = CardVocabulary((10, 20))
    model = LegalActionPolicy(vocabulary.size, width=16)
    rewards = {100: 1.0, 101: 1.0, 102: -1.0, 103: -1.0}
    seen = []

    def run_episode(_model, _vocabulary, _opponent, _decks, seed, *_args):
        return SimpleNamespace(
            seed=seed, winner=None, reward=rewards[seed], decisions=2,
            learner_records=(DecisionRecord(view(), actions(), actions()[0]),),
            trajectory=SimpleNamespace(deck_sha256=("a", "b"),
                                       asset_sha256={"core": "hash"},
                                       rules_profile="goat"))

    def update(_model, _vocabulary, _records, reward, baseline, _optimizer,
               *_args, **_kwargs):
        seen.append((reward, baseline))
        return 0.0

    monkeypatch.setattr("goat_ai.training.self_play.run_learning_episode", run_episode)
    monkeypatch.setattr("goat_ai.training.self_play.policy_gradient_update", update)
    matchups = (("goat", "chaos"), ("chaos", "goat"))
    seeds = (100, 101, 102, 103)
    reports = train_against_snapshot_pool(model, vocabulary, matchups, seeds,
                                          lambda: None, baseline_scope="learner_deck")
    assert [report["baseline"] for report in reports] == pytest.approx(
        [0.0, 0.05, 0.0, -0.05])
    assert seen == pytest.approx([(1.0, 0.0), (1.0, 0.05), (-1.0, 0.0), (-1.0, -0.05)])
    seen.clear()
    global_reports = train_against_snapshot_pool(model, vocabulary, matchups, seeds,
                                                 lambda: None)
    assert [report["baseline"] for report in global_reports] == pytest.approx(
        [0.0, 0.05, 0.0975, 0.042625])
    with pytest.raises(ValueError, match="hyperparameters"):
        train_against_snapshot_pool(model, vocabulary, matchups, seeds,
                                    lambda: None, baseline_scope="unknown")


def test_self_play_uses_named_opt_in_baseline_opponent(monkeypatch):
    vocabulary = CardVocabulary((10, 20))
    model = LegalActionPolicy(vocabulary.size, width=8)
    seen = []

    class Baseline:
        def __init__(self, seed):
            self.seed = seed

    def run_episode(_model, _vocabulary, opponent, _decks, seed, *_args, **_kwargs):
        seen.append((opponent.seed, seed))
        return SimpleNamespace(
            seed=seed, winner=0, reward=1.0, decisions=1, learner_records=(),
            trajectory=SimpleNamespace(deck_sha256=("a", "b"),
                                       asset_sha256={"core": "hash"},
                                       rules_profile="goat"))

    monkeypatch.setattr("goat_ai.training.self_play.run_learning_episode", run_episode)
    reports = train_against_snapshot_pool(
        model, vocabulary, (("a", "b"),), (100, 101), lambda: None,
        historical_probability=0, baseline_opponent_factory=Baseline,
        baseline_opponent_name="test_baseline")
    assert seen == [(100, 100), (101, 101)]
    assert [report["opponent"] for report in reports] == ["test_baseline"] * 2


@pytest.mark.parametrize("baseline_timing, first_advantages", [
    ("online", (1.0, -1.05, -1.05)),
    ("frozen_rollout", (1.0, -1.0, -1.0)),
    ("leave_one_out", (2.0, -2.0, -2.0)),
])
def test_multi_duel_ppo_freezes_policy_until_rollout_boundary(
        monkeypatch, baseline_timing, first_advantages):
    vocabulary = CardVocabulary((10, 20))
    model = LegalActionPolicy(vocabulary.size, width=8, feature_version=10)
    weights_seen = []
    batches = []

    def run_episode(policy, _vocabulary, _opponent, _decks, seed, *_args):
        weights_seen.append(float(next(policy.parameters()).flatten()[0]))
        decisions = (DecisionRecord(view(), actions(), actions()[0]),)
        return SimpleNamespace(
            seed=seed, winner=0, reward=1.0 if seed % 2 == 0 else -1.0,
            decisions=2, learner_records=decisions if seed % 2 == 0 else decisions * 2,
            trajectory=SimpleNamespace(deck_sha256=("a", "b"),
                                       asset_sha256={"core": "hash"},
                                       rules_profile="goat"))

    def update(policy, _vocabulary, records, _reward, _baseline, _optimizer, **kwargs):
        batches.append((len(records), tuple(kwargs["advantages"]),
                        tuple(kwargs["sample_weights"])))
        with torch.no_grad():
            next(policy.parameters()).add_(0.1)
        return float(len(batches))

    monkeypatch.setattr("goat_ai.training.self_play.run_learning_episode", run_episode)
    monkeypatch.setattr("goat_ai.training.self_play.ppo_clipped_update", update)
    reports = train_against_snapshot_pool(
        model, vocabulary, (("a", "b"),), (100, 101, 102, 103, 104),
        lambda: None, policy_update="clipped_ppo", ppo_rollout_games=2,
        ppo_rollout_weighting="per_episode", snapshot_every=2,
        ppo_baseline_timing=baseline_timing)
    assert weights_seen[0] == weights_seen[1]
    assert weights_seen[2] == weights_seen[3]
    assert weights_seen[0] != weights_seen[2]
    assert batches[0][0] == 3
    assert batches[0][1] == pytest.approx(first_advantages)
    assert batches[0][2] == pytest.approx((1.5, 0.75, 0.75))
    assert batches[1][0] == 3
    assert batches[2][0] == 1  # flush the final partial rollout
    assert [report["policy_loss"] for report in reports] == [1.0, 1.0, 2.0, 2.0, 3.0]
    if baseline_timing == "frozen_rollout":
        assert [report["baseline"] for report in reports] == pytest.approx(
            [0.0, 0.0, -0.0025, -0.0025, -0.00475625])
    if baseline_timing == "leave_one_out":
        assert [report["baseline"] for report in reports] == pytest.approx(
            [-1.0, 1.0, -1.0, 1.0, -0.00475625])
        assert batches[2][1] == pytest.approx((1.00475625,))
    with pytest.raises(ValueError, match="multi-duel PPO"):
        train_against_snapshot_pool(model, vocabulary, (("a", "b"),), (100,),
                                    lambda: None, ppo_rollout_games=2)


def test_terminal_gae_uses_visible_value_changes_and_terminal_outcome():
    values = (0.2, 0.4)
    assert terminal_gae_advantages(values, 1.0, 0.0) == pytest.approx((0.2, 0.6))
    assert terminal_gae_advantages(values, 1.0, 0.5) == pytest.approx((0.5, 0.6))
    assert terminal_gae_advantages(values, 1.0, 1.0) == pytest.approx((0.8, 0.6))
    assert terminal_gae_advantages(values, -1.0, 0.5) == pytest.approx((-0.5, -1.4))
    with pytest.raises(ValueError, match="GAE"):
        terminal_gae_advantages(values, 1.0, 1.1)
    with pytest.raises(ValueError, match="GAE"):
        terminal_gae_advantages((float("nan"),), 1.0, 0.5)


def test_frozen_visible_value_gae_reaches_multi_duel_ppo(monkeypatch):
    vocabulary = CardVocabulary((10, 20))
    model = LegalActionPolicy(vocabulary.size, width=8, feature_version=10)
    seen = []

    class FrozenValue:
        def predict_records(self, records, _vocabulary, _feature_version):
            assert len(records) == 2
            return (0.2, 0.4)

    def run_episode(_policy, _vocabulary, _opponent, _decks, seed, *_args):
        records = (DecisionRecord(view(), actions(), actions()[0]),) * 2
        return SimpleNamespace(
            seed=seed, winner=0, reward=1.0 if seed == 100 else -1.0,
            decisions=4, learner_records=records,
            trajectory=SimpleNamespace(deck_sha256=("a", "b"),
                                       asset_sha256={"core": "hash"},
                                       rules_profile="goat"))

    def update(_policy, _vocabulary, _records, _reward, _baseline, _optimizer, **kwargs):
        seen.append(tuple(kwargs["advantages"]))
        return 0.0

    monkeypatch.setattr("goat_ai.training.self_play.run_learning_episode", run_episode)
    monkeypatch.setattr("goat_ai.training.self_play.ppo_clipped_update", update)
    train_against_snapshot_pool(
        model, vocabulary, (("a", "b"),), (100, 101), lambda: None,
        policy_update="clipped_ppo", ppo_rollout_games=2, snapshot_every=2,
        historical_probability=0.0, baseline_scope="resource_ridge",
        resource_value_model=FrozenValue(), ppo_gae_lambda=0.5)
    assert len(seen) == 1
    assert seen[0] == pytest.approx((0.5, 0.6, -0.5, -1.4))
    with pytest.raises(ValueError, match="invalid self-play"):
        train_against_snapshot_pool(
            model, vocabulary, (("a", "b"),), (100, 101), lambda: None,
            policy_update="clipped_ppo", ppo_rollout_games=2, snapshot_every=2,
            ppo_gae_lambda=0.5)


def test_leave_one_out_uses_other_same_deck_games_even_without_policy_choices(
        monkeypatch):
    vocabulary = CardVocabulary((10, 20))
    model = LegalActionPolicy(vocabulary.size, width=8, feature_version=10)
    seen = []

    def run_episode(_policy, _vocabulary, _opponent, _decks, seed, *_args):
        records = () if seed == 101 else (DecisionRecord(
            view(), actions(), actions()[0]),)
        return SimpleNamespace(
            seed=seed, winner=0, reward=1.0 if seed % 2 == 0 else -1.0,
            decisions=2, learner_records=records,
            trajectory=SimpleNamespace(deck_sha256=("a", "b"),
                                       asset_sha256={"core": "hash"},
                                       rules_profile="goat"))

    def update(_policy, _vocabulary, records, _reward, _baseline, _optimizer,
               **kwargs):
        seen.append((len(records), tuple(kwargs["advantages"])))
        return 7.0

    monkeypatch.setattr("goat_ai.training.self_play.run_learning_episode", run_episode)
    monkeypatch.setattr("goat_ai.training.self_play.ppo_clipped_update", update)
    reports = train_against_snapshot_pool(
        model, vocabulary, (("a", "b"),), (100, 101, 102, 103),
        lambda: None, policy_update="clipped_ppo", ppo_rollout_games=4,
        schedule_mode="four_roles", baseline_scope="learner_deck",
        ppo_baseline_timing="leave_one_out", snapshot_every=4)
    assert seen == [(3, pytest.approx((2.0, 2.0, -2.0)))]
    assert [report["baseline"] for report in reports] == pytest.approx(
        [-1.0, 1.0, -1.0, 1.0])
    assert [report["policy_loss"] for report in reports] == [7.0, None, 7.0, 7.0]


def test_frozen_resource_ridge_supplies_per_decision_multi_duel_advantages(
        monkeypatch):
    vocabulary = CardVocabulary((10, 20))
    model = LegalActionPolicy(vocabulary.size, width=8, feature_version=10)
    seen = []

    def run_episode(_policy, _vocabulary, _opponent, _decks, seed, *_args):
        record = DecisionRecord(view(), actions(), actions()[0])
        return SimpleNamespace(
            seed=seed, winner=0, reward=1.0 if seed == 100 else -1.0,
            decisions=2, learner_records=(record, record) if seed == 100 else (record,),
            trajectory=SimpleNamespace(deck_sha256=("a", "b"),
                                       asset_sha256={"core": "hash"},
                                       rules_profile="goat"))

    def update(_policy, _vocabulary, _records, _reward, _baseline,
               _optimizer, **kwargs):
        seen.append(tuple(kwargs["advantages"]))
        return 1.0

    class Ridge:
        def predict_records(self, records, _vocabulary, _feature_version):
            return (0.2, -0.4) if len(records) == 2 else (0.2,)

    monkeypatch.setattr("goat_ai.training.self_play.run_learning_episode", run_episode)
    monkeypatch.setattr("goat_ai.training.self_play.ppo_clipped_update", update)
    reports = train_against_snapshot_pool(
        model, vocabulary, (("a", "b"),), (100, 101), lambda: None,
        policy_update="clipped_ppo", baseline_scope="resource_ridge",
        resource_value_model=Ridge(), ppo_rollout_games=2, snapshot_every=2)
    assert seen == [pytest.approx((0.8, 1.4, -1.2))]
    assert [report["baseline"] for report in reports] == pytest.approx((-0.1, 0.2))


def test_self_play_can_censor_over_cap_game_without_learning_from_it(monkeypatch):
    vocabulary = CardVocabulary((10, 20))
    model = LegalActionPolicy(vocabulary.size, width=16)
    saved = []

    def run_episode(_model, _vocabulary, _opponent, _decks, seed, *_args):
        if seed == 100:
            raise EpisodeDecisionLimit(seed, 5)
        return SimpleNamespace(
            seed=seed, winner=0, reward=1.0, decisions=3,
            learner_records=(), trajectory=SimpleNamespace(
                deck_sha256=("a", "b"), asset_sha256={"core": "hash"},
                rules_profile="goat"))

    monkeypatch.setattr("goat_ai.training.self_play.run_learning_episode", run_episode)
    kwargs = {"max_decisions": 5, "random_seed": 7,
              "record_episode": lambda index, episode: saved.append((index, episode.seed))}
    with pytest.raises(EpisodeDecisionLimit, match="seed=100"):
        train_against_snapshot_pool(model, vocabulary, (("a", "b"),), (100, 101),
                                    lambda: None, **kwargs)
    reports = train_against_snapshot_pool(
        model, vocabulary, (("a", "b"),), (100, 101), lambda: None,
        skip_capped_games=True, **kwargs)
    assert [report["status"] for report in reports] == ["decision_limit", "terminal"]
    assert reports[0]["learner_decisions"] == 0
    assert "reward" not in reports[0]
    assert saved == [(1, 101)]


def test_episode_decision_limit_round_trips_across_process_boundary():
    raised = pickle.loads(pickle.dumps(EpisodeDecisionLimit(100, 3000)))
    assert isinstance(raised, EpisodeDecisionLimit)
    assert (raised.seed, raised.max_decisions) == (100, 3000)
    assert str(raised) == "self-play duel exceeded 3000 decisions: seed=100"


def test_capped_episode_from_spawned_worker_retains_seed_and_limit():
    with ProcessPoolExecutor(max_workers=1, mp_context=get_context("spawn")) as pool:
        future = pool.submit(_raise_capped_episode_for_worker_test)
        with pytest.raises(EpisodeDecisionLimit) as error:
            future.result()
    assert (error.value.seed, error.value.max_decisions) == (21211, 3000)


def test_self_play_reports_unsupported_native_prompt_without_learning(monkeypatch):
    vocabulary = CardVocabulary((10, 20))
    model = LegalActionPolicy(vocabulary.size, width=16)
    saved = []

    def run_episode(_model, _vocabulary, _opponent, _decks, seed, *_args):
        if seed == 100:
            raise SimulatorUnavailable("card selection has 8008 combinations")
        return SimpleNamespace(
            seed=seed, winner=0, reward=1.0, decisions=3,
            learner_records=(), trajectory=SimpleNamespace(
                deck_sha256=("a", "b"), asset_sha256={"core": "hash"},
                rules_profile="goat"))

    monkeypatch.setattr("goat_ai.training.self_play.run_learning_episode", run_episode)
    kwargs = {"random_seed": 7, "record_episode": lambda index, episode: saved.append(
        (index, episode.seed))}
    with pytest.raises(SimulatorUnavailable, match="8008 combinations"):
        train_against_snapshot_pool(model, vocabulary, (("a", "b"),), (100, 101),
                                    lambda: None, **kwargs)
    reports = train_against_snapshot_pool(
        model, vocabulary, (("a", "b"),), (100, 101), lambda: None,
        skip_unsupported_games=True, **kwargs)
    assert [report["status"] for report in reports] == ["simulator_unavailable", "terminal"]
    assert reports[0]["error"] == "card selection has 8008 combinations"
    assert reports[0]["learner_decisions"] == 0
    assert "reward" not in reports[0]
    assert saved == [(1, 101)]


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
    legacy_rl = replace(trajectory, source="self_play_rl",
                        skill_metadata={"learner_seat": 1})
    assert demonstrator_seat(legacy_rl) == 1
    assert demonstrator_records(legacy_rl) == (second,)
    assert demonstrator_records(replace(
        legacy_rl, skill_metadata={"learner_seat": 0,
                                   "demonstrator_seat": 0})) == (first,)
    with pytest.raises(ValueError, match="conflicts"):
        demonstrator_records(replace(
            legacy_rl, skill_metadata={"learner_seat": 1,
                                       "demonstrator_seat": 0}))
    with pytest.raises(ValueError, match="learner_seat"):
        demonstrator_records(replace(legacy_rl, skill_metadata=None))
    with pytest.raises(ValueError, match="learner_seat"):
        demonstrator_records(replace(
            legacy_rl, skill_metadata={"learner_seat": True}))
    with pytest.raises(ValueError, match="demonstrator_seat"):
        demonstrator_records(replace(trajectory, skill_metadata=None))
    with pytest.raises(ValueError, match="demonstrator_seat"):
        demonstrator_records(replace(trajectory, skill_metadata={"demonstrator_seat": True}))


def test_raw_training_source_admission_keeps_unauthorized_replays_out():
    first = DecisionRecord(view(), actions(), actions()[0])
    base = Trajectory("goat", ("a", "b"), 1, (first,), 0)
    assert training_demonstrator_records(base) == (first,)
    teacher = replace(base, source="tactical",
                      skill_metadata={"demonstrator_seat": 0})
    assert training_demonstrator_records(teacher) == (first,)
    assert training_demonstrator_records(replace(
        base, source="combat_flip", skill_metadata={"demonstrator_seat": 0})) == (first,)
    human = replace(base, source="human_cli", skill_metadata={
        "demonstrator_seat": 0, "authorization": "self_recorded"})
    assert training_demonstrator_records(human) == (first,)
    for source in ("policy_evaluation", "edopro_conditional", "unknown"):
        with pytest.raises(ValueError, match="not an admitted raw training source"):
            training_demonstrator_records(replace(base, source=source))
    with pytest.raises(ValueError, match="scripted replay requires explicit annotations"):
        training_demonstrator_records(replace(base, source="scripted_probe"))
    with pytest.raises(ValueError, match="self_recorded authorization"):
        training_demonstrator_records(replace(
            human, skill_metadata={"demonstrator_seat": 0}))
    with pytest.raises(ValueError, match="demonstrator_seat"):
        training_demonstrator_records(replace(
            teacher, skill_metadata=None))
    with pytest.raises(ValueError, match="demonstrator_seat"):
        training_demonstrator_records(replace(
            human, skill_metadata={"authorization": "self_recorded"}))


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
    fresh_agent = PolicyAgent(FavorUnselect(), CardVocabulary((10, 20)))
    assert fresh_agent.select_action(view(), (toggle, other)) == other
    finish = Action("finish", "finish_selection", 0)
    assert agent.select_action(view(), (toggle, finish)) == finish

    class FavorCancel(FavorUnselect):
        def forward(self, features):
            return (features.action_kinds == ACTION_KINDS.index("cancel") + 1
                    ).float() * 10 + self.dummy

    cancel_agent = PolicyAgent(FavorCancel(), CardVocabulary((10, 20)))
    cancel = Action("cancel", "cancel", 0)
    assert cancel_agent.select_action(view(), (cancel, first)) == cancel
    retry = replace(view(), public_history=("Thunder Dragon effect resolved",))
    assert cancel_agent.select_action(
        retry, (Action("new-cancel-id", "cancel", 0),
                Action("new-select-id", "select_card", 0, first.parameters))
    ).kind == "select_card"
    # A changed visible hand is a new decision even on the same turn.
    changed = replace(view(), hand=(CardView(0, "hand", "hidden", 20, 0),))
    assert cancel_agent.select_action(changed, (cancel, first)) == cancel
    assert cancel_agent.select_action(replace(view(), turn=4), (cancel, first)) == cancel


def test_policy_tactical_guard_is_opt_in_and_uses_visible_state():
    class FavorCard(torch.nn.Module):
        def __init__(self, code_index):
            super().__init__()
            self.dummy = torch.nn.Parameter(torch.zeros(1))
            self.code_index = code_index

        def forward(self, features):
            return (features.action_cards == self.code_index).float() * 10 + self.dummy

    vocabulary = CardVocabulary(tuple(sorted((HEAVY_STORM, SCAPEGOAT))))
    own_set = CardView(0, "spell_trap", "facedown", 45986603, 0)
    snapshot = replace(view(), field=(own_set,))
    storm = Action("storm", "activate", 0, {"code": HEAVY_STORM})
    wait = Action("wait", "end_phase", 0)
    model = FavorCard(vocabulary.index(HEAVY_STORM))
    assert PolicyAgent(model, vocabulary).select_action(snapshot, (storm, wait)) == storm
    assert PolicyAgent(model, vocabulary, tactical_guard=True).select_action(
        snapshot, (storm, wait)) == wait

    goat = Action("goat", "chain", 0, {"code": SCAPEGOAT})
    decline = Action("decline", "pass", 0)
    model = FavorCard(vocabulary.index(SCAPEGOAT))
    guarded = PolicyAgent(model, vocabulary, tactical_guard=True)
    assert guarded.select_action(replace(view(), phase="draw"), (goat, decline)) == decline
    assert guarded.select_action(replace(view(), phase="end"), (goat, decline)) == goat


def test_optional_weak_flip_guard_substitutes_set_for_preferred_summon():
    class FavorFirst(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.dummy = torch.nn.Parameter(torch.zeros(1))

        def forward(self, features):
            return -torch.arange(len(features.action_cards)).float() + self.dummy

    faith = 31560081
    vocabulary = CardVocabulary((faith,))
    summon = Action("summon", "normal_summon", 0, {"code": faith})
    set_faith = Action("set", "set_monster", 0, {"code": faith})
    snapshot = replace(view(), field=(), life_points=(8000, 8000))
    model = FavorFirst()
    assert PolicyAgent(model, vocabulary, tactical_guard=True).select_action(
        snapshot, (summon, set_faith)) == summon
    guarded = PolicyAgent(model, vocabulary, tactical_guard=True,
                          weak_flip_attacks={faith: 300})
    assert guarded.select_action(snapshot, (summon, set_faith)) == set_faith
    battle = Action("battle", "battle_phase", 0)
    assert guarded.select_action(replace(snapshot, life_points=(8000, 300)),
                                 (summon, set_faith, battle)) == summon


def test_optional_self_target_guard_changes_only_target_choice():
    class FavorFirst(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.dummy = torch.nn.Parameter(torch.zeros(1))

        def forward(self, features):
            return -torch.arange(len(features.action_cards)).float() + self.dummy

    bls = 504700118
    own = Action("own", "select_card", 0,
                 {"code": bls, "controller": 0, "location": 4, "sequence": 0})
    enemy = Action("enemy", "select_card", 0,
                   {"controller": 1, "location": 4, "sequence": 0})
    snapshot = replace(view(), chain=(ChainLinkView(1, bls, 0, 4, 0),))
    vocabulary = CardVocabulary((bls,))
    model = FavorFirst()
    assert PolicyAgent(model, vocabulary, tactical_guard=True).select_action(
        snapshot, (own, enemy)) == own
    assert PolicyAgent(model, vocabulary, tactical_guard=True,
                       self_target_guard=True).select_action(
        snapshot, (own, enemy)) == enemy


def test_optional_position_guard_preserves_defending_sheep_token():
    class FavorFirst(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.dummy = torch.nn.Parameter(torch.zeros(1))

        def forward(self, features):
            return -torch.arange(len(features.action_cards)).float() + self.dummy

    sheep = CardView(0, "monster", "faceup", 73915053, 2,
                     "defense", 0, 0)
    snapshot = replace(view(), field=(sheep,))
    change = Action("change", "change_position", 0,
                    {"code": 73915053, "controller": 0,
                     "location": 4, "sequence": 2})
    end = Action("end", "end_phase", 0)
    model = FavorFirst()
    vocabulary = CardVocabulary((73915053,))
    assert PolicyAgent(model, vocabulary).select_action(snapshot, (change, end)) == change
    assert PolicyAgent(model, vocabulary, position_guard=True).select_action(
        snapshot, (change, end)) == end
    stronger_attacker = replace(sheep, code=87621407, orientation="attack",
                               attack=1400, defense=1000)
    snapshot = replace(snapshot, field=(stronger_attacker,))
    assert PolicyAgent(model, vocabulary, position_guard=True).select_action(
        snapshot, (change, end)) == end
    assert PolicyAgent(model, vocabulary, position_guard=True,
                       position_guard_version=1).select_action(
        snapshot, (change, end)) == change
