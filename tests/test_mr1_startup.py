"""MR1 is a native startup feasibility probe, not an Edison duel adapter."""

import hashlib
import os
from pathlib import Path

import pytest

from goat_ai.engine.ocgcore_probe import GOAT_FLAGS, MR1_FLAGS, OcgcoreProbe
from goat_ai.engine.probe_deck import VANILLA_DECK


def test_mr1_probe_rejects_unknown_modes_before_loading_native_assets():
    with pytest.raises(ValueError, match="startup mode"):
        OcgcoreProbe(Path("missing.so"), Path("missing.cdb"), Path("missing"),
                     mode="edison")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_mr1_startup_uses_separate_flags_and_unmodified_utility():
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    paths = (root / "build/libocgcore.so", root / "database/cards.cdb",
             root / "scripts")
    utility_hash = hashlib.sha256((root / "scripts/utility.lua").read_bytes()).hexdigest()
    with OcgcoreProbe(*paths, mode="mr1_startup") as mr1, OcgcoreProbe(*paths) as goat:
        first = mr1.first_decision(42, VANILLA_DECK)
        goat_first = goat.first_decision(42, VANILLA_DECK)
        assert (first.flags, goat_first.flags) == (MR1_FLAGS, GOAT_FLAGS)
        assert first.flags != goat_first.flags
        assert first.core_version == goat_first.core_version == (11, 0)
        assert first.hand_counts == goat_first.hand_counts == (6, 5)
        assert first.deck_counts == goat_first.deck_counts == (34, 35)
        assert first.draw_events == goat_first.draw_events == ((0, 5), (1, 5), (0, 1))
        assert mr1.loaded_script_sha256["utility.lua"] == utility_hash
        assert goat.loaded_script_sha256["utility.lua"] != utility_hash
        with pytest.raises(RuntimeError, match="does not expose gameplay"):
            mr1.decode_pending()
        with pytest.raises(RuntimeError, match="does not expose gameplay"):
            mr1.observation(0)
        with pytest.raises(RuntimeError, match="does not resolve gameplay"):
            mr1.respond(-1)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_mr1_startup_rejects_effect_cards_extra_decks_and_replay_reconstruction():
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    paths = (root / "build/libocgcore.so", root / "database/cards.cdb",
             root / "scripts")
    with OcgcoreProbe(*paths, mode="mr1_startup") as probe:
        effect_deck = (55144522, *VANILLA_DECK[1:])  # Pot of Greed
        with pytest.raises(ValueError, match="normal monsters only"):
            probe.first_decision(42, effect_deck)
        with pytest.raises(ValueError, match="empty Extra Decks"):
            probe.first_decision(42, VANILLA_DECK, extra=(44508094,))
        with pytest.raises(ValueError, match="does not reconstruct replays"):
            probe.first_replay_decision((43, 44, 45, 46), VANILLA_DECK,
                                        VANILLA_DECK)
