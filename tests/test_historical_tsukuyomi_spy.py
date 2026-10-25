"""Tsukuyomi resets Spy for a second Deck recruit on the next turn."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

SPY = 504700044
GUARD = 37101832
TSUKUYOMI = 34853266


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_tsukuyomi_resets_spy_for_second_recruit(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"goat/c{SPY}.lua", f"official/c{GUARD}.lua",
               f"official/c{TSUKUYOMI}.lua")
    for relative in scripts:
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    deck = tmp_path / "spy_tsukuyomi.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        *([SPY] * 3), *([GUARD] * 3), *([TSUKUYOMI] * 3),
        *VANILLA_DECK[9:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=4,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert {SPY, TSUKUYOMI}.issubset(card.code for card in observation.hand)
        set_spy = first_flip = first_recruit = tsuk_summoned = tsuk_targeted = False
        spy_reset = second_flip = second_recruit = False
        initial_deck_count = observation.deck_counts[0]
        for _ in range(120):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not set_spy:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == SPY), None)
                set_spy |= action is not None
            if observation.turn == 3 and observation.acting_player == 0:
                if not first_flip:
                    action = next((a for a in actions if a.kind == "flip_summon"
                                   and a.parameters.get("code") == SPY), None)
                    first_flip |= action is not None
                if first_flip and not first_recruit and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == GUARD
                                   and a.parameters.get("location") == 1), None)
                    first_recruit |= action is not None
                if first_recruit and not tsuk_summoned and action is None \
                        and sum(c.code == GUARD for c in observation.field) == 1:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == TSUKUYOMI), None)
                    tsuk_summoned |= action is not None
                if tsuk_summoned and not tsuk_targeted \
                        and actions[0].kind == "select_card":
                    assert [link.card_code for link in observation.chain] == [TSUKUYOMI]
                    action = next((a for a in actions if a.parameters.get("code") == SPY
                                   and a.parameters.get("controller") == 0), None)
                    tsuk_targeted |= action is not None
            if tsuk_targeted and observation.turn == 4 and not spy_reset:
                owner = env.engine.probe.observation(0)
                opponent = env.engine.probe.observation(1)
                assert any(c.code == SPY and c.position == "facedown"
                           for c in owner.field)
                assert any(c.controller == 0 and c.zone == "monster"
                           and c.position == "facedown" and c.code is None
                           for c in opponent.field)
                assert any(c.code == SPY for c in opponent.known_opponent_field_cards)
                assert TSUKUYOMI in {c.code for c in owner.hand}
                spy_reset = True
            if observation.turn == 5 and observation.acting_player == 0:
                if spy_reset and not second_flip:
                    action = next((a for a in actions if a.kind == "flip_summon"
                                   and a.parameters.get("code") == SPY), None)
                    second_flip |= action is not None
                if second_flip and not second_recruit and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == GUARD
                                   and a.parameters.get("location") == 1), None)
                    second_recruit |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if second_recruit and sum(c.code == GUARD for c in observation.field) == 2:
                assert sum(c.code == SPY for c in observation.field) == 1
                assert initial_deck_count - observation.deck_counts[0] == 4
                assert TSUKUYOMI in {c.code for c in observation.hand}
                assert not observation.graveyards[0]
                assert set(scripts).issubset(env.engine.probe.loaded_script_sha256)
                return
    pytest.fail(f"Spy/Tsukuyomi line stalled: first={first_flip}/{first_recruit} "
                f"tsuk={tsuk_summoned}/{tsuk_targeted}/{spy_reset} "
                f"second={second_flip}/{second_recruit} turn={observation.turn}")
