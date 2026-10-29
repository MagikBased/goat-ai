"""An attacked Des Koala resolves its Flip Effect after battle calculation."""

import hashlib
import os
from dataclasses import replace
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

DES_KOALA = 69579761
GEMINI_ELF = 69140098
PINNED_KOALA_SCRIPT_SHA256 = "6bf1d8a387bad90479c7fad6e7dd61b03e4a7fc6927f10f3070009bdabb1d4a7"


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_attacked_des_koala_damages_for_attacker_hand_after_battle(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    script = root / f"scripts/official/c{DES_KOALA}.lua"
    assert hashlib.sha256(script.read_bytes()).hexdigest() == PINNED_KOALA_SCRIPT_SHA256
    attacker = tmp_path / "attacker.ydk"
    defender = tmp_path / "defender.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, VANILLA_DECK))
                        + "\n#extra\n!side\n")
    defender.write_text("#main\n" + "\n".join(map(str, (
        DES_KOALA, VANILLA_DECK[1], *VANILLA_DECK[2:])))
                        + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=98,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert GEMINI_ELF in {card.code for card in obs.hand}
        assert DES_KOALA in {
            card.code for card in env.engine.probe.observation(1).hand}
        summoned = set_koala = attacked = targeted = trigger_seen = resolved = False
        attacker_hand_count = None
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(5000):
            if env.is_terminal():
                assert resolved
                path = tmp_path / "des_koala_battle.json"
                write_trajectory(path, env.trajectory())
                loaded = read_trajectory(path)
                assert verify_trajectory(loaded, ExperimentalOcgcoreEngine(root)) == len(
                    loaded.decisions)
                assert audit_trajectory_visibility(loaded)["decisions"] == len(
                    loaded.decisions)
                legacy = replace(
                    loaded, schema_version=26,
                    decisions=tuple(replace(record, observation=replace(
                        record.observation, recent_attacks=()))
                        for record in loaded.decisions),
                    terminal_observation=replace(
                        loaded.terminal_observation, recent_attacks=()),
                )
                legacy_path = tmp_path / "des_koala_battle_v26.json"
                write_trajectory(legacy_path, legacy)
                assert verify_trajectory(
                    read_trajectory(legacy_path), ExperimentalOcgcoreEngine(root)) == len(
                        loaded.decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == GEMINI_ELF), None)
                summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not set_koala:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == DES_KOALA), None)
                set_koala |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and set_koala and not attacked:
                action = next((a for a in actions if a.kind in ("battle_phase", "attack")
                               and (a.kind != "attack" or a.parameters.get("code")
                                    == GEMINI_ELF)), None)
                if action is not None and action.kind == "attack":
                    attacked = True
                    attacker_hand_count = len(obs.hand)
            if attacked and not targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 4), None)
                targeted |= action is not None
            if action is None and not resolved:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "main2", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if targeted and not resolved and obs.recent_attacks:
                attack = obs.recent_attacks[-1]
                assert attack.turn == 3
                assert attack.attacker.controller == 0
                assert attack.attacker.zone == "monster"
                assert attack.target is not None
                assert attack.target.controller == 1
                assert attack.target.zone == "monster"
                if not trigger_seen:
                    opposing = env.engine.probe.observation(0)
                    hidden = next((card for card in opposing.field
                                   if card.controller == 1 and card.zone == "monster"), None)
                    if hidden is not None and hidden.position == "facedown":
                        assert hidden.code is None
            if attacked and any(link.card_code == DES_KOALA for link in obs.chain):
                visible_attacker_count = (len(obs.hand) if obs.viewer == 0
                                          else obs.opponent_hand_count)
                assert visible_attacker_count == attacker_hand_count
                assert obs.known_opponent_hand_cards == ()
                trigger_seen = True
            if attacked and not resolved and DES_KOALA in {
                    card.code for card in obs.graveyards[1]}:
                assert targeted and trigger_seen
                assert obs.life_points == (8000 - 400 * attacker_hand_count, 8000)
                assert obs.public_history.count("attack") == 1
                assert env.engine.probe.loaded_script_sha256[
                    f"official/c{DES_KOALA}.lua"] == PINNED_KOALA_SCRIPT_SHA256
                resolved = True
    pytest.fail("Des Koala was not attacked and resolved")
