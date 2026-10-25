"""Dustshoot reveals the hand before chained draw Spells add private cards."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

POT_OF_GREED = 55144522
UPSTART_GOBLIN = 70368879
DUSTSHOOT = 64697231
GRACEFUL_CHARITY = 79571449


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("draw_spell,draw_count", [
    (POT_OF_GREED, 2), (UPSTART_GOBLIN, 1),
])
def test_dustshoot_chained_to_draw_spell_does_not_reveal_later_draws(
    tmp_path, draw_spell, draw_count,
):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (draw_spell, DUSTSHOOT):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    draw_deck = tmp_path / "draw_spell.ydk"
    trap_deck = tmp_path / "dustshoot.ydk"
    draw_deck.write_text("#main\n" + "\n".join(map(str, (
        draw_spell, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    trap_deck.write_text("#main\n" + "\n".join(map(str, (
        *([DUSTSHOOT] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(draw_deck), str(trap_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert draw_spell in {c.code for c in obs.hand}
        trap_set = spell_used = trap_chained = monster_chosen = False
        revealed = Counter()
        selected_code = before_deck = None
        for _ in range(70):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1 and not trap_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                trap_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not spell_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == draw_spell), None)
                if action is not None:
                    before_deck = obs.deck_counts[0]
                    spell_used = True
            if spell_used and obs.acting_player == 1 and not trap_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                if action is not None:
                    assert obs.chain[0].card_code == draw_spell
                    trap_chained = True
            if trap_chained and not monster_chosen and actions[0].kind == "select_card":
                assert [(link.index, link.card_code) for link in obs.chain] == [
                    (1, draw_spell), (2, DUSTSHOOT)]
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
            if monster_chosen and draw_spell in {c.code for c in obs.graveyards[0]}:
                chooser = env.engine.probe.observation(1)
                spell_player = env.engine.probe.observation(0)
                assert obs.chain == ()
                assert chooser.deck_counts[0] == before_deck + 1 - draw_count
                assert Counter(chooser.known_opponent_hand_cards) == (
                    revealed - Counter((selected_code,)))
                assert chooser.opponent_hand_count == (
                    sum(revealed.values()) - 1 + draw_count)
                assert chooser.life_points == (
                    8000, 9000 if draw_spell == UPSTART_GOBLIN else 8000)
                assert not spell_player.known_opponent_hand_cards
                assert {f"official/c{code}.lua" for code in (
                    draw_spell, DUSTSHOOT)}.issubset(
                        env.engine.probe.loaded_script_sha256)
                return
    pytest.fail(f"Dustshoot/draw Spell {draw_spell} chain did not finish")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_dustshoot_chained_to_graceful_tracks_only_revealed_hand_cards(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (GRACEFUL_CHARITY, DUSTSHOOT):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    draw_deck = tmp_path / "graceful.ydk"
    trap_deck = tmp_path / "dustshoot.ydk"
    draw_deck.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL_CHARITY, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    trap_deck.write_text("#main\n" + "\n".join(map(str, (
        *([DUSTSHOOT] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(draw_deck), str(trap_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert GRACEFUL_CHARITY in {c.code for c in obs.hand}
        trap_set = spell_used = trap_chained = monster_chosen = discarded = False
        revealed = Counter()
        returned_code = None
        deck_before = None
        selected = Counter()
        for _ in range(75):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1 and not trap_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                trap_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not spell_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == GRACEFUL_CHARITY), None)
                if action is not None:
                    deck_before = obs.deck_counts[0]
                    spell_used = True
            if spell_used and obs.acting_player == 1 and not trap_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                trap_chained |= action is not None
            if trap_chained and not monster_chosen and actions[0].kind == "select_card":
                assert [(link.index, link.card_code) for link in obs.chain] == [
                    (1, GRACEFUL_CHARITY), (2, DUSTSHOOT)]
                revealed = Counter(c.code for event in obs.private_reveals
                                   if event.recipient == 1 for c in event.cards
                                   if c.controller == 0 and c.location == 2)
                assert revealed
                assert Counter(obs.known_opponent_hand_cards) == revealed
                assert Counter(a.parameters["code"] for a in actions) == revealed
                assert all("sequence" not in a.parameters for a in actions)
                action = actions[0]
                returned_code = action.parameters["code"]
                monster_chosen = True
            if monster_chosen and not discarded and actions[0].kind == "select_cards":
                assert obs.acting_player == 0
                assert obs.deck_counts[0] == deck_before + 1 - 3
                assert Counter(env.engine.probe.observation(1).known_opponent_hand_cards) \
                    == revealed - Counter((returned_code,))
                assert len(obs.hand) == sum(revealed.values()) - 1 + 3
                assert all(len(a.parameters["cards"]) == 2 for a in actions)
                action = actions[0]
                selected = Counter(c["code"] for c in action.parameters["cards"])
                discarded = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if discarded and GRACEFUL_CHARITY in {c.code for c in obs.graveyards[0]} \
                    and not obs.chain:
                watcher = env.engine.probe.observation(1)
                assert obs.deck_counts[0] == deck_before - 2
                assert Counter(watcher.known_opponent_hand_cards) == (
                    revealed - Counter((returned_code,)) - selected)
                assert watcher.opponent_hand_count == len(obs.hand)
                assert len(obs.hand) == sum(revealed.values())
                assert not env.engine.probe.observation(0).private_reveals
                assert {f"official/c{code}.lua" for code in (
                    GRACEFUL_CHARITY, DUSTSHOOT)}.issubset(
                        env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Dustshoot/Graceful chain did not reach the discard")
