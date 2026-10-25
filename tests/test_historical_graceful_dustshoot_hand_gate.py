"""Setting cards before Graceful keeps Trap Dustshoot below four-hand gate."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

GRACEFUL = 79571449
MIRROR = 44095762
BOOK = 14087893
COMPULSORY = 94192409
SAKURETSU = 56120475
DUSTSHOOT = 64697231


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_setting_before_graceful_keeps_dustshoot_inactive(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (GRACEFUL, DUSTSHOOT):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    draw_deck = tmp_path / "graceful.ydk"
    draw_deck.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL, MIRROR,
        *([BOOK] * 3), *([COMPULSORY] * 3), *([SAKURETSU] * 3),
        *VANILLA_DECK[11:]))) + "\n#extra\n!side\n")
    trap_deck = tmp_path / "dustshoot.ydk"
    trap_deck.write_text("#main\n" + "\n".join(map(str, (
        *([DUSTSHOOT] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(draw_deck), str(trap_deck), seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, MIRROR, BOOK, COMPULSORY} <= {c.code for c in obs.hand}
        assert DUSTSHOOT in {c.code for c in env.engine.probe.observation(1).hand}
        initial_sets = set()
        dust_set = monster_set = graceful_used = discarded = checked = False
        offered_at_four = post_gate_checked = False
        deck_before = None
        agents = (RandomAgent(18), RandomAgent(19))
        for _ in range(5000):
            if env.is_terminal():
                assert checked and post_gate_checked
                path = tmp_path / "graceful_dustshoot_gate.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 3 and obs.acting_player == 1 and not monster_set \
                    and obs.opponent_hand_count == 4:
                offered_at_four |= any(a.kind in ("activate", "chain")
                                       and a.parameters.get("code") == DUSTSHOOT
                                       for a in actions)
            if discarded and obs.turn == 3 and obs.acting_player == 1 \
                    and obs.opponent_hand_count == 3 and not post_gate_checked:
                assert not any(a.kind in ("activate", "chain")
                               and a.parameters.get("code") == DUSTSHOOT
                               for a in actions)
                post_gate_checked = True
            if obs.turn == 1 and obs.acting_player == 0 and len(initial_sets) < 3:
                needed = ({MIRROR, BOOK, COMPULSORY} - initial_sets)
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") in needed), None)
                if action is not None:
                    initial_sets.add(action.parameters["code"])
            if obs.turn == 2 and obs.acting_player == 1 and not dust_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                dust_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and dust_set:
                if not monster_set:
                    assert len(obs.hand) == 4
                    action = next((a for a in actions if a.kind == "set_monster"), None)
                    monster_set |= action is not None
                elif not graceful_used and action is None \
                        and any(a.kind == "end_phase" for a in actions):
                    assert offered_at_four
                    assert len(obs.hand) == 3
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    if action is not None:
                        deck_before = obs.deck_counts[0]
                        graceful_used = True
            if graceful_used and obs.acting_player == 1 and not discarded:
                assert obs.opponent_hand_count == 2
                assert [link.card_code for link in obs.chain] == [GRACEFUL]
                assert not any(a.kind == "chain" and a.parameters.get("code")
                               == DUSTSHOOT for a in actions)
            if graceful_used and not discarded \
                    and any(a.kind == "select_cards" for a in actions):
                assert obs.deck_counts[0] == deck_before - 3
                action = next(a for a in actions if a.kind == "select_cards")
                discarded = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if discarded and not checked and GRACEFUL in {
                    c.code for c in obs.graveyards[0]} and not obs.chain:
                assert len(env.engine.probe.observation(0).hand) == 3
                assert obs.deck_counts[0] == deck_before - 3
                assert DUSTSHOOT not in {c.code for c in obs.graveyards[1]}
                assert env.engine.probe.observation(1).opponent_hand_count == 3
                assert {f"official/c{GRACEFUL}.lua",
                        f"official/c{DUSTSHOOT}.lua"} <= (
                    env.engine.probe.loaded_script_sha256.keys())
                checked = True
    pytest.fail("Graceful / Dustshoot hand-gate duel did not finish")
