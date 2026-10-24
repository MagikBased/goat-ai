"""GOAT trigger ordering through an actual Tribute Summon and chain."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.decks import read_ydk
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment

SANGAN = 504700178  # GOAT variant
THESTALOS = 26205777


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_sangan_trigger_precedes_thestalos_when_tributed_for_its_summon(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/goat/c{SANGAN}.lua").is_file() or not (
        root / f"scripts/official/c{THESTALOS}.lua"
    ).is_file():
        pytest.skip("full card script checkout not installed")
    decks = Path(__file__).resolve().parent.parent / "examples/decks"
    cards = list(read_ydk(decks / "cannon_probe.ydk").main)
    cards[0:2] = [SANGAN, THESTALOS]
    deck = tmp_path / "sangan_thestalos.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, cards)) + "\n")

    with GoatEnvironment(str(deck), str(decks / "vanilla_probe.ydk"), seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        sangan_summoned = thestalos_summoned = sangan_tributed = False
        chain_seen = search_seen = False
        before_deck = before_hand = before_opponent_hand = None
        for _ in range(40):
            choices = env.legal_actions()

            def choice(kind, code=None, actions=choices):
                return next((action for action in actions if action.kind == kind
                             and (code is None or action.parameters.get("code") == code)), None)

            if sangan_tributed and observation.chain and not chain_seen:
                assert tuple((link.index, link.card_code) for link in observation.chain) == (
                    (1, SANGAN), (2, THESTALOS))
                assert any(card.code == SANGAN for card in observation.graveyards[0])
                assert any(card.code == THESTALOS for card in observation.field)
                chain_seen = True
            if chain_seen and not search_seen and observation.acting_player == 0 and (
                choice("select_card") is not None
            ):
                # Thestalos resolves first: the opponent discards before Sangan searches.
                assert observation.chain[0].card_code == SANGAN
                assert observation.opponent_hand_count == before_opponent_hand - 1
                assert observation.deck_counts[0] == before_deck
                search_seen = True
            if search_seen and not observation.chain:
                assert observation.deck_counts[0] == before_deck - 1
                assert len(observation.hand) == before_hand + 1
                assert observation.opponent_hand_count == before_opponent_hand - 1
                return

            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not sangan_summoned:
                action = choice("normal_summon", SANGAN)
                sangan_summoned |= action is not None
            if (observation.turn == 3 and observation.acting_player == 0
                    and sangan_summoned and not thestalos_summoned):
                action = choice("normal_summon", THESTALOS)
                thestalos_summoned |= action is not None
                if thestalos_summoned:
                    before_deck = observation.deck_counts[0]
                    before_hand = len(observation.hand) - 1  # Thestalos leaves hand
                    before_opponent_hand = observation.opponent_hand_count
            if thestalos_summoned and not sangan_tributed and action is None:
                action = choice("tribute", SANGAN)
                sangan_tributed |= action is not None
            if action is None:
                action = choice("end_phase") or choice("pass") or choices[0]
            observation = env.step(action)
        pytest.fail("Sangan/Thestalos trigger sequence did not resolve within 40 decisions")
