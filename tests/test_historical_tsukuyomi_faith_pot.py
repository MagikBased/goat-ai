"""Tsukuyomi and Magician of Faith replay the same Pot across turns."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

POT = 55144522
FAITH = 31560081
TSUKUYOMI = 34853266


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_tsukuyomi_faith_reuses_pot_on_three_turns(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (POT, FAITH, TSUKUYOMI)}
    if any(not (root / "scripts" / relative).is_file() for relative in scripts):
        pytest.skip("Pot, Faith, or Tsukuyomi script not installed")
    deck = tmp_path / "faith_tsukuyomi.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        POT, *([FAITH] * 3), *([TSUKUYOMI] * 3),
        *VANILLA_DECK[7:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert {POT, FAITH, TSUKUYOMI}.issubset(c.code for c in observation.hand)
        initial_deck_count = observation.deck_counts[0]
        pot_uses = recoveries = 0
        faith_set = first_flip = tsuk_summoned = tsuk_targeted = False
        faith_reset = second_flip = False
        for _ in range(130):
            actions = env.legal_actions()
            action = None
            if observation.acting_player == 0 and observation.turn in (1, 3, 5):
                if pot_uses == (0 if observation.turn == 1 else
                               1 if observation.turn == 3 else 2):
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == POT), None)
                    if action is not None and observation.turn in (3, 5):
                        opponent = env.engine.probe.observation(1)
                        assert POT in opponent.known_opponent_hand_cards
                        assert sum(reveal.recipient == 1 and
                                   [card.code for card in reveal.cards] == [POT]
                                   for reveal in opponent.private_reveals) == recoveries
                    pot_uses += action is not None
            if observation.turn == 1 and observation.acting_player == 0 \
                    and pot_uses == 1 and not faith_set and action is None:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == FAITH), None)
                faith_set |= action is not None
            if observation.turn == 3 and observation.acting_player == 0:
                if faith_set and not first_flip:
                    action = next((a for a in actions if a.kind == "flip_summon"
                                   and a.parameters.get("code") == FAITH), action)
                    first_flip |= action is not None and action.kind == "flip_summon"
                if first_flip and recoveries == 0 and actions[0].kind == "select_card":
                    assert observation.chain[0].card_code == FAITH
                    action = next((a for a in actions if a.parameters.get("code") == POT
                                   and a.parameters.get("location") == 16), None)
                    recoveries += action is not None
                if recoveries == 1 and pot_uses == 2 and not tsuk_summoned \
                        and action is None and not observation.chain \
                        and POT in {c.code for c in observation.graveyards[0]}:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == TSUKUYOMI), None)
                    tsuk_summoned |= action is not None
                if tsuk_summoned and not tsuk_targeted \
                        and actions[0].kind == "select_card":
                    assert observation.chain[0].card_code == TSUKUYOMI
                    action = next((a for a in actions if a.parameters.get("code") == FAITH
                                   and a.parameters.get("controller") == 0), None)
                    tsuk_targeted |= action is not None
            if tsuk_targeted and observation.turn == 4 and not faith_reset:
                owner = env.engine.probe.observation(0)
                opponent = env.engine.probe.observation(1)
                assert any(c.code == FAITH and c.position == "facedown"
                           for c in owner.field)
                assert any(c.code is None and c.controller == 0
                           and c.zone == "monster" and c.position == "facedown"
                           for c in opponent.field)
                assert any(c.code == FAITH for c in opponent.known_opponent_field_cards)
                assert TSUKUYOMI in {c.code for c in owner.hand}
                faith_reset = True
            if observation.turn == 5 and observation.acting_player == 0:
                if faith_reset and not second_flip:
                    action = next((a for a in actions if a.kind == "flip_summon"
                                   and a.parameters.get("code") == FAITH), action)
                    second_flip |= action is not None and action.kind == "flip_summon"
                if second_flip and recoveries == 1 and actions[0].kind == "select_card":
                    assert observation.chain[0].card_code == FAITH
                    action = next((a for a in actions if a.parameters.get("code") == POT
                                   and a.parameters.get("location") == 16), None)
                    recoveries += action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if pot_uses == 3 and POT in {c.code for c in observation.graveyards[0]} \
                    and not observation.chain and observation.turn == 5:
                assert recoveries == 2 and faith_reset and second_flip
                assert initial_deck_count - observation.deck_counts[0] == 8
                assert sum(c.code == FAITH for c in observation.field) == 1
                assert TSUKUYOMI in {c.code for c in observation.hand}
                assert POT not in env.engine.probe.observation(1).known_opponent_hand_cards
                assert scripts.issubset(env.engine.probe.loaded_script_sha256)
                return
    pytest.fail(f"Faith/Tsukuyomi/Pot line stalled: Pot={pot_uses} "
                f"Faith={faith_set}/{first_flip}/{second_flip}/{recoveries} "
                f"Tsukuyomi={tsuk_summoned}/{tsuk_targeted}/{faith_reset} "
                f"turn={observation.turn}")
