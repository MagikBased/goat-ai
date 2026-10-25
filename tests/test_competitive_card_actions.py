"""Source-card coverage must not count target-selection identities as card use."""

from collections import Counter

from goat_ai.actions import Action
from scripts.probe_competitive_card_actions import ROOT, count_source_actions, deck_label


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
