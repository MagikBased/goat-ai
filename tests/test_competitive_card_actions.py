"""Source-card coverage must not count target-selection identities as card use."""

import os
from collections import Counter
from itertools import combinations
from pathlib import Path
from types import SimpleNamespace

import pytest

from goat_ai.actions import Action
from goat_ai.agents import CombatHeuristicAgent, HeuristicAgent, RandomAgent
from goat_ai.evaluation.competitive_corpus import TOURNAMENT_MAIN_DECKS
from scripts.probe_competitive_card_actions import (
    ROOT, count_chain_response, count_source_actions, deck_label, make_agent,
    probe, tournament_matchups,
)


def test_coverage_counts_source_options_once_and_ignores_target_choices():
    summon_a = Action("a", "normal_summon", 0, {"code": 69140098, "position": 1})
    summon_b = Action("b", "normal_summon", 0, {"code": 69140098, "position": 2})
    ring = Action("c", "activate", 0, {"code": 511000824})
    target = Action("d", "select_card", 0, {"code": 49881766})
    legal = (summon_a, summon_b, ring, target)
    offered, selected = Counter(), Counter()

    count_source_actions(legal, target, offered, selected)
    assert offered == {(69140098, "normal_summon"): 1,
                       (511000824, "activate"): 1}
    assert selected == {}

    count_source_actions(legal, ring, offered, selected)
    assert offered == {(69140098, "normal_summon"): 2,
                       (511000824, "activate"): 2}
    assert selected == {(511000824, "activate"): 1}


def test_report_uses_checkout_independent_example_deck_path():
    path = ROOT / "examples/decks/goat_control_lolmarcus_2020.ydk"
    assert deck_label(path) == "examples/decks/goat_control_lolmarcus_2020.ydk"


def test_tournament_probe_pairs_every_sourced_list_and_no_guide_deck():
    fixtures = ROOT / "examples/decks"
    expected = tuple(combinations((fixtures / name for name in TOURNAMENT_MAIN_DECKS), 2))
    assert tournament_matchups(fixtures) == expected
    assert len(expected) == 15
    assert all("guide" not in str(path) for pair in expected for path in pair)


def test_probe_agent_choice_uses_baseline_public_action_interfaces():
    assert isinstance(make_agent("random", 5), RandomAgent)
    assert isinstance(make_agent("heuristic", 5), HeuristicAgent)
    assert isinstance(make_agent("combat_heuristic", 5), CombatHeuristicAgent)


def test_chain_response_uses_latest_public_link_and_ignores_nonresponses():
    responses = Counter()
    chain = (SimpleNamespace(card_code=19613556),
             SimpleNamespace(card_code=14087893))
    observation = SimpleNamespace(chain=chain)
    ring = Action("ring", "chain", 0, {"code": 511000824})
    target = Action("target", "select_card", 0, {"code": 69140098})
    count_chain_response(observation, ring, responses)
    count_chain_response(observation, target, responses)
    count_chain_response(SimpleNamespace(chain=()), ring, responses)
    assert responses == {(511000824, 14087893): 1}


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_sourced_deck_probe_records_and_replay_verifies_full_duels(tmp_path):
    fixtures = ROOT / "examples/decks"
    report = probe(
        Path(os.environ["GOAT_AI_NATIVE_ROOT"]),
        ((fixtures / "goat_control_lolmarcus_2020.ydk",
          fixtures / "chaos_turbo_riclar_2020.ydk"),),
        first_seed=18500, seeds=1, max_decisions=3000,
        agent_name="combat_heuristic", verify_replays=True,
        record_dir=tmp_path / "replays",
    )
    assert report["replay_verification"] == {
        "verified_games": 2,
        "verified_decisions": sum(game["decisions"] for game in report["games"]),
        "serialized_round_trip": True,
    }
    assert all(game["replay_verified_decisions"] == game["decisions"]
               and (tmp_path / "replays" / game["trajectory_file"]).is_file()
               and len(game["trajectory_sha256"]) == 64
               for game in report["games"])
