"""Torrential Tribute may chain after Exiled Force uses summon priority."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.mr1_synchro_probe import Mr1SynchroProbeEngine
from goat_ai.engine.ocgcore_probe import MR1_FLAGS
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

EXILED = 74131780
TORRENTIAL = 53582587


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_torrential", [False, True])
@pytest.mark.parametrize("engine_type", [ExperimentalOcgcoreEngine,
                                          Mr1SynchroProbeEngine])
def test_torrential_can_chain_to_exiled_force_priority_effect(tmp_path,
                                                               chain_torrential,
                                                               engine_type):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{EXILED}.lua", f"official/c{TORRENTIAL}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    attacker = tmp_path / "exiled.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        EXILED, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    defender = tmp_path / "torrential.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        TORRENTIAL, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=52,
                         engine=engine_type(root)) as env:
        obs = env.reset()
        if engine_type is Mr1SynchroProbeEngine:
            assert env.engine.probe.flags == MR1_FLAGS
        assert EXILED in {c.code for c in obs.hand}
        assert TORRENTIAL in {c.code for c in env.engine.probe.observation(1).hand}
        own_summoned = defender_summoned = trap_set = exiled_summoned = False
        effect_used = target_chosen = trap_offered = trap_chained = False
        own_code = defender_code = None
        for _ in range(100):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not own_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") != EXILED), None)
                if action is not None:
                    own_code = action.parameters["code"]
                    own_summoned = True
            if obs.turn == 2 and obs.acting_player == 1:
                if not defender_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        defender_code = action.parameters["code"]
                        defender_summoned = True
                if defender_summoned and not trap_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == TORRENTIAL), None)
                    trap_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and trap_set:
                if not exiled_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == EXILED), None)
                    exiled_summoned |= action is not None
                if exiled_summoned and not effect_used and action is None:
                    action = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == EXILED), None)
                    effect_used |= action is not None
                if effect_used and not target_chosen and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == defender_code and a.parameters.get("controller") == 1),
                                  None)
                    target_chosen |= action is not None
                    if target_chosen:
                        assert EXILED in {c.code for c in obs.graveyards[0]}
            if target_chosen and obs.acting_player == 1 and obs.chain \
                    and not trap_offered:
                assert obs.chain[0].card_code == EXILED
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == TORRENTIAL), None)
                assert option is not None
                trap_offered = True
                if chain_torrential:
                    action = option
                    trap_chained = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_card", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if trap_offered and not obs.chain and obs.turn == 3 \
                    and defender_code in {c.code for c in obs.graveyards[1]}:
                assert all((own_summoned, defender_summoned, trap_set,
                            exiled_summoned, effect_used, target_chosen))
                assert EXILED in {c.code for c in obs.graveyards[0]}
                assert obs.life_points == (8000, 8000)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                if chain_torrential:
                    assert trap_chained
                    assert own_code in {c.code for c in obs.graveyards[0]}
                    assert TORRENTIAL in {c.code for c in obs.graveyards[1]}
                    assert not any(c.zone == "monster" for c in obs.field)
                else:
                    assert not trap_chained
                    assert any(c.code == own_code and c.controller == 0
                               and c.zone == "monster" for c in obs.field)
                    defender_view = env.engine.probe.observation(1)
                    assert any(c.code == TORRENTIAL and c.controller == 1
                               and c.zone == "spell_trap" for c in defender_view.field)
                    assert any(c.code is None and c.controller == 1
                               and c.zone == "spell_trap" for c in obs.field)
                agents = (RandomAgent(52), RandomAgent(53))
                for _ in range(3000):
                    if env.is_terminal():
                        break
                    obs = env.step(agents[obs.acting_player].select_action(
                        obs, env.legal_actions()))
                else:
                    pytest.fail("Exiled / Torrential continuation exceeded 3000 decisions")
                trajectory = env.trajectory()
                if engine_type is Mr1SynchroProbeEngine:
                    assert trajectory.ruleset == "mr1-synchro-protocol"
                assert audit_trajectory_visibility(trajectory)["decisions"] == len(
                    trajectory.decisions)
                path = tmp_path / f"exiled_torrential_{chain_torrential}.json"
                write_trajectory(path, trajectory)
                assert verify_trajectory(read_trajectory(path),
                                         engine_type(root)) == len(
                                             trajectory.decisions)
                return
        pytest.fail(f"Exiled / Torrential line stalled: first={own_summoned} "
                    f"defender={defender_summoned}/{trap_set} "
                    f"exiled={exiled_summoned}/{effect_used}/{target_chosen} "
                    f"trap={trap_offered}/{trap_chained} turn={obs.turn} phase={obs.phase}")
