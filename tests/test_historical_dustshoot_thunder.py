"""Dustshoot sees the pre-search hand when chained to Thunder Dragon."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

DUSTSHOOT = 64697231
THUNDER = 504700054


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_dustshoot_chained_to_thunder_search_tracks_both_reveals(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"official/c{DUSTSHOOT}.lua", f"goat/c{THUNDER}.lua")
    for relative in scripts:
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    trap_deck = tmp_path / "dustshoot.ydk"
    trap_deck.write_text("#main\n" + "\n".join(map(str, (
        *([DUSTSHOOT] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    thunder_deck = tmp_path / "thunder.ydk"
    thunder_deck.write_text("#main\n" + "\n".join(map(str, (
        *([THUNDER] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(trap_deck), str(thunder_deck), seed=11,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert DUSTSHOOT in {c.code for c in observation.hand}
        assert sum(c.code == THUNDER for c in
                   env.engine.probe.observation(1).hand) == 1
        trap_set = thunder_used = dustshoot_chained = target_selected = searched = False
        revealed_hand = Counter()
        selected_code = None
        for _ in range(55):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 \
                    and not trap_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                trap_set |= action is not None
            if observation.turn == 2 and observation.acting_player == 1 \
                    and not thunder_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == THUNDER), None)
                thunder_used |= action is not None
            if thunder_used and observation.acting_player == 0 \
                    and not dustshoot_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                if action is not None:
                    assert [link.card_code for link in observation.chain] == [THUNDER]
                    assert sum(c.code == THUNDER for c in
                               observation.graveyards[1]) == 1
                    dustshoot_chained = True
            if dustshoot_chained and not target_selected \
                    and actions[0].kind == "select_card":
                assert [link.card_code for link in observation.chain] == [
                    THUNDER, DUSTSHOOT]
                revealed_hand = Counter(observation.known_opponent_hand_cards)
                assert revealed_hand == Counter(c.code for c in
                                                env.engine.probe.observation(1).hand)
                assert sum(revealed_hand.values()) >= 4
                assert THUNDER not in revealed_hand
                assert Counter(a.parameters["code"] for a in actions) == revealed_hand
                assert all("sequence" not in a.parameters for a in actions)
                action = actions[0]
                selected_code = action.parameters["code"]
                target_selected = True
            if target_selected and not searched \
                    and any(a.kind == "select_cards" for a in actions):
                action = next((a for a in actions if a.kind == "select_cards"
                               and len(a.parameters.get("cards", ())) == 2), None)
                searched |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if searched and observation.chain == () and sum(
                    c.code == THUNDER for c in
                    env.engine.probe.observation(1).hand) == 2:
                chooser = env.engine.probe.observation(0)
                searcher = env.engine.probe.observation(1)
                assert target_selected and selected_code is not None
                assert Counter(chooser.known_opponent_hand_cards) == (
                    revealed_hand - Counter((selected_code,)) +
                    Counter({THUNDER: 2}))
                assert chooser.opponent_hand_count == len(searcher.hand)
                assert searcher.known_opponent_hand_cards == ()
                assert chooser.deck_counts[1] == 33
                assert [[c.code for c in reveal.cards]
                        for reveal in chooser.private_reveals][-1] == [THUNDER, THUNDER]
                assert set(scripts).issubset(env.engine.probe.loaded_script_sha256)
                return
    pytest.fail(f"Dustshoot/Thunder chain stalled: set={trap_set} "
                f"Thunder={thunder_used} Dustshoot={dustshoot_chained}/{target_selected} "
                f"search={searched} turn={observation.turn}")
