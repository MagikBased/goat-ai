"""Period MR1 probe: Sangan searches after becoming Synchro Material."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.mr1_synchro_probe import (
    BRIONAC, JUNK_SYNCHRON, SANGAN, Mr1SynchroProbeEngine,
)
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_sangan_synchro_material_searches_after_brionac_summon(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (SANGAN, JUNK_SYNCHRON, BRIONAC):
        if not (root / "scripts/official" / f"c{code}.lua").is_file():
            pytest.skip("full official card script checkout not installed")
    deck = tmp_path / "sangan_brionac.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        SANGAN, *([JUNK_SYNCHRON] * 3), *VANILLA_DECK[4:])))
        + f"\n#extra\n{BRIONAC}\n!side\n")
    opponent = Path(__file__).resolve().parents[1] / "examples/decks/vanilla_reverse.ydk"

    with GoatEnvironment(str(deck), str(opponent), seed=3,
                         engine=Mr1SynchroProbeEngine(root)) as env:
        view = env.reset()
        assert {SANGAN, JUNK_SYNCHRON} <= {card.code for card in view.hand}
        used = set()
        search_seen = False
        searched_code = None
        search_deck_count = None
        agents = (RandomAgent(3), RandomAgent(4))
        for _ in range(3000):
            if env.is_terminal():
                break
            actions = env.legal_actions()
            action = None
            if "search" not in used:
                for kind, code, label in (
                        ("normal_summon", SANGAN, "sangan"),
                        ("normal_summon", JUNK_SYNCHRON, "junk"),
                        ("special_summon", BRIONAC, "brionac")):
                    if label not in used and view.acting_player == 0 and view.phase == "main1":
                        action = next((candidate for candidate in actions
                                       if candidate.kind == kind
                                       and candidate.parameters.get("code") == code), None)
                        if action:
                            used.add(label)
                            break
                if "brionac" in used and not search_seen and any(
                        link.card_code == SANGAN for link in view.chain):
                    assert any(card.code == BRIONAC for card in view.field)
                    assert {SANGAN, JUNK_SYNCHRON} <= {
                        card.code for card in view.graveyards[0]}
                    search_seen = True
                if search_seen and action is None:
                    action = next((candidate for candidate in actions
                                   if candidate.kind == "select_card"
                                   and candidate.parameters.get("location") == 1
                                   and candidate.parameters.get("controller") == 0), None)
                    if action:
                        searched_code = action.parameters["code"]
                        search_deck_count = view.deck_counts[0]
                        used.add("search")
                if action is None:
                    action = next((candidate for candidate in actions
                                   if candidate.kind in ("place", "select_position",
                                                         "select_card", "yes",
                                                         "finish_selection")), None)
                if action is None:
                    action = next((candidate for candidate in actions
                                   if candidate.kind in ("pass", "end_phase")), actions[0])
            else:
                action = agents[view.acting_player].select_action(view, actions)
            view = env.step(action)
            if searched_code is not None and view.acting_player == 0 and not view.chain:
                assert searched_code in {card.code for card in view.hand}
                assert view.deck_counts[0] == search_deck_count - 1
                searched_code = None
        assert env.is_terminal()
        assert search_seen and "search" in used
        trajectory = env.trajectory()
        assert trajectory.ruleset == "mr1-synchro-protocol"
        for code in (SANGAN, JUNK_SYNCHRON, BRIONAC):
            assert f"scripts/official/c{code}.lua" in trajectory.asset_sha256

    saved = tmp_path / "sangan_synchro.json"
    write_trajectory(saved, trajectory)
    loaded = read_trajectory(saved)
    assert loaded == trajectory
    assert verify_trajectory(loaded, Mr1SynchroProbeEngine(root)) == len(
        trajectory.decisions)
    assert audit_trajectory_visibility(loaded)["decisions"] == len(
        trajectory.decisions)
