"""Archived Appropriate timing distinguishes an active Trap from a Set one."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

POT_OF_GREED = 55144522
GRACEFUL_CHARITY = 79571449
APPROPRIATE = 48539234


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("activate_appropriate", [False, True])
def test_appropriate_must_be_active_before_graceful_resolves(
        tmp_path, activate_appropriate):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (POT_OF_GREED, GRACEFUL_CHARITY, APPROPRIATE):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    own = tmp_path / "pot_graceful.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        POT_OF_GREED, GRACEFUL_CHARITY, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    opponent = tmp_path / "appropriate.ydk"
    opponent.write_text("#main\n" + "\n".join(map(str, (
        APPROPRIATE, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(opponent), 52,
                         ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {POT_OF_GREED, GRACEFUL_CHARITY} <= {card.code for card in obs.hand}
        assert APPROPRIATE in {
            card.code for card in env.engine.probe.observation(1).hand}
        set_trap = pot_used = app_decided = graceful_used = discarded = checked = False
        for _ in range(500):
            if env.is_terminal():
                assert set_trap and pot_used and app_decided and graceful_used
                assert discarded and checked
                path = tmp_path / f"appropriate_{activate_appropriate}.json"
                write_trajectory(path, env.trajectory())
                trajectory = read_trajectory(path)
                assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) == len(
                    trajectory.decisions)
                audit_trajectory_visibility(trajectory)
                for code in (POT_OF_GREED, GRACEFUL_CHARITY, APPROPRIATE):
                    assert f"official/c{code}.lua" in (
                        env.engine.probe.loaded_script_sha256)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1 and not set_trap:
                action = next((candidate for candidate in actions
                               if candidate.kind == "set_spell_trap" and
                               candidate.parameters.get("code") == APPROPRIATE), None)
                set_trap = action is not None
            if (obs.turn == 3 and obs.acting_player == 0 and obs.phase == "main1"
                    and any(candidate.kind == "end_phase" for candidate in actions)):
                code = (POT_OF_GREED if not pot_used else GRACEFUL_CHARITY
                        if app_decided and not graceful_used else None)
                if code is not None:
                    action = next((candidate for candidate in actions
                                   if candidate.kind == "activate" and
                                   candidate.parameters.get("code") == code), None)
                    assert action is not None
                    pot_used |= code == POT_OF_GREED
                    graceful_used |= code == GRACEFUL_CHARITY
            if (pot_used and not app_decided and obs.acting_player == 1
                    and any(candidate.kind == "chain" and
                            candidate.parameters.get("code") == APPROPRIATE
                            for candidate in actions)):
                app_decided = True
                if activate_appropriate:
                    action = next(candidate for candidate in actions
                                  if candidate.kind == "chain" and
                                  candidate.parameters.get("code") == APPROPRIATE)
                else:
                    action = next(candidate for candidate in actions
                                  if candidate.kind == "pass")
            if graceful_used and not discarded and actions[0].kind == "select_cards":
                assert obs.acting_player == 0
                assert obs.deck_counts == (28, 34)
                action = actions[0]
                discarded = True
            if action is None:
                action = next((candidate for candidate in actions
                               if candidate.kind in ("end_phase", "pass")), actions[0])
            obs = env.step(action)
            if discarded and not checked:
                expected_opponent_deck = 32 if activate_appropriate else 34
                assert obs.deck_counts == (28, expected_opponent_deck)
                assert obs.opponent_hand_count == (7 if activate_appropriate else 5)
                assert not any(candidate.kind == "chain" and
                               candidate.parameters.get("code") == APPROPRIATE
                               for candidate in env.legal_actions())
                checked = True
    pytest.fail("Appropriate/Graceful fixture did not terminate")
