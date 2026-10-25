"""Large native card selections can be made incrementally and replayed."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine import native_messages
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

GRACEFUL = 79571449
SANGAN = 504700178
THUNDER = 504700054


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
                for _ in range(copy_count):
                    action = next(a for a in env.legal_actions() if a.kind == "select_card")
                    obs = env.step(action)
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
                before_native_prompt = env.engine.probe._pending_message
                assert before_native_prompt[0] == 15
                action = next(a for a in actions if a.parameters.get("code") == SANGAN)
                selected_first = True
            elif selected_first and not selected_second and actions[0].kind == "select_card":
                assert env.engine.probe._pending_message == before_native_prompt
                assert all(a.parameters["cards"][0]["code"] == SANGAN for a in actions)
                assert SANGAN not in {card.code for card in obs.graveyards[0]}
                action = next(a for a in actions if a.parameters.get("code") != SANGAN)
                selected_second = True
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if selected_second and not committed_checked:
                assert SANGAN in {card.code for card in obs.graveyards[0]}
                assert len(env.engine.probe.observation(0).hand) == 6
                committed_checked = True
    pytest.fail("staged Graceful duel exceeded 3000 decisions")
