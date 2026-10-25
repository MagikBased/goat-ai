"""Pot of Greed and the native deck-out result at the end of a long duel."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

POT = 55144522
UPSTART = 70368879
PATCHED_POT_SHA256 = "f5fe5f873c46953ff998c04558dfdc0546856e683041204feb647f91bfec9065"
EXTRA_VANILLAS = (
    32864, 549481, 1184620, 1761063, 1784619, 2118022, 2311603, 2468169,
    2483611, 2863439, 2964201, 3134241, 3170832, 3573512, 3797883,
    4035199, 4042268, 4179849, 4920010, 5265750,
)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("remaining", [1, 2])
def test_pot_near_empty_deck_and_terminal_winner(tmp_path, remaining):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{POT}.lua").is_file():
        pytest.skip("Pot of Greed script not installed")
    pot_deck = tmp_path / "pot.ydk"
    pot_deck.write_text("#main\n" + "\n".join(map(str, (
        POT, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    long_deck = tmp_path / "sixty.ydk"
    long_deck.write_text("#main\n" + "\n".join(map(str, (
        *VANILLA_DECK, *EXTRA_VANILLAS))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(pot_deck), str(long_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert POT in {c.code for c in obs.hand}
        activated = boundary_seen = emptied = False
        for _ in range(700):
            if env.is_terminal():
                assert boundary_seen
                assert activated
                assert env.result() == 1
                assert obs.deck_counts[0] == 0
                assert obs.deck_counts[1] > 0
                assert obs.phase == ("main1" if remaining == 1 else "draw")
                assert obs.life_points == (8000, 8000)
                assert emptied == (remaining == 2)
                assert f"official/c{POT}.lua" in env.engine.probe.loaded_script_sha256
                assert env.engine.probe.loaded_script_sha256[f"official/c{POT}.lua"] \
                    == PATCHED_POT_SHA256
                return
            actions = env.legal_actions()
            action = None
            if obs.acting_player == 0 and obs.phase == "main1" and not activated:
                if obs.deck_counts[0] == remaining and not boundary_seen:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == POT), None)
                    assert POT in {c.code for c in obs.hand}
                    assert action is not None
                    activated = True
                    boundary_seen = True
            if action is None and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") != POT),
                              actions[0])
            if action is None:
                action = next((a for a in actions if a.kind in ("end_phase", "pass")),
                              actions[0])
            obs = env.step(action)
            if activated and obs.deck_counts[0] == 0 and not emptied:
                assert env.is_terminal() == (remaining == 1)
                assert obs.life_points == (8000, 8000)
                emptied = remaining == 2
                assert f"official/c{POT}.lua" in env.engine.probe.loaded_script_sha256
    pytest.fail("Pot did not reach the expected deck-out state")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_pot_can_be_activated_from_an_empty_deck_and_loses(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (POT, UPSTART):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    deck = tmp_path / "pot_upstart.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        POT, UPSTART, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    long_deck = tmp_path / "sixty.ydk"
    long_deck.write_text("#main\n" + "\n".join(map(str, (
        *VANILLA_DECK, *EXTRA_VANILLAS))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), str(long_deck), seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {POT, UPSTART} <= {c.code for c in obs.hand}
        upstart_used = empty_checked = pot_used = False
        for _ in range(700):
            if env.is_terminal():
                assert upstart_used and empty_checked and pot_used
                assert env.result() == 1
                assert obs.phase == "main1"
                assert obs.deck_counts[0] == 0
                assert obs.life_points == (8000, 9000)
                assert env.engine.probe.loaded_script_sha256[f"official/c{POT}.lua"] \
                    == PATCHED_POT_SHA256
                return
            actions = env.legal_actions()
            action = None
            if obs.acting_player == 0 and obs.phase == "main1":
                if obs.deck_counts[0] == 1 and not upstart_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == UPSTART), None)
                    assert action is not None
                    upstart_used = True
                if obs.deck_counts[0] == 0 and upstart_used and not pot_used \
                        and any(a.kind == "end_phase" for a in actions):
                    assert POT in {c.code for c in obs.hand}
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == POT), None)
                    assert action is not None
                    empty_checked = True
                    pot_used = True
            if action is None and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               not in (POT, UPSTART)), actions[0])
            if action is None:
                action = next((a for a in actions if a.kind in ("end_phase", "pass")),
                              actions[0])
            obs = env.step(action)
    pytest.fail("Pot did not reach the empty-Deck activation")
