"""Parallel PPO rollout keeps seed-scoped samples and updates reproducible."""

import copy
import os
from functools import partial
from pathlib import Path

import pytest
import torch

from goat_ai.agents import load_card_facts, load_card_races, load_flip_monster_codes
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine
from goat_ai.training.policy import CardVocabulary, LegalActionPolicy
from goat_ai.training.self_play import make_tactical_opponent, train_against_snapshot_pool

ROOT = Path(__file__).resolve().parents[1]
VANILLA = ROOT / "examples/decks/vanilla_probe.ydk"
REVERSE = ROOT / "examples/decks/vanilla_reverse.ydk"


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("baseline_timing", [
    "online", "frozen_rollout", "leave_one_out"])
def test_worker_count_preserves_rollout_trajectories_and_update(baseline_timing):
    native_root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    vocabulary = CardVocabulary.from_goat_whitelist(
        native_root / "banlist/GOAT.lflist.conf")
    torch.manual_seed(79)
    initial = LegalActionPolicy(vocabulary.size, width=8, feature_version=10)
    results = []
    for workers, batch_inference in ((1, False), (2, False), (0, True)):
        model = copy.deepcopy(initial)
        episodes = []
        reports = train_against_snapshot_pool(
            model, vocabulary, ((str(VANILLA), str(REVERSE)),),
            (90000, 90001), partial(RestrictedOcgcoreEngine, native_root),
            policy_update="clipped_ppo", ppo_rollout_games=2,
            ppo_baseline_timing=baseline_timing,
            rollout_workers=workers, rollout_batch_inference=batch_inference,
            snapshot_every=2,
            ppo_epochs=1, ppo_batch_size=8, historical_probability=0.5,
            max_decisions=2000, random_seed=79,
            record_episode=lambda _, episode, sink=episodes: sink.append(episode),
        )
        assert len(episodes) == 2
        assert all(report["status"] == "terminal" for report in reports)
        results.append((reports, episodes, model.state_dict()))
    serial = results[0]
    for other in results[1:]:
        assert serial[:2] == other[:2]
        assert all(torch.equal(serial[2][name], other[2][name])
                   for name in serial[2])


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_traced_v23_rollout_preserves_native_duels_and_update():
    native_root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    vocabulary = CardVocabulary.from_goat_whitelist(
        native_root / "banlist/GOAT.lflist.conf", native_root=native_root)
    torch.manual_seed(79)
    initial = LegalActionPolicy(vocabulary.size, width=8, feature_version=23)
    results = []
    for traced in (False, True):
        model = copy.deepcopy(initial)
        episodes = []
        reports = train_against_snapshot_pool(
            model, vocabulary, ((str(VANILLA), str(REVERSE)),),
            (90020, 90021), partial(RestrictedOcgcoreEngine, native_root),
            policy_update="clipped_ppo", ppo_rollout_games=2,
            trace_rollout_inference=traced, snapshot_every=2,
            ppo_epochs=1, ppo_batch_size=8, historical_probability=0.5,
            max_decisions=2000, random_seed=79,
            record_episode=lambda _, episode, sink=episodes: sink.append(episode),
        )
        assert len(episodes) == 2
        assert all(report["status"] == "terminal" for report in reports)
        results.append((reports, episodes, model.state_dict()))
    assert results[0][:2] == results[1][:2]
    assert all(torch.equal(results[0][2][name], results[1][2][name])
               for name in results[0][2])


def test_parallel_rollout_requires_multi_game_ppo():
    vocabulary = CardVocabulary((1,))
    model = LegalActionPolicy(vocabulary.size, width=8, feature_version=10)
    with pytest.raises(ValueError, match="parallel rollout needs multi-duel PPO"):
        train_against_snapshot_pool(
            model, vocabulary, (("a", "b"),), (1,), lambda: None,
            rollout_workers=2,
        )
    with pytest.raises(ValueError, match="batched inference needs multi-duel PPO"):
        train_against_snapshot_pool(
            model, vocabulary, (("a", "b"),), (1,), lambda: None,
            rollout_batch_inference=True,
        )


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_tactical_baseline_reproduces_across_rollout_worker_counts():
    native_root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    vocabulary = CardVocabulary.from_goat_whitelist(
        native_root / "banlist/GOAT.lflist.conf")
    torch.manual_seed(81)
    initial = LegalActionPolicy(vocabulary.size, width=8, feature_version=10)
    factory = partial(make_tactical_opponent,
                      flip_codes=load_flip_monster_codes(native_root),
                      card_races=load_card_races(native_root),
                      card_facts=load_card_facts(native_root))
    results = []
    for workers in (1, 2):
        model = copy.deepcopy(initial)
        episodes = []
        reports = train_against_snapshot_pool(
            model, vocabulary, ((str(VANILLA), str(REVERSE)),),
            (90040, 90041), partial(ExperimentalOcgcoreEngine, native_root),
            policy_update="clipped_ppo", ppo_rollout_games=2,
            rollout_workers=workers, snapshot_every=2,
            ppo_epochs=1, ppo_batch_size=8, historical_probability=0,
            baseline_opponent_factory=factory, baseline_opponent_name="tactical_v14",
            max_decisions=2000, random_seed=81,
            record_episode=lambda _, episode, sink=episodes: sink.append(episode),
        )
        assert len(episodes) == 2
        assert all(report["opponent"] == "tactical_v14" for report in reports)
        results.append((reports, episodes, model.state_dict()))
    assert results[0][:2] == results[1][:2]
    assert all(torch.equal(results[0][2][name], results[1][2][name])
               for name in results[0][2])
