"""Dustshoot reveals the hand before a chained Pot of Greed draws new cards."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

POT_OF_GREED = 55144522
DUSTSHOOT = 64697231


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_dustshoot_chained_to_pot_does_not_reveal_later_draws(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (POT_OF_GREED, DUSTSHOOT):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    pot_deck = tmp_path / "pot.ydk"
    trap_deck = tmp_path / "dustshoot.ydk"
    pot_deck.write_text("#main\n" + "\n".join(map(str, (
        POT_OF_GREED, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    trap_deck.write_text("#main\n" + "\n".join(map(str, (
        *([DUSTSHOOT] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(pot_deck), str(trap_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert POT_OF_GREED in {c.code for c in obs.hand}
        trap_set = pot_used = trap_chained = monster_chosen = False
        revealed = Counter()
        selected_code = before_deck = None
        for _ in range(70):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1 and not trap_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                trap_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not pot_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == POT_OF_GREED), None)
                if action is not None:
                    before_deck = obs.deck_counts[0]
                    pot_used = True
            if pot_used and obs.acting_player == 1 and not trap_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                if action is not None:
                    assert obs.chain[0].card_code == POT_OF_GREED
                    trap_chained = True
            if trap_chained and not monster_chosen and actions[0].kind == "select_card":
                assert [(link.index, link.card_code) for link in obs.chain] == [
                    (1, POT_OF_GREED), (2, DUSTSHOOT)]
                revealed = Counter(card.code for event in obs.private_reveals
                                   if event.recipient == 1 for card in event.cards
                                   if card.controller == 0 and card.location == 2)
                assert revealed
                assert Counter(obs.known_opponent_hand_cards) == revealed
                assert Counter(a.parameters["code"] for a in actions) == revealed
                assert all("sequence" not in a.parameters for a in actions)
                action = actions[0]
                selected_code = action.parameters["code"]
                monster_chosen = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if monster_chosen and POT_OF_GREED in {c.code for c in obs.graveyards[0]}:
                chooser = env.engine.probe.observation(1)
                pot_player = env.engine.probe.observation(0)
                assert obs.chain == ()
                assert chooser.deck_counts[0] == before_deck - 1
                assert Counter(chooser.known_opponent_hand_cards) == (
                    revealed - Counter((selected_code,)))
                assert chooser.opponent_hand_count == sum(revealed.values()) + 1
                assert not pot_player.known_opponent_hand_cards
                assert {f"official/c{code}.lua" for code in (
                    POT_OF_GREED, DUSTSHOOT)}.issubset(
                        env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Dustshoot/Pot chain did not finish")
