"""D.D. Designator declares at activation and reveals only to its player."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

DESIGNATOR = 33423043
POT = 55144522
HEAVY_STORM = 19613556
RESTRICT = 504700102


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("correct_name", [False, True])
def test_designator_hit_or_miss_keeps_opponent_hand_private_until_resolution(
    tmp_path, correct_name,
):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{DESIGNATOR}.lua").is_file():
        pytest.skip("D.D. Designator script not installed")
    own = tmp_path / "designator.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        DESIGNATOR, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    opposing = tmp_path / "pot.ydk"
    opposing.write_text("#main\n" + "\n".join(map(str, (
        POT, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(opposing), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert DESIGNATOR in {c.code for c in obs.hand}
        assert POT in {c.code for c in env.engine.probe.observation(1).hand}
        own_hand_before = len(obs.hand)
        other_hand_before = obs.opponent_hand_count
        activated = named = False
        for _ in range(30):
            actions = env.legal_actions()
            action = None
            if not activated and obs.turn == 1 and obs.acting_player == 0:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == DESIGNATOR), None)
                activated = action is not None
            if activated and not named and actions[0].kind == "announce_card":
                assert obs.acting_player == 0
                assert [link.card_code for link in obs.chain] == [DESIGNATOR]
                assert obs.opponent_hand_count == other_hand_before
                assert obs.known_opponent_hand_cards == ()
                assert obs.private_reveals == ()
                codes = {a.parameters["code"] for a in actions}
                assert {POT, HEAVY_STORM, DESIGNATOR} <= codes
                assert RESTRICT not in codes
                action = next(a for a in actions if a.parameters["code"] == (
                    POT if correct_name else HEAVY_STORM))
                named = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if named and DESIGNATOR in {c.code for c in obs.graveyards[0]} \
                    and not obs.chain:
                other = env.engine.probe.observation(1)
                assert activated and named
                assert any(POT in {c.code for c in reveal.cards}
                           for reveal in obs.private_reveals)
                assert not other.private_reveals
                assert (POT in {c.code for c in obs.banished[1]}) == correct_name
                assert (POT in {c.code for c in other.hand}) != correct_name
                assert len(obs.hand) == own_hand_before - 1 - (not correct_name)
                assert obs.opponent_hand_count == other_hand_before - correct_name
                assert f"official/c{DESIGNATOR}.lua" in \
                    env.engine.probe.loaded_script_sha256
                break
        else:
            pytest.fail("D.D. Designator did not resolve within 30 decisions")
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(3000):
            if env.is_terminal():
                break
            actions = env.legal_actions()
            obs = env.step(agents[obs.acting_player].select_action(obs, actions))
        assert env.is_terminal(), "D.D. Designator duel exceeded 3000 decisions"
        path = tmp_path / f"designator_{correct_name}.json"
        write_trajectory(path, env.trajectory())
        trajectory = read_trajectory(path)
        assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) == len(
            trajectory.decisions)
        assert audit_trajectory_visibility(trajectory)["decisions"] == len(
            trajectory.decisions)
