"""2010 Ryko target timing in the isolated MR1 native protocol."""

import hashlib
import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.mr1_synchro_probe import RYKO, Mr1SynchroProbeEngine
from goat_ai.engine.ocgcore_probe import PRE_ERRATA_RYKO_SHA256, UPSTREAM_RYKO_SHA256
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory


@pytest.mark.parametrize("set_opponent_monster", [False, True])
@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_ryko_targets_before_chain_resolution_and_mills_three(
        tmp_path, set_opponent_monster):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    official = root / f"scripts/official/c{RYKO}.lua"
    period = root / "scripts/pre-errata/c511003007.lua"
    assert hashlib.sha256(official.read_bytes()).hexdigest() == UPSTREAM_RYKO_SHA256
    assert hashlib.sha256(period.read_bytes()).hexdigest() == PRE_ERRATA_RYKO_SHA256

    attacker = tmp_path / "ryko.ydk"
    defender = tmp_path / "vanilla.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        *(RYKO for _ in range(3)), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    defender.write_text("#main\n" + "\n".join(map(str, VANILLA_DECK))
                        + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=0,
                         engine=Mr1SynchroProbeEngine(root)) as env:
        view = env.reset()
        opponent_code = None
        target_selected = False
        target_deck_count = None
        resolution_seen = False
        for _ in range(80):
            actions = env.legal_actions()

            def choose(kind, code=None, actions=actions):
                return next((a for a in actions if a.kind == kind and (
                    code is None or a.parameters.get("code") == code)), None)

            action = None
            if view.turn == 1 and view.acting_player == 0:
                action = choose("set_monster", RYKO)
            elif view.turn == 2 and view.acting_player == 1:
                action = next((a for a in actions if a.kind == (
                    "set_monster" if set_opponent_monster else "normal_summon")), None)
                if action is not None:
                    opponent_code = action.parameters["code"]
            elif view.turn == 3 and view.acting_player == 0:
                action = choose("flip_summon", RYKO) or choose("yes")
                if action is None and view.chain:
                    action = next((a for a in actions if a.kind == "select_card"
                                   and a.parameters.get("controller") == 1
                                   and a.parameters.get("location") == 4), None)
                    if action is not None:
                        # This selection happens while Ryko's Chain Link is
                        # pending, before either player passes to resolution.
                        assert view.chain[0].card_code == RYKO
                        field_card = next(card for card in view.field
                                          if card.controller == 1 and card.zone == "monster")
                        if set_opponent_monster:
                            assert field_card.code is None
                            assert "code" not in action.parameters
                        else:
                            assert field_card.code == opponent_code
                            assert action.parameters["code"] == opponent_code
                        target_selected = True
                        target_deck_count = view.deck_counts[0]
            action = action or choose("place") or choose("end_phase") or choose("pass")
            assert action is not None
            view = env.step(action)
            if (target_selected and not view.chain
                    and any(card.code == opponent_code for card in view.graveyards[1])):
                assert view.deck_counts[0] == target_deck_count - 3
                resolution_seen = True
                break
        assert resolution_seen, "Ryko's targeted destruction and mill did not resolve"
        assert env.engine.probe.loaded_script_sha256[f"official/c{RYKO}.lua"] == (
            PRE_ERRATA_RYKO_SHA256)

        agents = (RandomAgent(0), RandomAgent(1))
        for _ in range(3000):
            if env.is_terminal():
                break
            view = env.step(agents[view.acting_player].select_action(
                view, env.legal_actions()))
        assert env.is_terminal()
        trajectory = env.trajectory()

    path = tmp_path / "mr1_ryko.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    assert verify_trajectory(loaded, Mr1SynchroProbeEngine(root)) == len(
        trajectory.decisions)
    assert audit_trajectory_visibility(loaded)["decisions"] == len(
        loaded.decisions)
