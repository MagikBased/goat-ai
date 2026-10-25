"""Book can reset Dekoichi before its already activated Flip Effect resolves."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.observations import TargetSlotView
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

DEKOICHI = 87621407
BOOK = 14087893


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_book", [False, True])
def test_book_chained_to_dekoichi_flip_keeps_the_draw(tmp_path, chain_book):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (DEKOICHI, BOOK)}
    if any(not (root / "scripts" / relative).is_file() for relative in scripts):
        pytest.skip("required card script not installed")
    dekoichi_deck = tmp_path / "dekoichi.ydk"
    dekoichi_deck.write_text("#main\n" + "\n".join(map(str, (
        *([DEKOICHI] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    book_deck = tmp_path / "book.ydk"
    book_deck.write_text("#main\n" + "\n".join(map(str, (
        BOOK, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(dekoichi_deck), str(book_deck), seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert DEKOICHI in {card.code for card in obs.hand}
        assert BOOK in {card.code for card in env.engine.probe.observation(1).hand}
        set_monster = set_book = flipped = responded = targeted = checked = False
        two_link_seen = False
        deck_before = hand_before = None
        agents = (RandomAgent(15), RandomAgent(16))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"dekoichi_book_chain_{chain_book}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not set_monster:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == DEKOICHI), None)
                set_monster |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not set_book:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == BOOK), None)
                set_book |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not flipped:
                action = next((a for a in actions if a.kind == "flip_summon"
                               and a.parameters.get("code") == DEKOICHI), None)
                if action is not None:
                    deck_before = obs.deck_counts[0]
                    hand_before = len(obs.hand)
                    flipped = True
            if flipped and obs.acting_player == 1 and not responded and obs.chain:
                assert [link.card_code for link in obs.chain] == [DEKOICHI]
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK), None)
                assert option is not None
                action = option if chain_book else next(a for a in actions if a.kind == "pass")
                responded = True
            if chain_book and responded and not targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 0
                               and a.parameters.get("code") == DEKOICHI), None)
                targeted |= action is not None
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if targeted and len(obs.chain) == 2:
                assert [link.card_code for link in obs.chain] == [DEKOICHI, BOOK]
                dekoichi = next(card for card in obs.field if card.code == DEKOICHI)
                assert obs.chain[1].targets == (
                    TargetSlotView(0, "monster", dekoichi.sequence),)
                two_link_seen = True
            if responded and not checked and obs.turn == 3 and obs.acting_player == 0 \
                    and obs.phase == "main1" and not obs.chain \
                    and obs.deck_counts[0] == deck_before - 1:
                assert len(obs.hand) == hand_before + 1
                assert obs.life_points == (8000, 8000)
                own = env.engine.probe.observation(0)
                opponent = env.engine.probe.observation(1)
                if chain_book:
                    assert targeted and two_link_seen
                    assert BOOK in {card.code for card in obs.graveyards[1]}
                    assert any(card.controller == 0 and card.code == DEKOICHI
                               and card.position == "facedown" for card in own.field)
                    assert any(card.controller == 0 and card.code is None
                               and card.position == "facedown" for card in opponent.field)
                    assert any(card.code == DEKOICHI
                               for card in opponent.known_opponent_field_cards)
                    assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                else:
                    assert any(card.controller == 0 and card.code == DEKOICHI
                               and card.position == "faceup" for card in own.field)
                    assert BOOK not in {card.code for card in obs.graveyards[1]}
                checked = True
    pytest.fail("Dekoichi / Book chain duel exceeded 5000 decisions")
