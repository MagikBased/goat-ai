"""Nobleman's target decision must not disclose a hidden Flip identity."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

NOBLEMAN = 504700116
DEKOICHI = 87621407
KYCOO = 88240808
VANILLA = VANILLA_DECK[0]


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_nobleman_target_observation_is_identical_for_hidden_flip_or_nonflip(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{NOBLEMAN}.lua", f"official/c{DEKOICHI}.lua",
                     f"official/c{KYCOO}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")

    def run(hidden_code):
        opponent = tmp_path / f"hidden_{hidden_code}.ydk"
        opponent.write_text("#main\n" + "\n".join(map(str, (
            *([hidden_code] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
        with GoatEnvironment("examples/decks/nobleman_probe.ydk", str(opponent), seed=52,
                             engine=ExperimentalOcgcoreEngine(root)) as env:
            obs = env.reset()
            assert hidden_code in {c.code for c in env.engine.probe.observation(1).hand}
            set_done = activated = targeted = False
            decision = resolution = None
            deck_count_at_target = None
            for _ in range(55):
                actions = env.legal_actions()
                action = None
                if obs.turn == 2 and obs.acting_player == 1 and not set_done:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == hidden_code), None)
                    set_done |= action is not None
                if obs.turn == 3 and obs.acting_player == 0 and not activated:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == NOBLEMAN), None)
                    activated |= action is not None
                if activated and not targeted and actions[0].kind == "select_card":
                    assert obs.viewer == obs.acting_player == 0
                    assert obs.known_opponent_field_cards == ()
                    assert not obs.private_reveals
                    assert all("code" not in a.parameters for a in actions)
                    decision = (obs, actions)
                    deck_count_at_target = obs.deck_counts
                    action = actions[0]
                    targeted = True
                if action is None:
                    action = next((a for a in actions if a.kind in ("pass", "end_phase")),
                                  actions[0])
                obs = env.step(action)
                if targeted and hidden_code in {c.code for c in obs.banished[1]}:
                    resolution = obs
                    break
            assert set_done and activated and targeted and resolution is not None
            assert decision is not None
            assert f"goat/c{NOBLEMAN}.lua" in env.engine.probe.loaded_script_sha256
            owner_reveals = env.engine.probe.observation(1).private_reveals
            agents = (RandomAgent(52), RandomAgent(53))
            for _ in range(3000):
                if env.is_terminal():
                    break
                legal = env.legal_actions()
                obs = env.step(agents[obs.acting_player].select_action(obs, legal))
            assert env.is_terminal(), "Nobleman duel did not terminate"
            trajectory_path = tmp_path / f"nobleman_hidden_{hidden_code}.json"
            write_trajectory(trajectory_path, env.trajectory())
            assert verify_trajectory(read_trajectory(trajectory_path),
                                     ExperimentalOcgcoreEngine(root)) == len(
                                         env.trajectory().decisions)
            return decision, resolution, deck_count_at_target, owner_reveals

    (flip_obs, flip_actions), flip_resolved, flip_decks, flip_owner_reveals = run(DEKOICHI)
    (normal_obs, normal_actions), normal_resolved, normal_decks, normal_owner_reveals = run(
        KYCOO)
    assert flip_obs == normal_obs
    assert flip_actions == normal_actions
    assert any(c.code == DEKOICHI for c in flip_resolved.banished[1])
    assert any(c.code == KYCOO for c in normal_resolved.banished[1])
    assert flip_resolved.private_reveals
    assert flip_owner_reveals
    assert not normal_resolved.private_reveals
    assert not normal_owner_reveals
    assert flip_resolved.deck_counts[1] < flip_decks[1]
    assert normal_resolved.deck_counts == normal_decks
    assert sum(c.code == KYCOO for c in normal_resolved.banished[1]) == 1


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_two_hidden_targets_keep_nobleman_choices_identical_when_swapped(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/goat/c{NOBLEMAN}.lua").is_file():
        pytest.skip("GOAT Nobleman script not installed")
    normal = 97923414  # one-copy vanilla at the last probe-deck position
    assert VANILLA_DECK[-1] == normal

    def reach_target(first, second):
        cards = [first, *VANILLA_DECK[1:-1], second]
        opponent = tmp_path / f"opponent_{first}.ydk"
        opponent.write_text("#main\n" + "\n".join(map(str, cards))
                            + "\n#extra\n!side\n")
        with GoatEnvironment("examples/decks/nobleman_probe.ydk", str(opponent),
                             seed=52, engine=ExperimentalOcgcoreEngine(root)) as env:
            obs = env.reset()
            assert {DEKOICHI, normal} <= {
                c.code for c in env.engine.probe.observation(1).hand}
            first_set = second_set = activated = False
            for _ in range(100):
                actions = env.legal_actions()
                action = None
                if obs.turn == 2 and obs.acting_player == 1 and not first_set:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == first), None)
                    first_set = action is not None
                if obs.turn == 4 and obs.acting_player == 1 and not second_set:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == second), None)
                    second_set = action is not None
                if obs.turn == 5 and obs.acting_player == 0 \
                        and second_set and not activated:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == NOBLEMAN), None)
                    activated = action is not None
                if activated and actions[0].kind == "select_card":
                    assert obs.viewer == obs.acting_player == 0
                    assert len(actions) == 2
                    assert {a.parameters.get("sequence") for a in actions} == {0, 1}
                    assert all(a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 4
                               and "code" not in a.parameters for a in actions)
                    assert len([c for c in obs.field if c.controller == 1
                                and c.position == "facedown" and c.code is None]) == 2
                    native_slots = env.engine.probe._query_location(1, 4)
                    assert native_slots[0].code == first
                    assert native_slots[1].code == second
                    return obs, actions
                if action is None:
                    action = next((a for a in actions if a.kind in (
                        "pass", "end_phase")), actions[0])
                obs = env.step(action)
        pytest.fail("two-set-monster Nobleman target choice was not reached")

    first_observation, first_actions = reach_target(DEKOICHI, normal)
    second_observation, second_actions = reach_target(normal, DEKOICHI)
    assert first_observation == second_observation
    assert first_actions == second_actions
