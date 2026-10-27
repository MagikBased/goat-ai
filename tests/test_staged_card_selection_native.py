"""Large native card selections can be made incrementally and replayed."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine import native_messages
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory
from scripts.probe_random_decks import generate_deck, write_deck

GRACEFUL = 79571449
SANGAN = 504700178
THUNDER = 504700054


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_staged_puppet_magic_sum_matches_flat_native_choice(tmp_path, monkeypatch):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    seed = 10097
    decks = (tmp_path / "sum_first.ydk", tmp_path / "sum_second.ydk")
    write_deck(decks[0], generate_deck(root, seed))
    write_deck(decks[1], generate_deck(root, seed + 1_000_000))

    def run(staged: bool, target_code: int | None = None):
        monkeypatch.setattr(native_messages, "MAX_SUM_SELECTION_COMBINATIONS",
                            1 if staged else 4096)
        with GoatEnvironment(*(str(deck) for deck in decks), seed=seed,
                             engine=ExperimentalOcgcoreEngine(root)) as env:
            observation = env.reset()
            agent = RandomAgent(seed)
            after_sum = None
            for _ in range(3000):
                actions = env.legal_actions()
                if after_sum is None and env.engine.probe._pending_message[0] == 23:
                    assert observation.chain[-1].card_code == 40703393
                    if staged:
                        assert env.engine.probe.decode_pending().sum_selection is not None
                        choice = next(action for action in actions
                                      if action.kind == "select_card"
                                      and action.parameters.get("code") == target_code)
                        native_prompt = env.engine.probe._pending_message
                        observation = env.step(choice)
                        assert env.engine.probe._pending_message == native_prompt
                        finish = next(action for action in env.legal_actions()
                                      if action.kind == "finish_selection")
                        observation = env.step(finish)
                    else:
                        choice = actions[0]
                        target_code = choice.parameters["code"]
                        observation = env.step(choice)
                    after_sum = (observation, env.legal_actions())
                    continue
                observation = env.step(agent.select_action(observation, actions))
                if env.is_terminal():
                    break
            assert after_sum is not None and env.is_terminal()
            trajectory = env.trajectory()
            assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) == len(
                trajectory.decisions)
            audit_trajectory_visibility(trajectory)
            return after_sum, target_code

    flat, selected_code = run(False)
    staged, _ = run(True, selected_code)
    assert staged == flat


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("copy_count", [0, 1, 2])
def test_staged_thunder_search_matches_flat_native_choice(tmp_path, monkeypatch,
                                                          copy_count):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/goat/c{THUNDER}.lua").is_file():
        pytest.skip("GOAT Thunder Dragon script not installed")
    deck = tmp_path / "thunder.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        *([THUNDER] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    def run(staged: bool):
        monkeypatch.setattr(native_messages, "MAX_CARD_SELECTION_COMBINATIONS",
                            1 if staged else 4096)
        with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=4,
                             engine=ExperimentalOcgcoreEngine(root)) as env:
            obs = env.reset()
            activated = False
            for _ in range(20):
                actions = env.legal_actions()
                if activated and any(a.kind == "select_card"
                                     and a.parameters.get("location") == 1 for a in actions):
                    break
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == THUNDER), None)
                activated |= action is not None
                if action is None:
                    action = next((a for a in actions if a.kind == "pass"), actions[0])
                obs = env.step(action)
            else:
                pytest.fail("Thunder Dragon search prompt not reached")

            if staged:
                assert len([a for a in actions if a.kind == "select_card"]) == 2
                assert {(a.parameters["selection_minimum"],
                         a.parameters["selection_maximum"],
                         a.parameters["selected_count"]) for a in actions} == {(0, 2, 0)}
                for _ in range(copy_count):
                    action = next(a for a in env.legal_actions() if a.kind == "select_card")
                    before_pick = obs
                    obs = env.step(action)
                    if action.parameters["selected_count"] + 1 < 2:
                        assert obs is before_pick
                if copy_count < 2:
                    finish = next(a for a in env.legal_actions()
                                  if a.kind == "finish_selection")
                    obs = env.step(finish)
            else:
                action = next(a for a in actions if
                              (a.kind == "select_cards"
                               and len(a.parameters.get("cards", ())) == copy_count)
                              or (copy_count == 1 and a.kind == "select_card"))
                obs = env.step(action)
            return obs, env.legal_actions()

    assert run(True) == run(False)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_staged_graceful_discard_commits_one_exact_native_response(tmp_path, monkeypatch):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{GRACEFUL}.lua").is_file():
        pytest.skip("Graceful Charity script not installed")
    monkeypatch.setattr(native_messages, "MAX_CARD_SELECTION_COMBINATIONS", 1)
    deck = tmp_path / "graceful.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL, SANGAN, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    agents = (RandomAgent(18), RandomAgent(19))
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, SANGAN} <= {card.code for card in obs.hand}
        activated = selected_first = selected_second = committed_checked = False
        before_native_prompt = None
        for _ in range(3000):
            if env.is_terminal():
                assert selected_second
                path = tmp_path / "staged_graceful.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if not activated and obs.acting_player == 0:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == GRACEFUL), None)
                activated |= action is not None
            if activated and not selected_first and actions[0].kind == "select_card":
                assert len(obs.hand) == 8
                assert obs.deck_counts[0] == 31
                assert (actions[0].parameters["selection_minimum"],
                        actions[0].parameters["selection_maximum"],
                        actions[0].parameters["selected_count"]) == (2, 2, 0)
                before_native_prompt = env.engine.probe._pending_message
                assert before_native_prompt[0] == 15
                action = next(a for a in actions if a.parameters.get("code") == SANGAN)
                selected_first = True
            elif selected_first and not selected_second and actions[0].kind == "select_card":
                assert env.engine.probe._pending_message == before_native_prompt
                assert all(a.parameters["cards"][0]["code"] == SANGAN for a in actions)
                assert all(a.parameters["selected_count"] == 1 for a in actions)
                assert SANGAN not in {card.code for card in obs.graveyards[0]}
                action = next(a for a in actions if a.parameters.get("code") != SANGAN)
                selected_second = True
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            before_step = obs
            obs = env.step(action)
            if selected_first and not selected_second and action.kind == "select_card":
                assert obs is before_step
            if selected_second and not committed_checked:
                assert SANGAN in {card.code for card in obs.graveyards[0]}
                assert len(env.engine.probe.observation(0).hand) == 6
                committed_checked = True
    pytest.fail("staged Graceful duel exceeded 3000 decisions")
