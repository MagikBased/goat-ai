"""Mirror Force can answer BLS's second, consecutive attack declaration."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

BLS = 504700118
GRACEFUL = 79571449
MIRROR = 44095762
LIGHT = 15025844
DARK = 7359741


def _deck(path, cards):
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("use_mirror", [False, True])
def test_mirror_force_on_bls_second_attack(tmp_path, use_mirror):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{BLS}.lua", f"official/c{GRACEFUL}.lua",
               f"official/c{MIRROR}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card scripts not installed")
    lights = (LIGHT, 62651957)
    darks = (49881766, DARK)
    filler = [code for code in VANILLA_DECK if code not in (*lights, *darks)]
    attacker = _deck(tmp_path / "bls.ydk", (
        GRACEFUL, BLS, *(code for code in lights for _ in range(3)),
        *(code for code in darks for _ in range(3)), *filler[:26]))
    defender = _deck(tmp_path / "mirror.ydk", (
        MIRROR, *VANILLA_DECK[1:]))

    with GoatEnvironment(attacker, defender, seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, BLS, LIGHT, DARK} <= {c.code for c in obs.hand}
        assert MIRROR in {c.code for c in env.engine.probe.observation(1).hand}
        graceful = discarded = summoned = defender_summoned = mirror_set = False
        first_attack = first_targeted = first_response_seen = False
        second_enabled = second_attack = False
        second_response = checked = False
        costs = set()
        defender_code = defender_attack = None
        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"bls_second_mirror_{use_mirror}.json"
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
                    graceful = action is not None
                elif not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"] for c in
                                   a.parameters["cards"]} == {LIGHT, DARK}), None)
                    discarded = action is not None
                elif discarded and not summoned:
                    action = next((a for a in actions if a.kind == "special_summon"
                                   and a.parameters.get("code") == BLS), None)
                    summoned = action is not None
                elif summoned and len(costs) < 2 \
                        and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   in ({LIGHT, DARK} - costs)), None)
                    if action is not None:
                        costs.add(action.parameters["code"])
            if obs.turn == 2 and obs.acting_player == 1:
                if not defender_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") != MIRROR), None)
                    defender_summoned = action is not None
                    if action is not None:
                        defender_code = action.parameters["code"]
                elif not mirror_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == MIRROR), None)
                    mirror_set = action is not None
            if obs.turn == 3 and obs.acting_player == 0 and mirror_set:
                if defender_attack is None:
                    defender_attack = next(c.attack for c in obs.field
                                           if c.code == defender_code
                                           and c.controller == 1)
                if obs.phase == "main1":
                    action = next((a for a in actions if a.kind == "battle_phase"), action)
                elif obs.phase in ("battle_start", "battle_step"):
                    if not first_attack or second_enabled and not second_attack:
                        action = next((a for a in actions if a.kind == "attack"
                                       and a.parameters.get("code") == BLS), action)
                        if action is not None and action.kind == "attack":
                            if first_attack:
                                second_attack = True
                            else:
                                first_attack = True
                if first_attack and not first_targeted \
                        and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == defender_code and a.parameters.get("controller")
                                   == 1), action)
                    first_targeted = action is not None and action.kind == "select_card"
                if first_targeted and not second_enabled:
                    option = next((a for a in actions if a.kind == "yes"
                                   and a.parameters.get("code") == BLS), None)
                    if option is not None:
                        assert obs.phase == "damage_step"
                        assert obs.life_points == (8000, 8000 - (3000 - defender_attack))
                        action = option
                        second_enabled = True
            if first_attack and not second_attack and obs.acting_player == 1 \
                    and not first_response_seen:
                mirror = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == MIRROR), None)
                if mirror is not None:
                    action = next(a for a in actions if a.kind == "pass")
                    first_response_seen = True
            if second_attack and obs.acting_player == 1 and not second_response:
                mirror = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == MIRROR), None)
                if mirror is not None:
                    assert first_response_seen and second_enabled
                    assert obs.phase == "battle_step"
                    assert obs.life_points == (8000, 8000 - (3000 - defender_attack))
                    action = mirror if use_mirror else next(a for a in actions
                                                           if a.kind == "pass")
                    second_response = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "select_position", "pass", "end_phase")),
                              actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if second_response and not checked and obs.turn == 3 \
                    and obs.phase == "main2":
                assert set(costs) == {LIGHT, DARK}
                assert obs.public_history.count("attack") == 2
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                if use_mirror:
                    assert MIRROR in {c.code for c in obs.graveyards[1]}
                    assert BLS in {c.code for c in obs.graveyards[0]}
                    assert obs.life_points == (8000, 8000 - (3000 - defender_attack))
                else:
                    assert MIRROR not in {c.code for c in obs.graveyards[1]}
                    assert BLS in {c.code for c in obs.field}
                    assert obs.life_points == (8000, 5000 - (3000 - defender_attack))
                checked = True
    pytest.fail("BLS second attack / Mirror Force line did not complete")
