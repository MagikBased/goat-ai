"""Archived Scapegoat/Royal Oppression activation-timing regression."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SCAPEGOAT = 504700123
ROYAL_OPPRESSION = 93016201
SHEEP_CODES = {73915052, 73915053, 73915054, 73915055}


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("preactivate_oppression", [False, True])
def test_oppression_must_be_face_up_before_scapegoat_chain(tmp_path, preactivate_oppression):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{SCAPEGOAT}.lua", f"official/c{ROYAL_OPPRESSION}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    goat_deck = tmp_path / "goat.ydk"
    oppression_deck = tmp_path / "oppression.ydk"
    goat_deck.write_text("#main\n" + "\n".join(map(str, (
        SCAPEGOAT, SCAPEGOAT, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    oppression_deck.write_text("#main\n" + "\n".join(map(str, (
        ROYAL_OPPRESSION, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(goat_deck), str(oppression_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        goat_set = oppression_set = oppression_active = goat_used = False
        oppression_effect_used = checked = False
        for _ in range(1200):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"oppression_{preactivate_oppression}.json"
                write_trajectory(path, env.trajectory())
                trajectory = read_trajectory(path)
                assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) == len(
                    trajectory.decisions)
                audit_trajectory_visibility(trajectory)
                return
            actions = env.legal_actions()
            action = None
            if not checked and obs.turn == 1 and obs.acting_player == 0 and not goat_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                goat_set |= action is not None
            if not checked and obs.turn == 2 and obs.acting_player == 1 and not oppression_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == ROYAL_OPPRESSION), None)
                oppression_set |= action is not None
            if (not checked and preactivate_oppression and obs.turn == 3 and obs.acting_player == 1
                    and oppression_set and not oppression_active):
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == ROYAL_OPPRESSION), None)
                oppression_active |= action is not None
            if (not checked and obs.turn == 3 and obs.acting_player == 0 and oppression_set
                    and not goat_used and (not preactivate_oppression or oppression_active)
                    and obs.chain == ()):
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SCAPEGOAT), action)
                if action is not None and action.kind == "activate":
                    opposing_trap = next(c for c in obs.field if c.controller == 1
                                         and c.zone == "spell_trap")
                    assert opposing_trap.position == (
                        "faceup" if preactivate_oppression else "facedown")
                goat_used |= action is not None and action.kind == "activate"
            if not checked and goat_used and obs.acting_player == 1 and obs.chain:
                oppression_response = [a for a in actions if a.kind == "chain"
                                       and a.parameters.get("code") == ROYAL_OPPRESSION]
                if preactivate_oppression and not oppression_effect_used:
                    assert oppression_response, "face-up Oppression must respond to Scapegoat"
                    action = oppression_response[0]
                    oppression_effect_used = True
                elif not preactivate_oppression:
                    # A Set Oppression may flip, but cannot use its separate effect
                    # in the same chain as its activation.
                    if oppression_active:
                        assert not oppression_response
                    action = oppression_response[0] if oppression_response else action
                    oppression_active |= action is not None and action.kind == "chain"
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_zones", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if not checked and goat_used and obs.chain == () and SCAPEGOAT in {
                    c.code for c in obs.graveyards[0]}:
                assert goat_set and oppression_set and oppression_active
                assert "player0:cannot_summon_this_turn:scapegoat" in obs.restrictions
                if preactivate_oppression and oppression_effect_used:
                    assert not any(c.code in SHEEP_CODES for c in obs.field)
                    assert obs.life_points[1] == 7200
                elif not preactivate_oppression:
                    assert {c.code for c in obs.field if c.controller == 0
                            and c.zone == "monster"} == SHEEP_CODES
                    assert obs.life_points[1] == 8000
                else:
                    continue
                assert {f"goat/c{SCAPEGOAT}.lua",
                        f"official/c{ROYAL_OPPRESSION}.lua"}.issubset(
                            env.engine.probe.loaded_script_sha256)
                checked = True
    pytest.fail(f"Scapegoat/Oppression duel did not terminate: checked={checked}, "
                f"turn={obs.turn}, phase={obs.phase}, actor={obs.acting_player}, "
                f"actions={[a.kind for a in env.legal_actions()]}")
