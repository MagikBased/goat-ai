"""A set Raigeki Break may answer MST before MST destroys that Trap."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

BREAK = 4178474
MST = 5318639


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_break", [False, True])
def test_break_chained_to_mst_spends_discard_and_destroys_target(tmp_path, chain_break):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (BREAK, MST)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card scripts not installed")
    breaker = tmp_path / "breaker.ydk"
    breaker.write_text("#main\n" + "\n".join(map(str, (
        *([BREAK] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    typhoon = tmp_path / "typhoon.ydk"
    typhoon.write_text("#main\n" + "\n".join(map(str, (
        MST, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(breaker), str(typhoon), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert BREAK in {card.code for card in obs.hand}
        assert MST in {card.code for card in env.engine.probe.observation(1).hand}
        break_set = summoned = mst_activated = mst_targeted = response_seen = False
        break_discarded = break_targeted = checked = False
        monster_code = None
        hand_before = None
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"break_mst_{chain_break}.json"
                write_trajectory(path, env.trajectory())
                replay = read_trajectory(path)
                assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) \
                    == len(replay.decisions)
                audit_trajectory_visibility(replay)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not break_set:
                action = next((candidate for candidate in actions
                               if candidate.kind == "set_spell_trap"
                               and candidate.parameters.get("code") == BREAK), None)
                break_set = action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not summoned:
                    action = next((candidate for candidate in actions
                                   if candidate.kind == "normal_summon"), None)
                    if action is not None:
                        monster_code = action.parameters["code"]
                        summoned = True
                if summoned and not mst_activated and action is None:
                    action = next((candidate for candidate in actions
                                   if candidate.kind == "activate"
                                   and candidate.parameters.get("code") == MST), None)
                    mst_activated = action is not None
                if mst_activated and not mst_targeted and action is None \
                        and actions[0].kind == "select_card":
                    assert all("code" not in candidate.parameters
                               for candidate in actions)
                    action = next((candidate for candidate in actions
                                   if candidate.parameters.get("controller") == 0
                                   and candidate.parameters.get("location") == 8), None)
                    mst_targeted = action is not None
            if mst_targeted and obs.acting_player == 0 and not response_seen:
                option = next((candidate for candidate in actions
                               if candidate.kind == "chain"
                               and candidate.parameters.get("code") == BREAK), None)
                if option is not None:
                    assert [link.card_code for link in obs.chain] == [MST]
                    hand_before = len(obs.hand)
                    action = option if chain_break else next(
                        candidate for candidate in actions if candidate.kind == "pass")
                    response_seen = True
            if chain_break and response_seen and not break_discarded \
                    and action is None and obs.acting_player == 0 \
                    and actions[0].kind == "select_card":
                action = next((candidate for candidate in actions
                               if candidate.parameters.get("location") == 2), None)
                break_discarded = action is not None
            if chain_break and break_discarded and not break_targeted \
                    and action is None and obs.acting_player == 0 \
                    and actions[0].kind == "select_card":
                assert [link.card_code for link in obs.chain] == [MST, BREAK]
                action = next((candidate for candidate in actions
                               if candidate.parameters.get("controller") == 1
                               and candidate.parameters.get("location") == 4
                               and candidate.parameters.get("code") == monster_code), None)
                break_targeted = action is not None
            if action is None and not checked:
                action = next((candidate for candidate in actions
                               if candidate.kind in ("place", "pass", "end_phase")),
                              actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if response_seen and not checked and not obs.chain \
                    and MST in {card.code for card in obs.graveyards[1]}:
                own = env.engine.probe.observation(0)
                opponent = env.engine.probe.observation(1)
                assert own.life_points == (8000, 8000)
                assert len(own.hand) == hand_before - int(chain_break)
                assert BREAK in {card.code for card in own.graveyards[0]}
                assert not any(card.code == BREAK for card in own.field)
                assert (monster_code in {card.code for card in opponent.graveyards[1]}) \
                    == chain_break
                assert any(card.controller == 1 and card.zone == "monster"
                           for card in own.field) != chain_break
                assert break_targeted == chain_break
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail("Raigeki Break / MST duel did not finish")
