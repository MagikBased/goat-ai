"""Source-backed Flip Effect regression on a real GOAT-mode duel."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

DEKOICHI = 87621407


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_dekoichi_flip_summon_draws_one_without_bokoichi(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / "scripts/official/c87621407.lua").is_file():
        pytest.skip("full card script checkout not installed")
    cards = (DEKOICHI,) + VANILLA_DECK[1:]
    deck = tmp_path / "dekoichi.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, cards)) + "\n")
    with GoatEnvironment(str(deck), str(deck), seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        set_card = False
        flipped = False
        before: tuple[int, int] | None = None
        for _ in range(40):
            choices = env.legal_actions()
            action = None
            if observation.acting_player == 0 and observation.turn == 1 and not set_card:
                action = next((choice for choice in choices if choice.kind == "set_monster"
                               and choice.parameters.get("code") == DEKOICHI), None)
                set_card |= action is not None
            if observation.acting_player == 0 and observation.turn == 3 and not flipped:
                action = next((choice for choice in choices if choice.kind == "flip_summon"
                               and choice.parameters.get("code") == DEKOICHI), None)
                if action is not None:
                    assert set_card
                    flipped = True
                    before = (observation.deck_counts[0], len(observation.hand))
            if action is None:
                action = next((choice for choice in choices
                               if choice.kind == "end_phase"), None)
            if action is None:
                action = next((choice for choice in choices if choice.kind == "pass"),
                              choices[0])
            observation = env.step(action)
            if flipped and before is not None and observation.deck_counts[0] == before[0] - 1:
                assert len(observation.hand) == before[1] + 1
                assert any(card.code == DEKOICHI and card.position == "faceup"
                           for card in observation.field)
                return
        pytest.fail("Dekoichi Flip Effect did not resolve within 40 decisions")
