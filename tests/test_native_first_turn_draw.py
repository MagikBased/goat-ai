"""The GOAT first player draws on turn one; the second draws on turn two."""

import os
from dataclasses import replace
from pathlib import Path

import pytest

from goat_ai.engine import RulesProfile
from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine
from goat_ai.environments import GoatEnvironment


@pytest.mark.parametrize("change", (
    {"name": "other"},
    {"april_2005_banlist": False},
    {"first_turn_draw": False},
    {"first_turn_draw": "false"},
    {"obsolete_ignition_priority": False},
    {"side_deck_policy": "unsupported"},
))
def test_native_adapter_rejects_profiles_its_core_does_not_implement(change):
    with pytest.raises(ValueError, match="does not support"):
        RestrictedOcgcoreEngine(".cache/goat-ai", replace(RulesProfile(), **change))


def test_native_adapter_accepts_community_side_deck_validation_policy():
    profile = RulesProfile(side_deck_policy="community")
    assert RestrictedOcgcoreEngine(".cache/goat-ai", profile).ruleset == profile


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_goat_first_turn_draw_and_second_player_first_draw():
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck = Path(__file__).resolve().parent.parent / "examples/decks/vanilla_probe.ydk"
    with GoatEnvironment(str(deck), str(deck), seed=42,
                         engine=RestrictedOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert (observation.turn, observation.phase, observation.acting_player) == (1, "draw", 0)
        assert len(observation.hand) == 6
        assert observation.opponent_hand_count == 5
        assert observation.deck_counts == (34, 35)
        assert observation.public_history[:2] == ("turn:1", "phase:draw")

        for _ in range(12):
            if observation.turn == 2 and observation.acting_player == 1:
                break
            actions = env.legal_actions()
            action = next((item for item in actions if item.kind == "pass"), None)
            if action is None:
                action = next(item for item in actions if item.kind == "end_phase")
            observation = env.step(action)
        else:
            pytest.fail("passing turn one did not reach player two's Draw Phase")

        assert observation.phase == "draw"
        assert len(observation.hand) == 6
        assert observation.opponent_hand_count == 6
        assert observation.deck_counts == (34, 34)
        assert observation.public_history[-2:] == ("turn:2", "phase:draw")
