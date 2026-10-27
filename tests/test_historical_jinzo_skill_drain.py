"""The order of Jinzo and Skill Drain determines whether Traps remain live."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

GRACEFUL_CHARITY = 79571449
PREMATURE_BURIAL = 70828912
JINZO = 77585513
SKILL_DRAIN = 82732705
MIRROR_FORCE = 44095762
ROYAL_DECREE = 51452091
SECOND_DISCARD = 79182538


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("drain_before_jinzo,decree_third", [
    (False, False), (True, False), (True, True)])
def test_jinzo_skill_drain_order_controls_mirror_force(
        tmp_path, drain_before_jinzo, decree_third):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (
        GRACEFUL_CHARITY, PREMATURE_BURIAL, JINZO, SKILL_DRAIN, MIRROR_FORCE,
        *((ROYAL_DECREE,) if decree_third else ()))}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("Jinzo / Skill Drain scripts not installed")
    jinzo_deck = tmp_path / "jinzo.ydk"
    jinzo_deck.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL_CHARITY, PREMATURE_BURIAL, JINZO, *VANILLA_DECK[3:])))
        + "\n#extra\n!side\n")
    defender = tmp_path / "defender.ydk"
    defender_cards = [SKILL_DRAIN, *VANILLA_DECK[1:]]
    defender_cards[4] = MIRROR_FORCE
    if decree_third:
        defender_cards[18] = ROYAL_DECREE
    defender.write_text("#main\n" + "\n".join(map(str, defender_cards))
        + "\n#extra\n!side\n")

    with GoatEnvironment(str(jinzo_deck), str(defender), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL_CHARITY, PREMATURE_BURIAL, JINZO}.issubset(
            c.code for c in obs.hand)
        expected_hand = {SKILL_DRAIN, MIRROR_FORCE}
        if decree_third:
            expected_hand.add(ROYAL_DECREE)
        assert expected_hand.issubset(
            c.code for c in env.engine.probe.observation(1).hand)
        graceful = discarded = premature = jinzo_targeted = False
        drain_set = mirror_set = drain_chained = attacked = mirror_chained = False
        decree_set = decree_activated = False
        trap_window_checked = False
        for _ in range(150):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL_CHARITY), None)
                    graceful |= action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"]
                                   for c in a.parameters["cards"]} == {
                                       JINZO, SECOND_DISCARD}), None)
                    discarded = action is not None
            if (not drain_before_jinzo and obs.turn == 1
                    or drain_before_jinzo and obs.turn == 3) \
                    and obs.acting_player == 0 and discarded:
                if not premature:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == PREMATURE_BURIAL), action)
                    premature |= action is not None and action.kind == "activate" \
                        and action.parameters.get("code") == PREMATURE_BURIAL
                if premature and not jinzo_targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == JINZO
                                   and a.parameters.get("location") == 16), action)
                    jinzo_targeted = action is not None and action.kind == "select_card"
            if obs.turn == 2 and obs.acting_player == 1:
                if not drain_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == SKILL_DRAIN), action)
                    drain_set |= action is not None and action.kind == "set_spell_trap" \
                        and action.parameters.get("code") == SKILL_DRAIN
                elif not mirror_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == MIRROR_FORCE), action)
                    mirror_set |= action is not None and action.kind == "set_spell_trap" \
                        and action.parameters.get("code") == MIRROR_FORCE
                elif decree_third and not decree_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == ROYAL_DECREE), action)
                    decree_set |= action is not None and action.kind == "set_spell_trap" \
                        and action.parameters.get("code") == ROYAL_DECREE
            if (drain_before_jinzo and obs.turn == 3 and obs.acting_player == 1
                    and jinzo_targeted and not drain_chained
                    and [link.card_code for link in obs.chain] == [PREMATURE_BURIAL]):
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SKILL_DRAIN), None)
                assert action is not None
                drain_chained = True
            if (decree_third and drain_chained and not decree_activated
                    and obs.turn == 3 and obs.phase == "main1"
                    and obs.acting_player == 1 and not obs.chain
                    and any(c.code == JINZO and c.position == "faceup"
                            for c in obs.field)):
                option = next((a for a in actions if a.kind in ("activate", "chain")
                               and a.parameters.get("code") == ROYAL_DECREE), None)
                if option is not None:
                    action = option
                    decree_activated = True
            if obs.turn == 3 and obs.acting_player == 0 and jinzo_targeted:
                if obs.phase == "main1":
                    if not decree_third or decree_activated:
                        action = next((a for a in actions if a.kind == "battle_phase"), action)
                elif obs.phase == "battle_start" and not attacked:
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == JINZO), action)
                    attacked = action is not None and action.kind == "attack"
            if (attacked and obs.turn == 3 and obs.phase == "battle_step"
                    and obs.acting_player == 1 and not trap_window_checked):
                traps = {a.parameters.get("code") for a in actions if a.kind == "chain"}
                if decree_third:
                    assert decree_activated
                    assert MIRROR_FORCE not in traps
                    assert obs.life_points == (7200, 7000)
                elif drain_before_jinzo:
                    assert MIRROR_FORCE in traps
                    assert SKILL_DRAIN not in traps
                    action = next(a for a in actions if a.kind == "chain"
                                  and a.parameters.get("code") == MIRROR_FORCE)
                    mirror_chained = True
                    assert obs.life_points == (7200, 7000)
                else:
                    assert MIRROR_FORCE not in traps and SKILL_DRAIN not in traps
                    assert obs.life_points == (7200, 8000)
                trap_window_checked = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_card", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if (trap_window_checked and obs.turn == 3 and obs.acting_player == 0
                    and any(a.kind == "main2" for a in env.legal_actions())):
                assert drain_set and mirror_set and premature and jinzo_targeted
                if decree_third:
                    assert drain_chained and decree_set and decree_activated
                    assert not mirror_chained
                    assert obs.life_points == (7200, 4600)
                    assert any(c.code == JINZO and c.position == "faceup"
                               for c in obs.field)
                    defender_view = env.engine.probe.observation(1)
                    assert any(c.code == MIRROR_FORCE and c.position == "facedown"
                               for c in defender_view.field)
                    assert {SKILL_DRAIN, ROYAL_DECREE}.issubset(
                        c.code for c in obs.field if c.position == "faceup")
                elif drain_before_jinzo:
                    assert drain_chained and mirror_chained
                    assert obs.life_points == (7200, 7000)
                    assert JINZO in {c.code for c in obs.graveyards[0]}
                    assert MIRROR_FORCE in {c.code for c in obs.graveyards[1]}
                    assert any(c.code == SKILL_DRAIN and c.position == "faceup"
                               for c in obs.field)
                else:
                    assert not drain_chained and not mirror_chained
                    assert obs.life_points == (7200, 5600)
                    assert any(c.code == JINZO and c.position == "faceup"
                               for c in obs.field)
                    defender_view = env.engine.probe.observation(1)
                    assert any(c.code == SKILL_DRAIN and c.position == "facedown"
                               for c in defender_view.field)
                break
        else:
            pytest.fail("Jinzo / Skill Drain line did not reach battle result")
        agents = (RandomAgent(101), RandomAgent(102))
        for _ in range(3000):
            if env.is_terminal():
                break
            obs = env.step(agents[obs.acting_player].select_action(obs, env.legal_actions()))
        assert env.is_terminal()
        path = tmp_path / f"jinzo_skill_{drain_before_jinzo}_{decree_third}.json"
        write_trajectory(path, env.trajectory())
        recorded = read_trajectory(path)
        assert verify_trajectory(recorded, ExperimentalOcgcoreEngine(root)) == len(
            recorded.decisions)
        audit_trajectory_visibility(recorded)
