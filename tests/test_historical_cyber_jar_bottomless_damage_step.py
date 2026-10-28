"""Bottomless cannot answer Cyber Jar monsters Summoned in the Damage Step."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

CYBER_JAR = 504700188
BOTTOMLESS = 504700052
ATTACKER = 7359741  # Mechanicalchaser, 1850 ATK


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
def test_bottomless_unavailable_after_attacked_cyber_jar(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    required = (f"goat/c{CYBER_JAR}.lua", f"goat/c{BOTTOMLESS}.lua")
    if any(not (root / "scripts" / script).is_file() for script in required):
        pytest.skip("GOAT card script not installed")
    own = tmp_path / "cyber_jar.ydk"
    other = tmp_path / "bottomless.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        CYBER_JAR, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    other.write_text("#main\n" + "\n".join(map(str, (
        *VANILLA_DECK[:3], BOTTOMLESS, *VANILLA_DECK[4:])))
        + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(other), seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert CYBER_JAR in {card.code for card in obs.hand}
        assert {BOTTOMLESS, ATTACKER} <= {card.code for card in
                                          env.engine.probe.observation(1).hand}
        jar_set = trap_set = attacker_summoned = attacked = False
        revealed = full_field_seen = checked = False
        agents = (RandomAgent(3), RandomAgent(4))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / "cyber_jar_bottomless_damage_step.json"
                write_trajectory(path, env.trajectory())
                replay = read_trajectory(path)
                assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(
                    replay.decisions)
                audit_trajectory_visibility(replay)
                return
            actions = env.legal_actions()
            action = None
            if not checked and obs.turn == 1 and obs.acting_player == 0 \
                    and not jar_set:
                action = next((a for a in actions if a.kind == "set_monster" and
                               a.parameters.get("code") == CYBER_JAR), None)
                jar_set = action is not None
            if not checked and obs.turn == 2 and obs.acting_player == 1:
                if not trap_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap" and
                                   a.parameters.get("code") == BOTTOMLESS), None)
                    trap_set = action is not None
                if trap_set and not attacker_summoned and action is None:
                    action = next((a for a in actions if a.kind == "normal_summon" and
                                   a.parameters.get("code") == ATTACKER), None)
                    attacker_summoned = action is not None
                if attacker_summoned and not attacked and action is None:
                    action = next((a for a in actions if a.kind in (
                        "battle_phase", "attack") and (a.kind != "attack" or
                        a.parameters.get("code") == ATTACKER)), None)
                    attacked |= action is not None and action.kind == "attack"
            if attacked and not checked and actions[0].kind == "select_card" \
                    and obs.phase == "battle_start":
                action = next((a for a in actions if a.parameters.get("controller") == 0
                               and a.parameters.get("location") == 4), None)
            if attacked and not checked and actions[0].kind == "select_position":
                action = next(a for a in actions if a.parameters.get("position") == 1)
            if attacked and not checked and len(obs.public_reveals) == 2:
                revealed = True
                assert obs.turn == 2 and obs.phase in ("damage_step", "battle_step")
                assert [(r.player, len(r.codes)) for r in obs.public_reveals] \
                    == [(1, 5), (0, 5)]
                assert not any(a.kind == "chain" and a.parameters.get("code")
                               == BOTTOMLESS for a in actions)
                monsters = [card for card in obs.field if card.zone == "monster"]
                if len(monsters) == 10:
                    full_field_seen = True
                    assert any(card.controller == 0 and card.position == "faceup"
                               and card.attack >= 1500 for card in monsters)
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if full_field_seen and not checked and obs.phase == "main2":
                assert revealed and trap_set and attacked
                assert len([card for card in obs.field if card.zone == "monster"]) == 10
                assert not obs.banished[0] and not obs.banished[1]
                trap_owner = env.engine.probe.observation(1)
                assert any(card.controller == 1 and card.code == BOTTOMLESS and
                           card.position == "facedown" for card in trap_owner.field)
                assert any(card.controller == 1 and card.code is None and
                           card.position == "facedown" for card in obs.field)
                assert BOTTOMLESS not in {card.code for card in obs.graveyards[1]}
                assert f"goat/c{CYBER_JAR}.lua" in env.engine.probe.loaded_script_sha256
                checked = True
    pytest.fail("Cyber Jar Damage Step fixture did not finish")
