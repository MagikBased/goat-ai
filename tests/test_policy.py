"""Contract checks for the optional PyTorch legal-action policy."""

from dataclasses import replace
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import pytest

torch = pytest.importorskip("torch")

from goat_ai.actions import Action
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
    EpisodeDecisionLimit,
    episode_schedule,
    policy_gradient_update,
    sample_legal_action,
    train_against_snapshot_pool,
)
from scripts.audit_policy_agreement import (
    STAPLES,
    decision_deck,
    decision_fingerprint,
    decision_scopes,
    staple_context,
)
from scripts.evaluate_policy import (
    make_policy_agent,
    validate_heldout_seeds,
    validate_unseen_deck_hashes,
    validate_unseen_main_decks,
)
from scripts.train_behavioral_clone import focus_opportunity


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
    kwargs = dict(max_decisions=5, random_seed=7,
                  record_episode=lambda index, episode: saved.append((index, episode.seed)))
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
    kwargs = dict(random_seed=7, record_episode=lambda index, episode: saved.append(
        (index, episode.seed)))
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
