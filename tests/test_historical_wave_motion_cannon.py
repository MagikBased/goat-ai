"""Wave-Motion Cannon's Main Phase cost beats a late MST response."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

CANNON = 38992735
MST = 5318639
FAITH = 31560081


def _deck(path, position, code):
    cards = list(VANILLA_DECK)
    cards[position] = code
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("mst_in_standby", [False, True])
def test_cannon_fires_if_mst_waits_until_main_phase(tmp_path, mst_in_standby):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{CANNON}.lua", f"official/c{MST}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("Cannon or MST script not installed")
    own = _deck(tmp_path / "cannon.ydk", 2, CANNON)
    other = _deck(tmp_path / "mst.ydk", 4, MST)
    with GoatEnvironment(own, other, seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert CANNON in {c.code for c in observation.hand}
        assert MST in {c.code for c in env.engine.probe.observation(1).hand}
        activated = mst_set = mst_used = mst_targeted = fired = resolved = False
        for _ in range(60):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 \
                    and not activated:
                action = next((a for a in actions if a.kind == "activate" and
                               a.parameters.get("code") == CANNON), None)
                activated |= action is not None
            if observation.turn == 2 and observation.acting_player == 1 \
                    and not mst_set:
                action = next((a for a in actions if a.kind == "set_spell_trap" and
                               a.parameters.get("code") == MST), None)
                mst_set |= action is not None
            if observation.turn == 3 and mst_in_standby and \
                    observation.phase == "standby":
                if observation.acting_player == 1 and not mst_used:
                    action = next((a for a in actions if a.kind == "chain" and
                                   a.parameters.get("code") == MST), None)
                    if action is not None:
                        assert any(c.code == CANNON for c in observation.field)
                        mst_used = True
                if mst_used and not mst_targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") ==
                                   CANNON and a.parameters.get("controller") == 0), None)
                    mst_targeted |= action is not None
            if observation.turn == 3 and observation.phase == "main1" and \
                    observation.acting_player == 0 and not mst_in_standby and not fired:
                action = next((a for a in actions if a.kind == "activate" and
                               a.parameters.get("code") == CANNON), None)
                if action is not None:
                    assert observation.life_points == (8000, 8000)
                    fired = True
            if fired and observation.turn == 3 and observation.acting_player == 1:
                assert CANNON in {c.code for c in observation.graveyards[0]}
                assert not any(a.parameters.get("code") == MST for a in actions)
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if observation.turn == 3 and observation.phase == "main1" and \
                    observation.acting_player == 0:
                if mst_in_standby and mst_targeted:
                    assert observation.life_points == (8000, 8000)
                    assert not any(a.kind == "activate" and
                                   a.parameters.get("code") == CANNON
                                   for a in env.legal_actions())
                    assert CANNON in {c.code for c in observation.graveyards[0]}
                    assert MST in {c.code for c in observation.graveyards[1]}
                    resolved = True
                elif fired and observation.life_points == (8000, 7000):
                    assert CANNON in {c.code for c in observation.graveyards[0]}
                    opponent = env.engine.probe.observation(1)
                    assert any(c.code == MST and c.position == "facedown"
                               for c in opponent.field)
                    assert MST not in {c.code for c in observation.graveyards[1]}
                    resolved = True
            if resolved:
                break
        assert resolved, "Cannon / MST timing branch did not resolve"
        assert f"official/c{CANNON}.lua" in env.engine.probe.loaded_script_sha256
        if mst_in_standby:
            assert scripts <= env.engine.probe.loaded_script_sha256.keys()

        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(5000):
            if env.is_terminal():
                break
            legal = env.legal_actions()
            observation = env.step(
                agents[observation.acting_player].select_action(observation, legal))
        assert env.is_terminal(), "Cannon / MST duel exceeded 5000 decisions"
        trajectory = env.trajectory()
        path = tmp_path / f"cannon_mst_standby_{mst_in_standby}.json"
        write_trajectory(path, trajectory)
        assert verify_trajectory(read_trajectory(path),
                                 ExperimentalOcgcoreEngine(root)) == len(
                                     trajectory.decisions)
        assert audit_trajectory_visibility(trajectory)["decisions"] == len(
            trajectory.decisions)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_faith_recovers_fired_cannon_and_reactivation_resets_phase_count(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{CANNON}.lua", f"official/c{FAITH}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("Cannon or Faith script not installed")
    cards = list(VANILLA_DECK)
    cards[2], cards[1] = CANNON, FAITH
    deck = tmp_path / "faith_cannon.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert {CANNON, FAITH} <= {c.code for c in observation.hand}
        first_activated = faith_set = first_fired = flipped = targeted = False
        recovered = second_activated = second_fired = False
        second_field_seen = False
        for _ in range(85):
            actions = env.legal_actions()
            action = None
            if observation.acting_player == 0 and observation.phase == "main1":
                if observation.turn == 1:
                    if not first_activated:
                        action = next((a for a in actions if a.kind == "activate" and
                                       a.parameters.get("code") == CANNON), None)
                        first_activated |= action is not None
                    if first_activated and not faith_set and action is None:
                        action = next((a for a in actions if a.kind == "set_monster" and
                                       a.parameters.get("code") == FAITH), None)
                        faith_set |= action is not None
                if observation.turn == 3:
                    if not first_fired:
                        action = next((a for a in actions if a.kind == "activate" and
                                       a.parameters.get("code") == CANNON and
                                       a.parameters.get("location") == 8), None)
                        first_fired |= action is not None
                    if first_fired and not flipped and action is None:
                        action = next((a for a in actions if a.kind == "flip_summon" and
                                       a.parameters.get("code") == FAITH), None)
                        flipped |= action is not None
                    if recovered and not second_activated and action is None:
                        action = next((a for a in actions if a.kind == "activate" and
                                       a.parameters.get("code") == CANNON and
                                       a.parameters.get("location") == 2), None)
                        second_activated |= action is not None
                if observation.turn == 5 and not second_fired:
                    assert observation.life_points == (8000, 7000)
                    action = next((a for a in actions if a.kind == "activate" and
                                   a.parameters.get("code") == CANNON and
                                   a.parameters.get("location") == 8), None)
                    second_fired |= action is not None
            if flipped and not targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") ==
                               CANNON and a.parameters.get("location") == 16), None)
                targeted |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            owner = env.engine.probe.observation(0)
            opponent = env.engine.probe.observation(1)
            if targeted and not recovered and CANNON in {c.code for c in owner.hand}:
                assert owner.life_points == (8000, 7000)
                assert CANNON not in {c.code for c in owner.graveyards[0]}
                assert opponent.known_opponent_hand_cards == (CANNON,)
                assert len(opponent.private_reveals) == 1
                assert opponent.private_reveals[0].recipient == 1
                assert [c.code for c in opponent.private_reveals[0].cards] == [CANNON]
                assert not owner.private_reveals
                recovered = True
            if second_activated and not second_field_seen and \
                    CANNON in {c.code for c in owner.field}:
                assert CANNON not in {c.code for c in owner.hand}
                assert opponent.known_opponent_hand_cards == ()
                assert owner.life_points == (8000, 7000)
                second_field_seen = True
            if second_fired and owner.life_points == (8000, 6000):
                assert first_activated and faith_set and first_fired
                assert flipped and targeted and recovered and second_field_seen
                assert CANNON in {c.code for c in owner.graveyards[0]}
                assert CANNON not in {c.code for c in owner.field}
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                break
        else:
            pytest.fail("Faith/Cannon reuse did not deal a second 1000 damage")

        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(5000):
            if env.is_terminal():
                break
            legal = env.legal_actions()
            observation = env.step(
                agents[observation.acting_player].select_action(observation, legal))
        assert env.is_terminal(), "Faith/Cannon duel exceeded 5000 decisions"
        trajectory = env.trajectory()
        path = tmp_path / "faith_cannon_reuse.json"
        write_trajectory(path, trajectory)
        assert verify_trajectory(read_trajectory(path),
                                 ExperimentalOcgcoreEngine(root)) == len(
                                     trajectory.decisions)
        assert audit_trajectory_visibility(trajectory)["decisions"] == len(
            trajectory.decisions)
