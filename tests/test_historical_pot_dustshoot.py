"""Pot's two-card draw opens Dustshoot only after Pot resolves."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

POT = 55144522
DUSTSHOOT = 64697231
BOOK = 14087893
BOTTOMLESS = 504700052
SAKURETSU = 56120475


def _deck(path, cards):
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("play_pot", [False, True])
def test_pot_draw_opens_dustshoot_only_after_chain(play_pot, tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (POT, DUSTSHOOT)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card scripts not installed")
    own_cards = [POT, BOOK, BOOK, *VANILLA_DECK[3:]]
    own_cards = [BOTTOMLESS if code == 49003308 else
                 SAKURETSU if code == 49881766 else code
                 for code in own_cards]
    own = _deck(tmp_path / "pot.ydk", own_cards)
    other = _deck(tmp_path / "dustshoot.ydk", (DUSTSHOOT, *VANILLA_DECK[1:]))

    with GoatEnvironment(own, other, seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {POT, BOOK, BOTTOMLESS, SAKURETSU} <= {c.code for c in obs.hand}
        backrow_set = 0
        dust_set = pot_used = dust_used = chosen = checked = False
        threshold_checked = chain_checked = control_checked = False
        hand_before = deck_before = selected_code = None
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"pot_dustshoot_{play_pot}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and backrow_set < 4:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") in (
                                   BOOK, BOTTOMLESS, SAKURETSU)), None)
                if action is not None:
                    backrow_set += 1
            if obs.turn == 2 and obs.acting_player == 1 and not dust_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                dust_set = action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not threshold_checked:
                assert backrow_set == 4 and dust_set and len(obs.hand) == 3
                threshold_checked = True
            if threshold_checked and obs.turn == 3 and obs.acting_player == 1 \
                    and not play_pot:
                assert obs.opponent_hand_count == 3
                assert not any(a.parameters.get("code") == DUSTSHOOT for a in actions)
                control_checked = True
            if play_pot and threshold_checked and obs.turn == 3 \
                    and obs.acting_player == 0 and not pot_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == POT), action)
                pot_used = action is not None and action.kind == "activate"
            if pot_used and not chain_checked and obs.acting_player == 1 \
                    and obs.chain and obs.chain[0].card_code == POT:
                assert obs.opponent_hand_count == 2
                assert not any(a.parameters.get("code") == DUSTSHOOT for a in actions)
                chain_checked = True
            if pot_used and obs.acting_player == 1 and not dust_used:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                if option is not None:
                    assert chain_checked and not obs.chain
                    assert obs.opponent_hand_count == 4
                    hand_before = Counter(c.code for c in
                                          env.engine.probe.observation(0).hand)
                    deck_before = obs.deck_counts[0]
                    action = option
                    dust_used = True
            if dust_used and not chosen and actions[0].kind == "select_card":
                assert obs.acting_player == 1
                assert Counter(obs.known_opponent_hand_cards) == hand_before
                assert all("sequence" not in a.parameters for a in actions)
                action = actions[0]
                selected_code = action.parameters["code"]
                chosen = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if play_pot and chosen and not checked and DUSTSHOOT in {
                    c.code for c in obs.graveyards[1]}:
                assert obs.deck_counts[0] == deck_before + 1
                assert Counter(c.code for c in
                               env.engine.probe.observation(0).hand) == (
                    hand_before - Counter((selected_code,)))
                assert Counter(env.engine.probe.observation(
                    1).known_opponent_hand_cards) == (
                        hand_before - Counter((selected_code,)))
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
            if not play_pot and threshold_checked and obs.turn >= 4 and not checked:
                assert control_checked and not dust_used
                assert DUSTSHOOT not in {c.code for c in obs.graveyards[1]}
                checked = True
    pytest.fail("Pot / Dustshoot threshold line did not complete")
