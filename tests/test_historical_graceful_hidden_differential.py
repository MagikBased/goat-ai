"""Graceful's private draw must not change the opponent's decision view."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

GRACEFUL = 79571449


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_graceful_drawn_card_swap_does_not_change_opponent_view(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{GRACEFUL}.lua").is_file():
        pytest.skip("Graceful Charity script not installed")
    first = [GRACEFUL, *VANILLA_DECK[1:]]
    second = first.copy()
    second[2], second[39] = second[39], second[2]
    assert sorted(first) == sorted(second)

    def run(label, cards):
        deck = tmp_path / f"{label}.ydk"
        deck.write_text("#main\n" + "\n".join(map(str, cards))
                        + "\n#extra\n!side\n")
        with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk",
                             seed=52, engine=ExperimentalOcgcoreEngine(root)) as env:
            obs = env.reset()
            opening = obs
            assert GRACEFUL in {c.code for c in obs.hand}
            for _ in range(20):
                actions = env.legal_actions()
                if actions[0].kind == "select_cards":
                    assert obs.viewer == obs.acting_player == 0
                    assert len(obs.hand) == len(opening.hand) + 2
                    hand_during = tuple(sorted(c.code for c in obs.hand))
                    opponent_during = env.engine.probe.observation(1)
                    assert opponent_during.opponent_hand_count == len(obs.hand)
                    assert not opponent_during.private_reveals
                    selected = next(a for a in actions if sorted(
                        card["code"] for card in a.parameters["cards"])
                        == [13039848, 49003308])
                    obs = env.step(selected)
                    break
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == GRACEFUL), None)
                if action is None:
                    action = next((a for a in actions if a.kind == "pass"), actions[0])
                obs = env.step(action)
            else:
                pytest.fail("Graceful discard decision not reached")

            assert {13039848, 49003308} <= {c.code for c in obs.graveyards[0]}
            assert obs.deck_counts[0] == opening.deck_counts[0] - 3
            opponent_after = env.engine.probe.observation(1)
            assert not opponent_after.private_reveals
            for _ in range(25):
                if obs.turn == 2 and obs.acting_player == 1 \
                        and obs.phase == "main1" and any(
                            a.kind == "normal_summon" for a in env.legal_actions()):
                    assert f"official/c{GRACEFUL}.lua" in (
                        env.engine.probe.loaded_script_sha256)
                    return (opening, hand_during, opponent_during,
                            opponent_after, obs, env.legal_actions())
                actions = env.legal_actions()
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
                obs = env.step(action)
        pytest.fail("opponent's next Main Phase decision not reached")

    left = run("original", first)
    right = run("reordered", second)
    assert left[0] == right[0]  # Same visible opening hand and deck multiset.
    assert left[1] != right[1]  # Graceful actually drew different private cards.
    assert left[2] == right[2]  # During the private discard choice.
    assert left[3] == right[3]  # After the same public discards.
    assert left[4] == right[4]  # At the opponent's next decision.
    assert left[5] == right[5]  # Its complete legal-action list is unchanged.
