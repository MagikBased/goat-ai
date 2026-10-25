"""Graceful Charity can be activated when its draw will deck out the player."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

GRACEFUL = 79571449
UPSTART = 70368879
PATCHED_GRACEFUL_SHA256 = "5ab8c1b6aa3dfca5e5409926115089f9a12584f260c1a7e2d31867040e30f89d"
EXTRA_VANILLAS = (
    32864, 549481, 1184620, 1761063, 1784619, 2118022, 2311603, 2468169,
    2483611, 2863439, 2964201, 3134241, 3170832, 3573512, 3797883,
    4035199, 4042268, 4179849, 4920010, 5265750,
)


def _decks(tmp_path, cards):
    own = tmp_path / "graceful.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        *cards, *VANILLA_DECK[len(cards):]))) + "\n#extra\n!side\n")
    other = tmp_path / "sixty.ydk"
    other.write_text("#main\n" + "\n".join(map(str, (
        *VANILLA_DECK, *EXTRA_VANILLAS))) + "\n#extra\n!side\n")
    return own, other


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("remaining", [1, 2, 3])
def test_graceful_near_empty_deck(tmp_path, remaining):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{GRACEFUL}.lua").is_file():
        pytest.skip("Graceful Charity script not installed")
    own, other = _decks(tmp_path, (GRACEFUL,))
    with GoatEnvironment(str(own), str(other), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert GRACEFUL in {c.code for c in obs.hand}
        activated = discarded = emptied = False
        for _ in range(700):
            if env.is_terminal():
                assert activated
                assert discarded == (remaining == 3)
                assert emptied == (remaining == 3)
                assert env.result() == 1
                assert obs.phase == ("main1" if remaining < 3 else "draw")
                assert obs.deck_counts[0] == 0
                assert obs.life_points == (8000, 8000)
                assert env.engine.probe.loaded_script_sha256[
                    f"official/c{GRACEFUL}.lua"] == PATCHED_GRACEFUL_SHA256
                return
            actions = env.legal_actions()
            action = None
            if obs.acting_player == 0 and obs.phase == "main1" \
                    and obs.deck_counts[0] == remaining and not activated \
                    and any(a.kind == "end_phase" for a in actions):
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == GRACEFUL), None)
                assert action is not None
                activated = True
            if activated and remaining == 3 and actions[0].kind == "select_cards":
                action = actions[0]
                discarded = True
            if action is None and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               != GRACEFUL), actions[0])
            if action is None:
                action = next((a for a in actions if a.kind in ("end_phase", "pass")),
                              actions[0])
            obs = env.step(action)
            if activated and remaining < 3 and obs.deck_counts[0] == 0:
                assert env.is_terminal()
            if activated and remaining == 3 and discarded \
                    and obs.deck_counts[0] == 0 and not emptied:
                assert not env.is_terminal()
                emptied = True
    pytest.fail("Graceful did not reach the near-empty Deck boundary")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_graceful_activates_from_empty_deck_and_loses(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (GRACEFUL, UPSTART):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    own, other = _decks(tmp_path, (GRACEFUL, UPSTART))
    with GoatEnvironment(str(own), str(other), seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, UPSTART} <= {c.code for c in obs.hand}
        upstart_used = graceful_used = False
        for _ in range(700):
            if env.is_terminal():
                assert upstart_used and graceful_used
                assert env.result() == 1
                assert obs.phase == "main1"
                assert obs.deck_counts[0] == 0
                assert obs.life_points == (8000, 9000)
                assert env.engine.probe.loaded_script_sha256[
                    f"official/c{GRACEFUL}.lua"] == PATCHED_GRACEFUL_SHA256
                return
            actions = env.legal_actions()
            action = None
            if obs.acting_player == 0 and obs.phase == "main1" \
                    and any(a.kind == "end_phase" for a in actions):
                if obs.deck_counts[0] == 1 and not upstart_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == UPSTART), None)
                    assert action is not None
                    upstart_used = True
                if obs.deck_counts[0] == 0 and upstart_used and not graceful_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    assert action is not None
                    graceful_used = True
            if action is None and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               not in (GRACEFUL, UPSTART)), actions[0])
            if action is None:
                action = next((a for a in actions if a.kind in ("end_phase", "pass")),
                              actions[0])
            obs = env.step(action)
    pytest.fail("Graceful did not reach the empty-Deck activation")
