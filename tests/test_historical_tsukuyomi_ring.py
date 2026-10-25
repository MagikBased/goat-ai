"""Ring may destroy Tsukuyomi or its target before the set effect resolves."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

DEKOICHI = 87621407
TSUKUYOMI = 34853266
RING = 511000824


def _deck(path, cards):
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("ring_target", [TSUKUYOMI, DEKOICHI])
def test_ring_response_to_tsukuyomi_sets_target_only_if_it_survives(
    tmp_path, ring_target,
):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (DEKOICHI, TSUKUYOMI)}
    scripts.add(f"pre-errata/c{RING}.lua")
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card scripts not installed")
    own = _deck(tmp_path / "tsukuyomi.ydk", (
        *([DEKOICHI] * 3), *([TSUKUYOMI] * 3), *VANILLA_DECK[6:]))
    other = _deck(tmp_path / "ring.ydk", (
        RING, *VANILLA_DECK[1:]))

    with GoatEnvironment(own, other, seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {DEKOICHI, TSUKUYOMI} <= {c.code for c in obs.hand}
        assert RING in {c.code for c in env.engine.probe.observation(1).hand}
        dekoichi_summoned = ring_set = tsuk_summoned = tsuk_targeted = False
        ring_chained = ring_targeted = checked = False
        agents = (RandomAgent(15), RandomAgent(16))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"tsukuyomi_ring_{ring_target}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not dekoichi_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == DEKOICHI), None)
                dekoichi_summoned = action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not ring_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == RING), None)
                ring_set = action is not None
            if obs.turn == 3 and obs.acting_player == 0 and ring_set:
                if not tsuk_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == TSUKUYOMI), None)
                    tsuk_summoned = action is not None
                if tsuk_summoned and not tsuk_targeted \
                        and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == DEKOICHI and a.parameters.get("controller") == 0),
                                  None)
                    tsuk_targeted = action is not None
            if tsuk_targeted and obs.acting_player == 1 and not ring_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == RING), None)
                ring_chained = action is not None
                if ring_chained:
                    assert [link.card_code for link in obs.chain] == [TSUKUYOMI]
            if ring_chained and not ring_targeted \
                    and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == ring_target and a.parameters.get("controller") == 0),
                              None)
                ring_targeted = action is not None
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if ring_targeted and not checked and RING in {
                    c.code for c in obs.graveyards[1]} and not obs.chain:
                own_view = env.engine.probe.observation(0)
                other_view = env.engine.probe.observation(1)
                damage = 1100 if ring_target == TSUKUYOMI else 1400
                assert own_view.life_points == (8000 - damage, 8000 - damage)
                if ring_target == TSUKUYOMI:
                    assert TSUKUYOMI in {c.code for c in own_view.graveyards[0]}
                    assert any(c.code == DEKOICHI and c.position == "facedown"
                               for c in own_view.field)
                    assert any(c.controller == 0 and c.zone == "monster"
                               and c.code is None and c.position == "facedown"
                               for c in other_view.field)
                else:
                    assert DEKOICHI in {c.code for c in own_view.graveyards[0]}
                    assert any(c.code == TSUKUYOMI and c.position == "faceup"
                               for c in own_view.field)
                    assert not any(c.code == DEKOICHI for c in own_view.field)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail("Ring / Tsukuyomi response duel did not finish")
