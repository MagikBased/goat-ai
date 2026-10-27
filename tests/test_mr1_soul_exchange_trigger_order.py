"""Cross-controller trigger order in the unpatched MR1 protocol probe."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.mr1_synchro_probe import (
    CAIUS, SANGAN, SOUL_EXCHANGE, Mr1SynchroProbeEngine,
)
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_mr1_soul_exchange_opponent_sangan_chain_order(tmp_path):
    """Probe native MR1's turn-player-first order without GOAT's core patch."""
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (SOUL_EXCHANGE, SANGAN, CAIUS):
        if not (root / "scripts/official" / f"c{code}.lua").is_file():
            pytest.skip("full official card script checkout not installed")
    attacker = tmp_path / "soul_caius.ydk"
    defender = tmp_path / "sangan.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        *([SOUL_EXCHANGE] * 3), *([CAIUS] * 3), *VANILLA_DECK[6:])))
        + "\n#extra\n!side\n")
    defender.write_text("#main\n" + "\n".join(map(str, (
        SANGAN, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=15,
                         engine=Mr1SynchroProbeEngine(root)) as env:
        view = env.reset()
        summoned = soul_used = soul_targeted = caius_used = tribute_paid = False
        for _ in range(80):
            actions = env.legal_actions()

            def choose(kind, code=None):
                return next((a for a in actions if a.kind == kind and (
                    code is None or a.parameters.get("code") == code)), None)

            if tribute_paid and len(view.chain) >= 2:
                assert tuple((link.index, link.card_code) for link in view.chain[:2]) == (
                    (1, CAIUS), (2, SANGAN))
                break

            action = None
            if view.turn == 2 and view.acting_player == 1 and not summoned:
                action = choose("normal_summon", SANGAN)
                summoned = action is not None
            if view.turn == 3 and view.acting_player == 0 and summoned:
                if not soul_used:
                    action = choose("activate", SOUL_EXCHANGE)
                    soul_used = action is not None
                elif soul_targeted and not caius_used:
                    action = choose("normal_summon", CAIUS)
                    caius_used = action is not None
            if soul_used and not soul_targeted and choose("select_card"):
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 4), None)
                soul_targeted = action is not None
            if caius_used and not tribute_paid and choose("tribute"):
                action = choose("tribute", SANGAN)
                tribute_paid = action is not None
            if action is None:
                action = choose("place") or choose("pass") or choose("end_phase") or actions[0]
            view = env.step(action)
        else:
            pytest.fail("MR1 Soul Exchange / Sangan / Caius chain was not reached")

        agents = (RandomAgent(15), RandomAgent(16))
        for _ in range(3000):
            if env.is_terminal():
                break
            view = env.step(agents[view.acting_player].select_action(
                view, env.legal_actions()))
        assert env.is_terminal()
        trajectory = env.trajectory()
        assert trajectory.ruleset == "mr1-synchro-protocol"
        for code in (SOUL_EXCHANGE, SANGAN, CAIUS):
            assert f"scripts/official/c{code}.lua" in trajectory.asset_sha256
        path = tmp_path / "mr1_soul_caius.json"
        write_trajectory(path, trajectory)
        loaded = read_trajectory(path)
        assert loaded == trajectory
        assert verify_trajectory(loaded, Mr1SynchroProbeEngine(root)) == len(
            trajectory.decisions)
        assert audit_trajectory_visibility(loaded)["decisions"] == len(
            trajectory.decisions)
