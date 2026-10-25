"""Swords flips a set monster even if MST destroys Swords in its activation chain."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SWORDS = 72302403
DEKOICHI = 87621407
MST = 5318639


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_mst", [False, True])
def test_swords_flips_dekoichi_even_when_mst_destroys_swords(tmp_path, chain_mst):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (SWORDS, DEKOICHI, MST)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("Swords / Dekoichi / MST scripts not installed")
    own = tmp_path / "swords.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        SWORDS, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    other = tmp_path / "dekoichi_mst.ydk"
    other.write_text("#main\n" + "\n".join(map(str, (
        *([DEKOICHI] * 3), MST, *VANILLA_DECK[4:])))
                     + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(other), seed=316,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert SWORDS in {c.code for c in obs.hand}
        assert {DEKOICHI, MST} <= {
            c.code for c in env.engine.probe.observation(1).hand}
        dekoichi_set = mst_set = swords_activated = response_seen = False
        mst_targeted = resolved = normal_summoned = battle_entered = False
        before_hand = before_deck = None
        for _ in range(100):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1:
                if not dekoichi_set:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == DEKOICHI), None)
                    dekoichi_set |= action is not None
                elif not mst_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == MST), None)
                    mst_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not swords_activated:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SWORDS), None)
                if action is not None:
                    other_view = env.engine.probe.observation(1)
                    before_hand = len(other_view.hand)
                    before_deck = obs.deck_counts[1]
                    assert any(c.zone == "monster" and c.controller == 1
                               and c.code is None and c.position == "facedown"
                               for c in obs.field)
                    swords_activated = True
            if swords_activated and obs.acting_player == 1 and not response_seen:
                mst = next((a for a in actions if a.kind == "chain"
                            and a.parameters.get("code") == MST), None)
                if mst is not None:
                    assert [link.card_code for link in obs.chain] == [SWORDS]
                    action = mst if chain_mst else next(a for a in actions
                                                         if a.kind == "pass")
                    response_seen = True
            if chain_mst and response_seen and not mst_targeted \
                    and obs.acting_player == 1 and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == SWORDS and a.parameters.get("controller") == 0), None)
                assert action is not None
                mst_targeted = True
            if swords_activated and not resolved and obs.turn == 3 \
                    and obs.acting_player == 0 and obs.chain == () \
                    and any(a.kind == "end_phase" for a in actions) \
                    and any(c.code == DEKOICHI and c.position == "faceup"
                            for c in obs.field):
                other_view = env.engine.probe.observation(1)
                assert response_seen
                assert other_view.deck_counts[1] == before_deck - 1
                assert len(other_view.hand) == before_hand + 1
                assert any(c.code == DEKOICHI and c.position == "faceup"
                           for c in obs.field)
                assert (SWORDS in {c.code for c in obs.field}) != chain_mst
                assert (SWORDS in {c.code for c in obs.graveyards[0]}) == chain_mst
                assert (MST in {c.code for c in obs.graveyards[1]}) == chain_mst
                required = (scripts if chain_mst else
                            scripts - {f"official/c{MST}.lua"})
                assert required <= env.engine.probe.loaded_script_sha256.keys()
                resolved = True
            if resolved and obs.turn == 4 and obs.acting_player == 1:
                if not normal_summoned and obs.phase == "main1":
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") != DEKOICHI), None)
                    normal_summoned |= action is not None
                elif normal_summoned and obs.phase == "main1":
                    action = next((a for a in actions if a.kind == "battle_phase"), action)
                    battle_entered |= action is not None and action.kind == "battle_phase"
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if battle_entered and obs.turn == 4 and obs.acting_player == 1 \
                    and obs.phase == "battle_start":
                attacks = [a for a in env.legal_actions() if a.kind == "attack"]
                assert bool(attacks) == chain_mst
                assert (SWORDS in {c.code for c in obs.field}) != chain_mst
                agents = (RandomAgent(316), RandomAgent(317))
                for _ in range(5000):
                    obs = env.step(agents[obs.acting_player].select_action(
                        obs, env.legal_actions()))
                    if env.is_terminal():
                        path = tmp_path / f"swords_mst_{chain_mst}.json"
                        write_trajectory(path, env.trajectory())
                        assert verify_trajectory(read_trajectory(path),
                                                 ExperimentalOcgcoreEngine(root)) == len(
                                                     env.trajectory().decisions)
                        return
                pytest.fail("Swords / MST duel did not finish")
    pytest.fail("Swords / MST / Dekoichi line did not reach Battle Phase")
