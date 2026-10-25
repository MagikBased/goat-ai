"""Dustshoot responds to Scapegoat before Sheep Tokens appear."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

GOAT = 504700123
DUSTSHOOT = 64697231
BOOK = 14087893
BOTTOMLESS = 504700052
SAKURETSU = 56120475


def _deck(path, cards):
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_dustshoot_chained_to_scapegoat_reveals_before_tokens(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{GOAT}.lua", f"official/c{DUSTSHOOT}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card scripts not installed")
    own_cards = [GOAT, BOOK, BOOK, *VANILLA_DECK[3:]]
    own_cards = [BOTTOMLESS if code == 49003308 else
                 SAKURETSU if code == 49881766 else code
                 for code in own_cards]
    own = _deck(tmp_path / "scapegoat.ydk", own_cards)
    other = _deck(tmp_path / "dustshoot.ydk", (
        DUSTSHOOT, *VANILLA_DECK[1:]))

    with GoatEnvironment(own, other, seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GOAT, BOOK, BOTTOMLESS, SAKURETSU} <= {
            card.code for card in obs.hand}
        backrow_set = 0
        dust_set = goat_used = dust_chained = selected = checked = False
        hand_before = selected_code = deck_before = None
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / "dustshoot_scapegoat.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and backrow_set < 2:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") in (BOOK, BOTTOMLESS)),
                              None)
                if action is not None:
                    backrow_set += 1
            if obs.turn == 2 and obs.acting_player == 1 and not dust_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                dust_set = action is not None
            if obs.turn == 3 and obs.acting_player == 0 and dust_set \
                    and not goat_used:
                assert backrow_set == 2 and len(obs.hand) == 5
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == GOAT), None)
                goat_used = action is not None
            if goat_used and obs.acting_player == 1 and not dust_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                dust_chained = action is not None
                if dust_chained:
                    assert [link.card_code for link in obs.chain] == [GOAT]
                    assert obs.opponent_hand_count == 4
                    assert not any(c.controller == 0 and c.zone == "monster"
                                   for c in obs.field)
                    hand_before = Counter(c.code for c in
                                          env.engine.probe.observation(0).hand)
                    deck_before = obs.deck_counts[0]
            if dust_chained and not selected and actions[0].kind == "select_card":
                assert obs.acting_player == 1
                assert Counter(obs.known_opponent_hand_cards) == hand_before
                assert not env.engine.probe.observation(0).private_reveals
                assert all("sequence" not in a.parameters for a in actions)
                action = actions[0]
                selected_code = action.parameters["code"]
                selected = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if selected and not checked and GOAT in {c.code for c in
                                                       obs.graveyards[0]} and not obs.chain:
                own_view = env.engine.probe.observation(0)
                dust_view = env.engine.probe.observation(1)
                assert sum(c.controller == 0 and c.zone == "monster"
                           for c in own_view.field) == 4
                assert own_view.deck_counts[0] == deck_before + 1
                assert Counter(c.code for c in own_view.hand) == (
                    hand_before - Counter((selected_code,)))
                assert Counter(dust_view.known_opponent_hand_cards) == (
                    hand_before - Counter((selected_code,)))
                assert not own_view.private_reveals
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail("Dustshoot / Scapegoat chain did not finish")
