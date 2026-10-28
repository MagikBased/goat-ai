"""Bottomless responds to a completed Call Summon, not a midchain Summon.

Historical ruling: https://www.goatformat.com/rulings1.html (Bottomless Trap Hole).
"""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

GRACEFUL = 79571449
CALL = 97077563
UPSTART = 70368879
BOTTOMLESS = 504700052  # GOAT variant
GEMINI_ELF = 69140098
MYSTICAL_ELF = 15025844
MAD_DOG = 79182538


def _decks(tmp_path):
    # Exchange the printed vanillas' positions to put 1900-ATK Gemini Elf in
    # the fixed seed's opening hand without changing either copy count.
    filler = [GEMINI_ELF if code == MYSTICAL_ELF else
              MYSTICAL_ELF if code == GEMINI_ELF else code
              for code in VANILLA_DECK[3:]]
    own = tmp_path / "caller.ydk"
    other = tmp_path / "bottomless.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL, CALL, UPSTART, *filler))) + "\n#extra\n!side\n")
    other.write_text("#main\n" + "\n".join(map(str, (
        BOTTOMLESS, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    return str(own), str(other)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
@pytest.mark.parametrize("call_at_chain_link_two", [False, True])
def test_call_summon_midchain_avoids_bottomless_response(tmp_path,
                                                            call_at_chain_link_two):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    required = (f"goat/c{BOTTOMLESS}.lua", *(f"official/c{code}.lua"
                for code in (GRACEFUL, CALL, UPSTART)))
    if any(not (root / "scripts" / relative).is_file() for relative in required):
        pytest.skip("required card script not installed")
    own, other = _decks(tmp_path)
    with GoatEnvironment(own, other, seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, CALL, UPSTART, GEMINI_ELF, MAD_DOG} <= {
            card.code for card in obs.hand}
        assert BOTTOMLESS in {card.code for card in
                              env.engine.probe.observation(1).hand}
        graceful = discarded = call_set = bottomless_set = started = targeted = False
        checked = bottomless_used = False
        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"call_bottomless_{call_at_chain_link_two}.json"
                write_trajectory(path, env.trajectory())
                replay = read_trajectory(path)
                assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(
                    replay.decisions)
                audit_trajectory_visibility(replay)
                loaded = env.engine.probe.loaded_script_sha256
                assert {f"official/c{code}.lua" for code in (GRACEFUL, CALL)} <= set(loaded)
                assert f"goat/c{BOTTOMLESS}.lua" in loaded
                return
            actions = env.legal_actions()
            action = None

            def choose(kind, code=None):
                return next((candidate for candidate in actions
                             if candidate.kind == kind and (code is None or
                                candidate.parameters.get("code") == code)), None)

            if not checked and obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = choose("activate", GRACEFUL)
                    graceful |= action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((candidate for candidate in actions
                                   if {card["code"] for card in
                                       candidate.parameters["cards"]} ==
                                   {GEMINI_ELF, MAD_DOG}), None)
                    discarded |= action is not None
                if discarded and not call_set and action is None:
                    action = choose("set_spell_trap", CALL)
                    call_set |= action is not None
            if not checked and obs.turn == 2 and obs.acting_player == 1 \
                    and not bottomless_set:
                action = choose("set_spell_trap", BOTTOMLESS)
                bottomless_set |= action is not None
            if not checked and obs.turn == 3 and obs.acting_player == 0:
                if not started:
                    code = UPSTART if call_at_chain_link_two else CALL
                    action = choose("activate", code)
                    started |= action is not None
                if started and call_at_chain_link_two and not targeted:
                    chained = choose("chain", CALL)
                    if chained is not None:
                        assert [(link.index, link.card_code) for link in obs.chain] == [
                            (1, UPSTART)]
                        action = chained
                if started and not targeted and actions[0].kind == "select_card":
                    action = choose("select_card", GEMINI_ELF)
                    targeted |= action is not None
                    if targeted:
                        assert [(link.index, link.card_code) for link in obs.chain] == (
                            [(1, UPSTART), (2, CALL)] if call_at_chain_link_two
                            else [(1, CALL)])
            if targeted and not checked and obs.acting_player == 1 and not obs.chain \
                    and any(card.code == GEMINI_ELF and card.zone == "monster"
                            for card in obs.field):
                response = choose("chain", BOTTOMLESS)
                if call_at_chain_link_two:
                    assert response is None
                    assert BOTTOMLESS not in {card.code for card in obs.graveyards[1]}
                    assert obs.life_points == (8000, 9000)  # Upstart resolved after Call.
                    checked = True
                else:
                    assert response is not None
                    action = response
                    bottomless_used = True
            if bottomless_used and not checked and GEMINI_ELF in {
                    card.code for card in obs.banished[0]}:
                assert GEMINI_ELF not in {card.code for card in obs.field}
                assert BOTTOMLESS in {card.code for card in obs.graveyards[1]}
                checked = True
            if action is None:
                action = (agents[obs.acting_player].select_action(obs, actions)
                          if checked else next((candidate for candidate in actions
                                                if candidate.kind in (
                                                    "place", "pass", "end_phase")),
                                               actions[0]))
            obs = env.step(action)
    pytest.fail("Call/Bottomless fixture did not reach a verified terminal duel")
