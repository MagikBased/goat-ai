"""Pot of Greed and the native deck-out result at the end of a long duel."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

POT = 55144522
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
                assert activated == (remaining == 2)
                assert env.result() == 1
                assert obs.deck_counts[0] == 0
                assert obs.deck_counts[1] > 0
                assert obs.phase == "draw"
                assert obs.life_points == (8000, 8000)
                if activated:
                    assert emptied
                    assert f"official/c{POT}.lua" in env.engine.probe.loaded_script_sha256
                return
            actions = env.legal_actions()
            action = None
            if obs.acting_player == 0 and obs.phase == "main1" and not activated:
                if obs.deck_counts[0] == remaining and not boundary_seen:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == POT), None)
                    assert POT in {c.code for c in obs.hand}
                    assert (action is not None) == (remaining == 2)
                    activated = action is not None
                    boundary_seen = True
            if action is None and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") != POT),
                              actions[0])
            if action is None:
                action = next((a for a in actions if a.kind in ("end_phase", "pass")),
                              actions[0])
            obs = env.step(action)
            if activated and obs.deck_counts[0] == 0 and not emptied:
                assert not env.is_terminal()
                assert obs.life_points == (8000, 8000)
                emptied = True
                assert f"official/c{POT}.lua" in env.engine.probe.loaded_script_sha256
    pytest.fail("Pot did not reach the expected deck-out state")
