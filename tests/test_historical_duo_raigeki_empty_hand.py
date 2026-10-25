"""Raigeki Break empties a one-card hand after Duo is activated."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

DUO = 44763025
BREAK = 4178474
SETTABLE = (14087893, 94192409, 56120475, 60082869,
            BREAK, 504700123)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_raigeki_break_last_hand_cost_leaves_duo_nothing_to_discard(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{DUO}.lua", f"official/c{BREAK}.lua"}
    if any(not (root / "scripts" / relative).is_file() for relative in scripts):
        pytest.skip("required card script not installed")
    attacker = tmp_path / "duo.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        DUO, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    defender = tmp_path / "break.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        *(code for code in SETTABLE for _ in range(3)),
        *VANILLA_DECK[18:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=43,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert DUO in {c.code for c in obs.hand}
        set_monster = set_break = duo_used = break_chained = discarded = False
        target_chosen = checked = False
        set_other = 0
        last_card = target_code = None
        agents = (RandomAgent(43), RandomAgent(44))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / "duo_break_empty_hand.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1:
                if not set_monster:
                    action = next((a for a in actions if a.kind == "set_monster"), None)
                    set_monster |= action is not None
                elif not set_break:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BREAK), None)
                    set_break |= action is not None
                elif set_other < 3:
                    action = next((a for a in actions if a.kind == "set_spell_trap"), None)
                    set_other += action is not None
            if obs.turn == 3 and obs.acting_player == 0 and set_other == 3 \
                    and not duo_used:
                assert obs.opponent_hand_count == 1
                assert obs.known_opponent_hand_cards == ()
                last_card = env.engine.probe.observation(1).hand[0].code
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == DUO), None)
                duo_used |= action is not None
            if duo_used and obs.acting_player == 1 and not break_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BREAK), None)
                if action is not None:
                    assert obs.life_points == (7000, 8000)
                    assert [link.card_code for link in obs.chain] == [DUO]
                    break_chained = True
            if break_chained and not discarded and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == last_card
                               and a.parameters.get("location") == 2), None)
                discarded |= action is not None
            if discarded and not target_chosen and action is None \
                    and actions[0].kind == "select_card":
                assert env.engine.probe.observation(1).hand == ()
                assert env.engine.probe.observation(0).opponent_hand_count == 0
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 8
                               and a.parameters.get("code") != BREAK), None)
                target_chosen |= action is not None
                if action is not None:
                    target_code = action.parameters.get("code")
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if target_chosen and not checked and DUO in {c.code for c in obs.graveyards[0]} \
                    and BREAK in {c.code for c in obs.graveyards[1]} and not obs.chain:
                assert obs.life_points == (7000, 8000)
                assert obs.opponent_hand_count == 0
                assert len(obs.graveyards[1]) == 3
                assert {c.code for c in obs.graveyards[1]} == {
                    last_card, BREAK, target_code}
                assert env.engine.probe.observation(1).hand == ()
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail("Duo / Raigeki Break empty-hand chain did not finish")
