"""Call chained to Breaker revives Sangan, then Breaker destroys Call."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

GRACEFUL = 79571449
CALL = 97077563
SANGAN = 504700178
BREAKER = 71413901
MYSTICAL_ELF = 15025844
MAD_DOG = 79182538


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_call_chained_to_breaker_revives_sangan_before_search(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (GRACEFUL, CALL, BREAKER)}
    scripts.add(f"goat/c{SANGAN}.lua")
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    caller = tmp_path / "caller.ydk"
    caller.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL, CALL, SANGAN, *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    breaker = tmp_path / "breaker.ydk"
    breaker.write_text("#main\n" + "\n".join(map(str, (
        BREAKER, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(caller), str(breaker), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, CALL, SANGAN, MAD_DOG} <= {card.code for card in obs.hand}
        assert BREAKER in {card.code for card in env.engine.probe.observation(1).hand}
        graceful = discarded = call_set = breaker_summoned = counter_placed = False
        breaker_used = call_targeted = call_chained = sangan_targeted = False
        searched = resolved = False
        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(5000):
            if env.is_terminal():
                assert resolved
                path = tmp_path / "breaker_call_sangan.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    graceful |= action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"] for c in
                                   a.parameters["cards"]} == {SANGAN, MAD_DOG}), None)
                    discarded |= action is not None
                if discarded and not call_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == CALL), None)
                    call_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and call_set:
                if not breaker_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == BREAKER), None)
                    breaker_summoned |= action is not None
                if breaker_summoned and any(card.code == BREAKER
                                            and card.counters == ((1, 1),)
                                            for card in obs.field):
                    counter_placed = True
                if counter_placed and not breaker_used:
                    action = next((a for a in actions if a.kind in ("activate", "chain")
                                   and a.parameters.get("code") == BREAKER), None)
                    breaker_used |= action is not None
                if breaker_used and not call_targeted \
                        and actions[0].kind == "select_card":
                    assert any(card.controller == 0 and card.zone == "spell_trap"
                               and card.position == "facedown" and card.code is None
                               for card in obs.field)
                    action = next((a for a in actions if a.parameters.get("controller") == 0
                                   and a.parameters.get("location") == 8
                                   and "code" not in a.parameters), None)
                    call_targeted |= action is not None
            if call_targeted and obs.acting_player == 0 and not call_chained:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == CALL), None)
                if option is not None:
                    assert tuple(link.card_code for link in obs.chain) == (BREAKER,)
                    action = option
                    call_chained = True
            if call_chained and not sangan_targeted and actions[0].kind == "select_card":
                assert tuple(link.card_code for link in obs.chain) == (BREAKER, CALL)
                action = next((a for a in actions if a.parameters.get("code") == SANGAN
                               and a.parameters.get("location") == 16), None)
                sangan_targeted |= action is not None
            if (sangan_targeted and not searched and actions[0].kind == "select_card"
                    and actions[0].parameters.get("location") == 1):
                assert tuple(link.card_code for link in obs.chain) == (SANGAN,)
                action = next((a for a in actions if a.parameters.get("code") == MYSTICAL_ELF
                               and a.parameters.get("location") == 1), None)
                assert action is not None and "sequence" not in action.parameters
                searched = True
            if action is None and not resolved:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if searched and not resolved and not obs.chain:
                caller_view = env.engine.probe.observation(0)
                breaker_view = env.engine.probe.observation(1)
                assert {CALL, SANGAN} <= {card.code for card in caller_view.graveyards[0]}
                assert not any(card.code == SANGAN for card in caller_view.field)
                breaker_card = next(card for card in caller_view.field
                                    if card.code == BREAKER)
                assert (breaker_card.attack, breaker_card.counters) == (1600, ())
                assert MYSTICAL_ELF in {card.code for card in caller_view.hand}
                assert breaker_view.known_opponent_hand_cards == (MYSTICAL_ELF,)
                assert [card.code for card in breaker_view.private_reveals[-1].cards] == [
                    MYSTICAL_ELF]
                assert caller_view.life_points == (8000, 8000)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                resolved = True
    pytest.fail("Breaker / Call / Sangan duel did not finish")
