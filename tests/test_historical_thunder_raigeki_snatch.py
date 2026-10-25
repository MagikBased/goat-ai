"""Thunder Dragon pays Raigeki Break to remove Snatch Steal from Dekoichi."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

THUNDER = 504700054
RAIGEKI_BREAK = 4178474
DEKOICHI = 87621407
SNATCH_STEAL = 45986603


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_thunder_cost_raigeki_break_restores_snatch_stolen_dekoichi(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{THUNDER}.lua", f"official/c{RAIGEKI_BREAK}.lua",
               f"official/c{DEKOICHI}.lua", f"official/c{SNATCH_STEAL}.lua"}
    for relative in scripts:
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    own = tmp_path / "turbo.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        *([THUNDER] * 3), *([RAIGEKI_BREAK] * 3), DEKOICHI,
        *VANILLA_DECK[7:]))) + "\n#extra\n!side\n")
    opponent = tmp_path / "snatch.ydk"
    opponent.write_text("#main\n" + "\n".join(map(str, (
        SNATCH_STEAL, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(opponent), seed=184,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {THUNDER, RAIGEKI_BREAK, DEKOICHI} <= {c.code for c in obs.hand}
        assert SNATCH_STEAL in {
            c.code for c in env.engine.probe.observation(1).hand}
        dragon_used = searched = dekoichi_summoned = break_set = False
        snatch_used = snatch_targeted = stolen = break_used = discarded = False
        break_targeted = checked = False
        agents = (RandomAgent(184), RandomAgent(185))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / "thunder_raigeki_snatch.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not dragon_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == THUNDER), None)
                    dragon_used |= action is not None
                elif not searched and any(a.kind == "select_cards" for a in actions):
                    action = next((a for a in actions if a.kind == "select_cards"
                                   and len(a.parameters.get("cards", ())) == 2), None)
                    searched |= action is not None
                elif searched and not dekoichi_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == DEKOICHI), None)
                    dekoichi_summoned |= action is not None
                elif dekoichi_summoned and not break_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == RAIGEKI_BREAK), None)
                    break_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and break_set and not snatch_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SNATCH_STEAL), None)
                snatch_used |= action is not None
            if snatch_used and not snatch_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == DEKOICHI
                               and a.parameters.get("controller") == 0), None)
                snatch_targeted |= action is not None
            if snatch_targeted and obs.turn == 2 and not stolen:
                stolen = any(c.code == DEKOICHI and c.controller == 1 for c in obs.field)
            if obs.turn == 3 and obs.acting_player == 0 and stolen and not break_used:
                assert env.engine.probe.observation(1) \
                    .known_opponent_hand_cards.count(THUNDER) == 1
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == RAIGEKI_BREAK), None)
                break_used |= action is not None
            if break_used and not discarded and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == THUNDER
                               and a.parameters.get("location") == 2), None)
                discarded |= action is not None
            if discarded and not break_targeted and action is None \
                    and actions[0].kind == "select_card":
                assert obs.chain and obs.chain[-1].card_code == RAIGEKI_BREAK
                assert env.engine.probe.observation(1) \
                    .known_opponent_hand_cards.count(THUNDER) == 0
                action = next((a for a in actions if a.parameters.get("code")
                               == SNATCH_STEAL and a.parameters.get("controller") == 1), None)
                break_targeted |= action is not None
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if break_targeted and not checked \
                    and SNATCH_STEAL in {c.code for c in obs.graveyards[1]} \
                    and RAIGEKI_BREAK in {c.code for c in obs.graveyards[0]}:
                assert sum(c.code == THUNDER for c in obs.graveyards[0]) == 2
                assert any(c.code == DEKOICHI and c.controller == 0 for c in obs.field)
                assert not any(c.code == DEKOICHI for c in obs.graveyards[0])
                assert env.engine.probe.observation(1) \
                    .known_opponent_hand_cards.count(THUNDER) == 0
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail("Thunder / Raigeki Break / Snatch duel did not finish")
