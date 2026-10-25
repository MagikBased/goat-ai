"""Mirror Force can answer a newly declared attack after a GOAT replay."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SCAPEGOAT = 504700123
MIRROR_FORCE = 44095762
GEMINI_ELF = 69140098
TOKENS = {73915052, 73915053, 73915054, 73915055}


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_mirror_force_can_answer_new_attack_after_scapegoat_replay(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{SCAPEGOAT}.lua", f"official/c{MIRROR_FORCE}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    attacker = tmp_path / "attacker.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, VANILLA_DECK))
                        + "\n#extra\n!side\n")
    defender = tmp_path / "defender.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        SCAPEGOAT, SCAPEGOAT, MIRROR_FORCE, *VANILLA_DECK[3:])))
        + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=7,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert GEMINI_ELF in {c.code for c in obs.hand}
        assert {SCAPEGOAT, MIRROR_FORCE} <= {
            c.code for c in env.engine.probe.observation(1).hand}
        summoned = goat_set = mirror_set = first_attack = goat_chained = False
        replay_attack = mirror_chained = checked = False
        agents = (RandomAgent(7), RandomAgent(8))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / "scapegoat_mirror_replay.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == GEMINI_ELF), None)
                summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not goat_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == SCAPEGOAT), None)
                    goat_set |= action is not None
                elif not mirror_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == MIRROR_FORCE), None)
                    mirror_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and mirror_set \
                    and not first_attack:
                action = next((a for a in actions if a.kind in ("battle_phase", "attack")
                               and (a.kind != "attack" or a.parameters.get("code")
                                    == GEMINI_ELF)), action)
                first_attack |= action is not None and action.kind == "attack"
                if first_attack:
                    assert not any(c.zone == "monster" and c.controller == 1
                                   for c in obs.field)
            if first_attack and obs.acting_player == 1 and not goat_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SCAPEGOAT), action)
                goat_chained |= action is not None and action.kind == "chain"
            token_count = sum(c.code in TOKENS for c in obs.field)
            if goat_chained and token_count == 4 and not replay_attack:
                action = next((a for a in actions if a.kind == "attack"
                               and a.parameters.get("code") == GEMINI_ELF), action)
                replay_attack |= action is not None and action.kind == "attack"
            if replay_attack and obs.acting_player == 1 and not mirror_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == MIRROR_FORCE), action)
                mirror_chained |= action is not None and action.kind == "chain"
                if mirror_chained:
                    assert obs.phase == "battle_step"
                    assert obs.public_history.count("attack") == 2
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "main2", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if mirror_chained and not checked and MIRROR_FORCE in {
                    c.code for c in obs.graveyards[1]}:
                assert GEMINI_ELF in {c.code for c in obs.graveyards[0]}
                assert token_count == 4
                assert sum(c.code in TOKENS for c in obs.field) == 4
                assert obs.life_points == (8000, 8000)
                assert {f"goat/c{SCAPEGOAT}.lua",
                        f"official/c{MIRROR_FORCE}.lua"} <= (
                    env.engine.probe.loaded_script_sha256.keys())
                checked = True
    pytest.fail("Scapegoat replay / Mirror Force line did not finish")
