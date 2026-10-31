"""Different Dimension Capsule's face-down banish stays private to its owner."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.observations import CardView, Observation
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

CAPSULE = 11961740


def test_observation_rejects_opponent_facedown_banished_identity():
    kwargs = dict(viewer=0, acting_player=0, turn=1, phase="main1",
                  life_points=(8000, 8000), hand=(), field=(),
                  graveyards=((), ()), opponent_hand_count=0,
                  deck_counts=(40, 40), extra_deck_counts=(0, 0))
    with pytest.raises(ValueError, match="opponent facedown identity"):
        Observation(**kwargs, banished=((), (
            CardView(1, "banished", "facedown", 123, 0),)))
    visible = Observation(**kwargs, banished=((), (
        CardView(1, "banished", "facedown", None, 0),)))
    assert visible.banished[1][0].code is None


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_capsule_choice_changes_only_owner_visible_banished_identity(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{CAPSULE}.lua").is_file():
        pytest.skip("full card script checkout not installed")
    deck = tmp_path / "capsule.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        *([CAPSULE] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    opponent_views = []
    opponent_decisions = []
    own_codes = []
    for selected_code in (11321183, 15025844):
        with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=0,
                             engine=ExperimentalOcgcoreEngine(root)) as env:
            observation = env.reset()
            for _ in range(20):
                actions = env.legal_actions()
                capsule_pick = next((action for action in actions
                                     if action.kind == "select_card"
                                     and action.parameters.get("location") == 1
                                     and action.parameters.get("code") == selected_code), None)
                if capsule_pick is not None:
                    observation = env.step(capsule_pick)
                    break
                action = next((action for action in actions if action.kind == "activate"
                               and action.parameters.get("code") == CAPSULE), None)
                if action is None:
                    action = next((action for action in actions if action.kind in (
                        "place", "pass", "end_phase")), actions[0])
                observation = env.step(action)
            else:
                pytest.fail("Capsule did not offer a Deck card choice")
            own = env.engine.probe.observation(0)
            opposing = env.engine.probe.observation(1)
            assert len(own.banished[0]) == len(opposing.banished[0]) == 1
            assert own.banished[0][0].position == "facedown"
            assert own.banished[0][0].code == selected_code
            assert opposing.banished[0][0].code is None
            own_codes.append(own.banished[0][0].code)
            opponent_views.append(opposing)

            for _ in range(25):
                if (observation.turn == 2 and observation.acting_player == 1
                        and observation.phase == "main1"):
                    assert observation.banished[0][0].code is None
                    assert len(env.legal_actions()) > 1
                    opponent_decisions.append((observation, env.legal_actions()))
                    break
                actions = env.legal_actions()
                action = next((candidate for candidate in actions
                               if candidate.kind in ("place", "pass", "end_phase")),
                              actions[0])
                observation = env.step(action)
            else:
                pytest.fail("opponent Main Phase after Capsule was not reached")

            agents = (RandomAgent(0), RandomAgent(1))
            for _ in range(3000):
                if env.is_terminal():
                    break
                observation = env.step(agents[observation.acting_player].select_action(
                    observation, env.legal_actions()))
            assert env.is_terminal()
            path = tmp_path / f"capsule_{selected_code}.json"
            write_trajectory(path, env.trajectory())
            trajectory = read_trajectory(path)
            audit_trajectory_visibility(trajectory)
            assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) == len(
                trajectory.decisions)
    assert own_codes[0] != own_codes[1]
    assert opponent_views[0] == opponent_views[1]
    assert opponent_decisions[0] == opponent_decisions[1]
