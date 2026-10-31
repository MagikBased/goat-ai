"""Catastor's start-of-Damage-Step effect depends on the opponent's position."""

import hashlib
import os
import random
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.mr1_synchro_probe import (
    ALLY_OF_JUSTICE_CATASTOR,
    BOKOICHI,
    JUNK_SYNCHRON,
    Mr1SynchroProbeEngine,
)
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

MYSTICAL_ELF = 15025844  # LIGHT, 800 ATK
MECHANICALCHASER = 7359741  # DARK, 1850 ATK


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
@pytest.mark.parametrize(
    ("target_code", "face_down", "target_attacks", "expected_chain", "expected_lp"),
    ((MYSTICAL_ELF, False, True, True, (8000, 8000)),
     (MYSTICAL_ELF, True, False, False, (8000, 8000)),
     (MECHANICALCHASER, False, False, False, (8000, 7650))),
    ids=("faceup-light", "facedown-light", "faceup-dark"),
)
def test_catastor_damage_step_faceup_boundary(
        tmp_path, target_code, face_down, target_attacks, expected_chain, expected_lp):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    script = root / f"scripts/official/c{ALLY_OF_JUSTICE_CATASTOR}.lua"
    if not script.is_file():
        pytest.skip("Catastor script not installed")
    own_deck = tmp_path / "catastor.ydk"
    own_deck.write_text(
        Path("examples/decks/mr1_junk_warrior_probe.ydk").read_text().replace(
            "60800381\n!side", f"{ALLY_OF_JUSTICE_CATASTOR}\n!side"))
    permutation = list(range(40))
    random.Random(3 * 2 + 1).shuffle(permutation)
    other_main = list(VANILLA_DECK)
    first_target = other_main.index(target_code)
    opening_slot = permutation[34]
    other_main[first_target], other_main[opening_slot] = (
        other_main[opening_slot], other_main[first_target])
    other_deck = tmp_path / "target_opponent.ydk"
    other_deck.write_text("#main\n" + "\n".join(map(str, other_main))
                          + "\n#extra\n!side\n")

    with GoatEnvironment(str(own_deck), str(other_deck), seed=3,
                         engine=Mr1SynchroProbeEngine(root)) as env:
        view = env.reset()
        set_bokoichi = summon_target = summon_junk = summon_catastor = False
        target_attack = not target_attacks
        flip_bokoichi = not target_attacks
        catastor_attack = destroyed = False
        agents = (RandomAgent(3), RandomAgent(4))
        for _ in range(3000):
            if env.is_terminal():
                break
            actions = env.legal_actions()
            action = None
            if not destroyed:
                if view.turn == 1 and view.acting_player == 0 and not set_bokoichi:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == BOKOICHI), None)
                    set_bokoichi = action is not None
                if view.turn == 2 and view.acting_player == 1:
                    if not summon_target:
                        action = next((a for a in actions if a.kind == (
                            "set_monster" if face_down else "normal_summon")
                                       and a.parameters.get("code") == target_code), None)
                        summon_target = action is not None
                    elif not target_attack and view.phase.startswith("battle"):
                        action = next((a for a in actions if a.kind == "attack"), None)
                        target_attack = action is not None
                if view.turn == 3 and view.acting_player == 0:
                    if flip_bokoichi:
                        action = next((a for a in actions if a.kind == "flip_summon"
                                       and a.parameters.get("code") == BOKOICHI), None)
                        if action is not None:
                            flip_bokoichi = False
                    elif not summon_junk:
                        action = next((a for a in actions if a.kind == "normal_summon"
                                       and a.parameters.get("code") == JUNK_SYNCHRON), None)
                        summon_junk = action is not None
                    elif not summon_catastor:
                        action = next((a for a in actions if a.kind == "special_summon"
                                       and a.parameters.get("code") == ALLY_OF_JUSTICE_CATASTOR), None)
                        summon_catastor = action is not None
                    elif not catastor_attack and view.phase.startswith("battle"):
                        action = next((a for a in actions if a.kind == "attack"), None)
                        if action is not None:
                            assert any(card.code == (None if face_down else target_code)
                                       and card.controller == 1
                                       and card.position == ("facedown" if face_down else "faceup")
                                       for card in view.field)
                        catastor_attack = action is not None
                if action is None:
                    action = next((a for kind in (
                        "place", "select_position", "yes", "select_card",
                        "finish_selection", "battle_phase", "pass", "end_phase")
                        for a in actions if a.kind == kind), actions[0])
            else:
                action = agents[view.acting_player].select_action(view, actions)
            view = env.step(action)
            if catastor_attack and target_code in {
                    card.code for card in view.graveyards[1]} and not destroyed:
                assert view.life_points == expected_lp
                assert any(card.code == ALLY_OF_JUSTICE_CATASTOR
                           for card in view.field)
                destroyed = True
        assert env.is_terminal() and all((set_bokoichi, summon_target, target_attack,
                                          summon_junk, summon_catastor,
                                          catastor_attack, destroyed))
        assert env.engine.probe.loaded_script_sha256[
            f"official/c{ALLY_OF_JUSTICE_CATASTOR}.lua"] == hashlib.sha256(
                script.read_bytes()).hexdigest()
        trajectory = env.trajectory()
        catastor_chain = any(record.observation.turn == 3
                             and record.observation.phase == "damage_step"
                             and any(link.card_code == ALLY_OF_JUSTICE_CATASTOR
                                     for link in record.observation.chain)
                             and target_code not in {
                                 card.code for card in record.observation.graveyards[1]}
                             for record in trajectory.decisions)
        assert catastor_chain is expected_chain
        path = tmp_path / f"catastor_damage_step_{target_code}_{face_down}.json"
        write_trajectory(path, trajectory)
    replay = read_trajectory(path)
    assert verify_trajectory(replay, Mr1SynchroProbeEngine(root)) == len(replay.decisions)
    assert audit_trajectory_visibility(replay)["decisions"] == len(replay.decisions)
