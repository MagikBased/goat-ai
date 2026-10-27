"""Deck-asymmetry controls require exact schedules and native fingerprints."""

import json
from copy import deepcopy

import pytest

from goat_ai.engine.decks import main_deck_composition_sha256, read_ydk
from goat_ai.evaluation.tournament import GameResult, TournamentReport
from goat_ai.replay.fingerprint import sha256_file
from scripts.compare_policy_baseline_mirror import compare_policy_to_mirrors


def _reports(tmp_path):
    decks = [tmp_path / "a.ydk", tmp_path / "b.ydk"]
    for code, path in enumerate(decks, 1):
        path.write_text(f"#main\n{code}\n")
    names = [str(path) for path in decks]
    keys = [(a, b, seed, seat) for a, b in (names, names[::-1])
            for seed in (100, 101) for seat in (0, 1)]
    mirror_games = tuple(GameResult(a, b, seed, seat, seat if i % 2 == 0
                                    else 1 - seat, 20 + i)
                         for i, (a, b, seed, seat) in enumerate(keys))
    policy_games = tuple(GameResult(a, b, seed, seat, 1 - seat if i < 5
                                    else seat, 21 + i)
                         for i, (a, b, seed, seat) in enumerate(keys))

    def saved_games(games):
        return [vars(game) | {"a_outcome": game.a_outcome} for game in games]

    hashes = {str(path): sha256_file(path) for path in decks}
    compositions = {str(path): main_deck_composition_sha256(read_ydk(path))
                    for path in decks}
    assets = {"core_library": "a" * 64, "unofficial_database": "b" * 64}
    policy = {
        "engine": "experimental", "core_commit": "pinned",
        "checkpoint_sha256": "f" * 64,
        "asset_sha256": assets, "card_scripts_sha256": "e" * 64,
        "deck_sha256": hashes, "main_deck_composition_sha256": compositions,
        "evaluation_seeds": [100, 101], "both_deck_assignments": True,
        "opponent": "tactical", "opponent_agent_version": 14,
        "opponent_checkpoint_sha256": None,
        "training_games": [{"seed": 99,
                            "main_deck_composition_sha256": ["c" * 64, "d" * 64]}],
        "games": saved_games(policy_games), "summary": TournamentReport(policy_games).summary(),
    }
    mirror = {
        "agent_a": "tactical", "agent_b": "tactical",
        "agent_a_version": 14, "agent_b_version": 14,
        "ruleset_scope": "experimental GOAT-mode native adapter",
        "core": "edo9300/ygopro-core pinned", "asset_sha256": assets,
        "card_scripts_sha256": "e" * 64,
        "deck_sha256": hashes, "main_deck_composition_sha256": compositions,
        "seeds": [100, 101], "both_deck_assignments": True,
        "games": saved_games(mirror_games),
        "summary": TournamentReport(mirror_games).summary(),
    }
    p = tmp_path / "policy.json"
    m = tmp_path / "mirror.json"
    p.write_text(json.dumps(policy))
    m.write_text(json.dumps(mirror))
    return p, m, mirror, decks[0]


def test_mirror_comparison_verifies_controls_and_reports_deck_split(tmp_path):
    policy, mirror, _, _ = _reports(tmp_path)
    result = compare_policy_to_mirrors(policy, [mirror])
    assert result["games_per_arm"] == 8
    assert result["policy_score"] == 3 / 8
    assert result["mirror_score"] == 4 / 8
    assert result["paired_score_difference"] == -1 / 8
    assert len(result["by_deck"]) == 2
    assert result["mirror_report_sha256"][str(mirror)] == sha256_file(mirror)


@pytest.mark.parametrize("change,reason", [
    (lambda d: d["asset_sha256"].update(unofficial_database="0" * 64), "controls differ"),
    (lambda d: d.update(agent_b_version=13), "controls differ"),
    (lambda d: d["games"].pop(), "summary disagrees"),
    (lambda d: d["games"][0].update(a_outcome="draw"), "invalid mirror game outcome"),
])
def test_mirror_comparison_rejects_mismatches(tmp_path, change, reason):
    policy, mirror_path, mirror, _ = _reports(tmp_path)
    changed = deepcopy(mirror)
    change(changed)
    mirror_path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match=reason):
        compare_policy_to_mirrors(policy, [mirror_path])


def test_mirror_comparison_rejects_local_deck_change_and_duplicate_schedule(tmp_path):
    policy, mirror, _, deck = _reports(tmp_path)
    with pytest.raises(ValueError, match="duplicate tournament game"):
        compare_policy_to_mirrors(policy, [mirror, mirror])
    deck.write_text("#main\n3\n")
    with pytest.raises(ValueError, match="local deck differs"):
        compare_policy_to_mirrors(policy, [mirror])
