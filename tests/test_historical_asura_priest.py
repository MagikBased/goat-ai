"""Asura Priest's four Sheep Token attacks and Spirit return."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import verify_trajectory

ASURA_PRIEST = 2134346
SCAPEGOAT = 504700123
SHEEP_TOKENS = {73915052, 73915053, 73915054, 73915055}
SPIRIT_REAPER = 504700038


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_asura_priest_attacks_four_sheep_then_returns_to_hand(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{ASURA_PRIEST}.lua").is_file():
        pytest.skip("Asura Priest script not installed")
    if not (root / f"scripts/goat/c{SCAPEGOAT}.lua").is_file():
        pytest.skip("GOAT Scapegoat script not installed")
    own_deck = tmp_path / "asura.ydk"
    own_deck.write_text("#main\n" + "\n".join(map(str, (
        *([ASURA_PRIEST] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    other_deck = tmp_path / "scapegoat.ydk"
    other_deck.write_text("#main\n" + "\n".join(map(str, (
        *([SCAPEGOAT] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own_deck), str(other_deck), seed=11,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        goat_used = asura_summoned = False
        declared_attacks = []
        targeted_tokens = set()
        empty_field_checked = False
        for _ in range(120):
            actions = env.legal_actions()
            action = None
            if observation.turn == 2 and observation.acting_player == 1 \
                    and not goat_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                goat_used = action is not None
            if observation.turn == 3 and observation.acting_player == 0 \
                    and goat_used:
                if not asura_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == ASURA_PRIEST), None)
                    if action is not None:
                        assert {c.code for c in observation.field
                                if c.code in SHEEP_TOKENS} == SHEEP_TOKENS
                        asura_summoned = True
                if asura_summoned and action is None:
                    action = next((a for a in actions if a.kind == "battle_phase"), None)
                if asura_summoned and action is None:
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == ASURA_PRIEST), None)
                    if action is not None:
                        remaining = {c.code for c in observation.field
                                     if c.code in SHEEP_TOKENS}
                        assert len(remaining) == 4 - len(declared_attacks)
                        declared_attacks.append(action)
            if asura_summoned and actions[0].kind == "select_card":
                remaining = {a.parameters.get("code") for a in actions
                             if a.kind == "select_card"}
                assert remaining == SHEEP_TOKENS - targeted_tokens
                action = next(a for a in actions if a.kind == "select_card")
                targeted_tokens.add(action.parameters["code"])
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if len(targeted_tokens) == 4 and observation.turn == 3 \
                    and observation.acting_player == 0 and observation.phase == "battle_step" \
                    and any(a.kind == "main2" for a in env.legal_actions()):
                assert len(declared_attacks) == 4
                assert targeted_tokens == SHEEP_TOKENS
                assert not any(c.code in SHEEP_TOKENS for c in observation.field)
                assert not any(a.kind == "attack" for a in env.legal_actions())
                assert observation.life_points == (8000, 8000)
                assert not any(c.code in SHEEP_TOKENS for zone in (
                    *observation.graveyards, *observation.banished) for c in zone)
                empty_field_checked = True
            if empty_field_checked and observation.turn == 3 \
                    and ASURA_PRIEST in {c.code for c in observation.hand}:
                assert not any(c.code == ASURA_PRIEST for c in observation.field)
                assert "official/c2134346.lua" in env.engine.probe.loaded_script_sha256
                assert "goat/c504700123.lua" in env.engine.probe.loaded_script_sha256
                return
    pytest.fail("Asura Priest did not clear all four Sheep Tokens and return")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_asura_cannot_attack_new_sheep_after_completed_direct_attack(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{ASURA_PRIEST}.lua").is_file() or not (
        root / f"scripts/goat/c{SCAPEGOAT}.lua"
    ).is_file():
        pytest.skip("Asura Priest or GOAT Scapegoat script not installed")
    own_deck = tmp_path / "asura.ydk"
    own_deck.write_text("#main\n" + "\n".join(map(str, (
        *([ASURA_PRIEST] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    other_deck = tmp_path / "scapegoat.ydk"
    other_deck.write_text("#main\n" + "\n".join(map(str, (
        *([SCAPEGOAT] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own_deck), str(other_deck), seed=11,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        goat_set = asura_summoned = battle = attacked = damage_dealt = False
        goat_chained = False
        for _ in range(100):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1 and not goat_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                goat_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0:
                if not asura_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == ASURA_PRIEST), None)
                    asura_summoned |= action is not None
                if asura_summoned and not battle and action is None:
                    action = next((a for a in actions if a.kind == "battle_phase"), None)
                    battle |= action is not None
                if battle and not attacked and obs.phase == "battle_start" \
                        and action is None:
                    assert not any(c.controller == 1 and c.zone == "monster"
                                   for c in obs.field)
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == ASURA_PRIEST), None)
                    attacked |= action is not None
            if attacked and obs.life_points[1] == 6300:
                damage_dealt = True
            if damage_dealt and not goat_chained and obs.acting_player == 1:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                goat_chained |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            tokens = [c for c in obs.field if c.code in SHEEP_TOKENS]
            if goat_chained and len(tokens) == 4 and obs.acting_player == 0 \
                    and obs.phase == "battle_step" and any(
                        a.kind == "main2" for a in env.legal_actions()):
                assert damage_dealt and attacked and goat_set
                assert {c.code for c in tokens} == SHEEP_TOKENS
                assert obs.life_points == (8000, 6300)
                assert not any(a.kind == "attack" and a.parameters.get("code")
                               == ASURA_PRIEST for a in env.legal_actions())
                assert f"official/c{ASURA_PRIEST}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                assert f"goat/c{SCAPEGOAT}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Asura attacked again after a completed direct attack")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
def test_asura_cannot_attack_surviving_reaper_twice_but_can_attack_sheep(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"scripts/official/c{ASURA_PRIEST}.lua",
                     f"scripts/goat/c{SPIRIT_REAPER}.lua",
                     f"scripts/goat/c{SCAPEGOAT}.lua"):
        if not (root / relative).is_file():
            pytest.skip(f"{relative} not installed")
    own_deck = tmp_path / "asura.ydk"
    own_deck.write_text("#main\n" + "\n".join(map(str, (
        *([ASURA_PRIEST] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    other_deck = tmp_path / "reaper_goat.ydk"
    other_deck.write_text("#main\n" + "\n".join(map(str, (
        *([SPIRIT_REAPER] * 3), *([SCAPEGOAT] * 3),
        *VANILLA_DECK[6:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own_deck), str(other_deck), seed=11,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        reaper_set = goat_used = asura_summoned = battle = False
        reaper_targeted = reaper_survived = sheep_targeted = False
        for _ in range(160):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1:
                if not reaper_set:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == SPIRIT_REAPER), None)
                    reaper_set |= action is not None
                if reaper_set and not goat_used and action is None:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == SCAPEGOAT), None)
                    goat_used |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and goat_used:
                if not asura_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == ASURA_PRIEST), None)
                    asura_summoned |= action is not None
                if asura_summoned and not battle and action is None:
                    action = next((a for a in actions if a.kind == "battle_phase"), None)
                    battle |= action is not None
                if battle and not sheep_targeted and action is None:
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == ASURA_PRIEST), None)
            if battle and actions[0].kind == "select_card":
                targets = [a for a in actions if a.kind == "select_card"]
                if not reaper_targeted:
                    action = next((a for a in targets
                                   if a.parameters.get("controller") == 1
                                   and a.parameters.get("code") in (None, SPIRIT_REAPER)
                                   and a.parameters.get("sequence") == 0), None)
                    reaper_targeted = action is not None
                else:
                    assert all(a.parameters.get("code") != SPIRIT_REAPER
                               and a.parameters.get("sequence") != 0
                               for a in targets)
                    action = next((a for a in targets
                                   if a.parameters.get("code") in SHEEP_TOKENS), None)
                    sheep_targeted = action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if reaper_targeted and not reaper_survived and obs.turn == 3:
                reaper = next((c for c in obs.field if c.code == SPIRIT_REAPER), None)
                if reaper is not None and reaper.position == "faceup":
                    reaper_survived = True
            if sheep_targeted:
                break
        assert reaper_set and goat_used and asura_summoned and battle
        assert reaper_targeted and reaper_survived and sheep_targeted
        assert obs.life_points == (8000, 8000)
        assert any(c.code == SPIRIT_REAPER for c in obs.field)
        assert f"official/c{ASURA_PRIEST}.lua" in env.engine.probe.loaded_script_sha256
        assert f"goat/c{SPIRIT_REAPER}.lua" in env.engine.probe.loaded_script_sha256
        for _ in range(3000):
            if env.is_terminal():
                break
            actions = env.legal_actions()
            obs = env.step(next((a for a in actions if a.kind in (
                "place", "pass", "end_phase")), actions[0]))
        assert env.is_terminal()
        trajectory = env.trajectory()
        assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) == len(
            trajectory.decisions)
        assert audit_trajectory_visibility(trajectory)["decisions"] == len(
            trajectory.decisions)
