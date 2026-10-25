"""Solemn can negate Snatch Steal before its Equip control effect applies."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SNATCH = 45986603
SOLEMN = 41420027


def _deck(path, cards):
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("negate", [False, True])
def test_solemn_negates_snatch_before_control_changes(tmp_path, negate):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{SNATCH}.lua", f"official/c{SOLEMN}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card scripts not installed")
    attacker = _deck(tmp_path / "snatch.ydk", (
        SNATCH, *VANILLA_DECK[1:]))
    defender = _deck(tmp_path / "solemn.ydk", (
        SOLEMN, *VANILLA_DECK[1:]))

    with GoatEnvironment(attacker, defender, seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert SNATCH in {c.code for c in obs.hand}
        defender_hand = env.engine.probe.observation(1).hand
        assert SOLEMN in {c.code for c in defender_hand}
        monster_code = next(c.code for c in defender_hand if c.code != SOLEMN)
        summoned = solemn_set = snatch_used = targeted = responded = checked = False
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"snatch_solemn_{negate}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1:
                if not summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == monster_code), None)
                    summoned = action is not None
                elif not solemn_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == SOLEMN), None)
                    solemn_set = action is not None
            if obs.turn == 3 and obs.acting_player == 0 and solemn_set \
                    and not snatch_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SNATCH), None)
                snatch_used = action is not None
            if snatch_used and not targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == monster_code
                               and a.parameters.get("controller") == 1), None)
                targeted = action is not None
            if targeted and not responded and obs.acting_player == 1:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SOLEMN), None)
                if option is not None:
                    assert [link.card_code for link in obs.chain] == [SNATCH]
                    assert next(c for c in obs.field if c.code == monster_code
                                and c.zone == "monster").controller == 1
                    action = option if negate else next(a for a in actions
                                                        if a.kind == "pass")
                    responded = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if responded and not checked and not obs.chain and \
                    SNATCH in {c.code for c in obs.graveyards[0]} | \
                    {c.code for c in obs.field}:
                soldier = next(c for c in obs.field if c.code == monster_code
                               and c.zone == "monster")
                assert obs.life_points == ((8000, 4000) if negate else (8000, 8000))
                assert soldier.controller == (1 if negate else 0)
                assert (SOLEMN in {c.code for c in obs.graveyards[1]}) == negate
                assert (SNATCH in {c.code for c in obs.graveyards[0]}) == negate
                if negate:
                    assert not any(c.code == SNATCH for c in obs.field)
                else:
                    snatch = next(c for c in obs.field if c.code == SNATCH)
                    assert snatch.equipped_to == (0, soldier.sequence)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail("Snatch / Solemn duel did not complete")
