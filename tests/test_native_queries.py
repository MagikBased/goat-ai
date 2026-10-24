import os
from pathlib import Path

import pytest

from goat_ai.engine.native_messages import decode_decision
from goat_ai.engine.native_queries import decode_location
from goat_ai.engine.ocgcore_probe import OcgcoreProbe
from goat_ai.engine.probe_deck import VANILLA_DECK


def test_query_location_rejects_truncation():
    with pytest.raises(ValueError, match="header"):
        decode_location(b"\x00")
    with pytest.raises(ValueError, match="size mismatch"):
        decode_location(b"\x01\x00\x00\x00")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_native_observation_hides_opponent_hand_and_deck_order():
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])

    def observe(opponent_deck):
        with OcgcoreProbe(root / "build/libocgcore.so", root / "database/cards.cdb",
                          root / "scripts") as probe:
            probe.first_decision(42, VANILLA_DECK, opponent_deck)
            return probe.observation(0), probe.observation(1)

    viewer_a, opponent_a = observe(VANILLA_DECK)
    viewer_b, opponent_b = observe(tuple(reversed(VANILLA_DECK)))
    assert viewer_a == viewer_b
    assert opponent_a.hand != opponent_b.hand
    assert viewer_a.turn == 1 and viewer_a.phase == "draw"
    assert viewer_a.life_points == (8000, 8000)
    assert viewer_a.deck_counts == (34, 35)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_native_observation_redacts_opponent_facedown_monster():
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    with OcgcoreProbe(root / "build/libocgcore.so", root / "database/cards.cdb",
                      root / "scripts") as probe:
        probe.first_decision(42, VANILLA_DECK)
        probe.pass_empty_chain()
        probe.pass_empty_chain()
        set_action = next(choice for choice in decode_decision(probe._pending_message).choices
                          if choice.kind == "set_monster")
        probe.respond(set_action.response)
        place = decode_decision(probe._pending_message).choices[0]
        probe.respond(place.response)
        own = probe.observation(0)
        opponent = probe.observation(1)
        assert own.field[0].code == set_action.code
        assert opponent.field[0].code is None
        assert opponent.field[0].position == "facedown"
        assert opponent.field[0].orientation == "defense"
