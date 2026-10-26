"""Solemn negates Time Seal before it can skip the next Draw Phase."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

TIME_SEAL = 35316708
SOLEMN = 41420027


def _deck(path, card):
    path.write_text("#main\n" + "\n".join(map(str, (
        card, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("negate", [False, True])
def test_solemn_response_controls_time_seal_next_draw(tmp_path, negate):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (TIME_SEAL, SOLEMN)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required official card script not installed")
    decks = (_deck(tmp_path / "seal.ydk", TIME_SEAL),
             _deck(tmp_path / "solemn.ydk", SOLEMN))
    with GoatEnvironment(*decks, seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert TIME_SEAL in {c.code for c in obs.hand}
        assert SOLEMN in {c.code for c in env.engine.probe.observation(1).hand}
        seal_set = solemn_set = seal_activated = solemn_chained = False
        draw_baseline = None
        for _ in range(95):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not seal_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == TIME_SEAL), None)
                seal_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not solemn_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SOLEMN), None)
                solemn_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not seal_activated:
                assert seal_set and solemn_set
                draw_baseline = obs.deck_counts[1]
                action = next((a for a in actions if a.kind in ("activate", "chain")
                               and a.parameters.get("code") == TIME_SEAL), None)
                seal_activated |= action is not None
            if (negate and seal_activated and obs.acting_player == 1
                    and not solemn_chained):
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SOLEMN), action)
                solemn_chained |= action is not None and action.kind == "chain"
                if solemn_chained:
                    assert [link.card_code for link in obs.chain] == [TIME_SEAL]
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if obs.turn == 4:
                assert seal_activated and draw_baseline is not None
                assert obs.deck_counts[1] == draw_baseline - int(negate)
                assert obs.life_points[1] == (4000 if negate else 8000)
                assert TIME_SEAL in {c.code for c in obs.graveyards[0]}
                assert (SOLEMN in {c.code for c in obs.graveyards[1]}) == negate
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                break
        else:
            pytest.fail("Time Seal / Solemn did not reach the next Draw Phase")

        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(3000):
            if env.is_terminal():
                break
            obs = env.step(agents[obs.acting_player].select_action(obs, env.legal_actions()))
        else:
            pytest.fail("Time Seal / Solemn duel exceeded 3000 decisions")
        trajectory = env.trajectory()
        assert trajectory.winner in (0, 1, None)
    path = tmp_path / f"time_seal_solemn_{negate}.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    assert audit_trajectory_visibility(loaded)["decisions"] == len(loaded.decisions)
    assert verify_trajectory(loaded, ExperimentalOcgcoreEngine(root)) == len(
        trajectory.decisions)
