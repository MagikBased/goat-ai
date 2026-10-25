"""Kycoo's Graveyard lock does not stop Warrior Lady's field banish."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

KYCOO = 88240808
WARRIOR_LADY = 7572887


def _deck(path, card):
    path.write_text("#main\n" + "\n".join(map(str, (
        card, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("banish", [False, True])
def test_warrior_lady_can_banish_battling_kycoo_from_field(tmp_path, banish):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (KYCOO, WARRIOR_LADY)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card scripts not installed")
    warrior = _deck(tmp_path / "warrior.ydk", WARRIOR_LADY)
    kycoo = _deck(tmp_path / "kycoo.ydk", KYCOO)

    with GoatEnvironment(warrior, kycoo, seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert WARRIOR_LADY in {card.code for card in obs.hand}
        assert KYCOO in {card.code for card in env.engine.probe.observation(1).hand}
        warrior_summoned = kycoo_summoned = attacked = targeted = choice = False
        checked = False
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"kycoo_warrior_{banish}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not warrior_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == WARRIOR_LADY), None)
                warrior_summoned = action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not kycoo_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == KYCOO), None)
                    kycoo_summoned = action is not None
                elif obs.phase == "main1":
                    action = next((a for a in actions if a.kind == "battle_phase"), action)
                elif obs.phase == "battle_start" and not attacked:
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == KYCOO), None)
                    attacked = action is not None
                elif attacked and not targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == WARRIOR_LADY and a.parameters.get("controller")
                                   == 0), None)
                    targeted = action is not None
            if targeted and obs.acting_player == 0 and not choice:
                option = next((a for a in actions if a.parameters.get("code")
                               == WARRIOR_LADY and a.kind in ("yes", "chain")), None)
                if option is not None:
                    assert obs.phase == "damage_step"
                    assert any(c.code == KYCOO and c.position == "faceup"
                               for c in obs.field)
                    action = option if banish else next(
                        a for a in actions if a.kind in ("no", "pass"))
                    choice = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "main2", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if choice and not checked and obs.turn == 2 and obs.phase == "main2":
                assert obs.life_points == (7700, 8000)
                assert (WARRIOR_LADY in {c.code for c in obs.banished[0]}) == banish
                assert (KYCOO in {c.code for c in obs.banished[1]}) == banish
                assert (WARRIOR_LADY in {c.code for c in obs.graveyards[0]}) != banish
                assert any(c.code == KYCOO for c in obs.field) != banish
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail("Kycoo / D.D. Warrior Lady battle did not resolve")
