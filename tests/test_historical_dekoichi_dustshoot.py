"""Dekoichi's draw opens Dustshoot only after its Flip Effect resolves."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

DEKOICHI = 87621407
DUSTSHOOT = 64697231
BOOK = 14087893
BOTTOMLESS = 504700052
SAKURETSU = 56120475


def _deck(path, cards):
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("flip", [False, True])
def test_dekoichi_draw_opens_dustshoot_hand_threshold(tmp_path, flip):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (DEKOICHI, DUSTSHOOT)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card scripts not installed")
    own_cards = [DEKOICHI, BOOK, BOOK, *VANILLA_DECK[3:]]
    own_cards = [BOTTOMLESS if code == 49003308 else
                 SAKURETSU if code == 49881766 else code
                 for code in own_cards]
    own = _deck(tmp_path / "dekoichi.ydk", own_cards)
    other = _deck(tmp_path / "dustshoot.ydk", (
        DUSTSHOOT, *VANILLA_DECK[1:]))

    with GoatEnvironment(own, other, seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {DEKOICHI, BOOK, BOTTOMLESS, SAKURETSU} <= {
            c.code for c in obs.hand}
        dekoichi_set = dust_set = flipped = dust_used = chosen = False
        backrow_set = 0
        threshold_checked = chain_gate_checked = checked = False
        no_flip_response_checked = False
        hand_before = deck_before = selected_code = None
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"dekoichi_dustshoot_{flip}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not dekoichi_set:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == DEKOICHI), None)
                    dekoichi_set = action is not None
                elif backrow_set < 3:
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
                assert dekoichi_set and backrow_set == 3 and dust_set
                assert len(obs.hand) == 3
                threshold_checked = True
            if not flip and threshold_checked and obs.turn == 3 \
                    and obs.acting_player == 1:
                assert obs.opponent_hand_count == 3
                assert not any(a.parameters.get("code") == DUSTSHOOT for a in actions)
                no_flip_response_checked = True
            if threshold_checked and obs.turn == 3 and obs.acting_player == 0 \
                    and not flipped and flip:
                action = next((a for a in actions if a.kind == "flip_summon"
                               and a.parameters.get("code") == DEKOICHI), action)
                flipped = action is not None and action.kind == "flip_summon"
            if flipped and not checked and obs.turn == 3 and obs.chain \
                    and obs.chain[0].card_code == DEKOICHI \
                    and obs.acting_player == 1:
                assert len(env.engine.probe.observation(0).hand) == 3
                assert obs.opponent_hand_count == 3
                assert not any(a.parameters.get("code") == DUSTSHOOT for a in actions)
                chain_gate_checked = True
            if flipped and obs.acting_player == 1 and not dust_used:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                if option is not None:
                    assert not obs.chain
                    assert obs.opponent_hand_count == 4
                    hand_before = Counter(c.code for c in
                                          env.engine.probe.observation(0).hand)
                    deck_before = obs.deck_counts[0]
                    action = option
                    dust_used = True
            if dust_used and not chosen and actions[0].kind == "select_card":
                assert obs.acting_player == 1
                assert obs.opponent_hand_count == 4
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
            if flip and chosen and not checked and DUSTSHOOT in {
                    c.code for c in obs.graveyards[1]}:
                assert DEKOICHI in {c.code for c in obs.field}
                assert chain_gate_checked
                assert obs.deck_counts[0] == deck_before + 1
                assert Counter(c.code for c in
                               env.engine.probe.observation(0).hand) == (
                    hand_before - Counter((selected_code,)))
                watcher = env.engine.probe.observation(1)
                assert Counter(watcher.known_opponent_hand_cards) == (
                    hand_before - Counter((selected_code,)))
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
            if not flip and threshold_checked and obs.turn >= 4 and not checked:
                assert no_flip_response_checked
                assert not dust_used
                assert DUSTSHOOT not in {c.code for c in obs.graveyards[1]}
                checked = True
    pytest.fail("Dekoichi / Dustshoot threshold line did not complete")
