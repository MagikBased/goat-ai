"""Limiter Removal stacks, while Book of Moon resets its End Phase destruction."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

LIMITER_GOAT = 504700037
DEKOICHI = 87621407
BOOK_OF_MOON = 14087893
LIMITER_SCRIPT = "goat/c504700037.lua"
LIMITER_SHA256 = "68a9919c8deabee329804c46081958e9c144c8161dadbaf39cd4ed975e733c88"


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("book_before_end", [False, True])
def test_double_limiter_and_book_end_phase_reset(tmp_path, book_before_end):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for script in (LIMITER_SCRIPT, f"official/c{BOOK_OF_MOON}.lua"):
        if not (root / "scripts" / script).is_file():
            pytest.skip(f"script {script} not installed")
    cards = list(VANILLA_DECK)
    # These four positions appear in the seed-100 opening hand. Use a real
    # 40-card Deck and the GOAT variant ID selected by the pinned whitelist.
    cards[0], cards[1], cards[2], cards[9] = (
        DEKOICHI, LIMITER_GOAT, LIMITER_GOAT, BOOK_OF_MOON)
    deck = tmp_path / "limiter.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert [card.code for card in observation.hand].count(LIMITER_GOAT) == 2
        assert {DEKOICHI, BOOK_OF_MOON} <= {card.code for card in observation.hand}
        summoned = targeted = False
        limiter_activations = 0
        book_activated = False
        seen_atk = set()
        for _ in range(65):
            if observation.turn >= 2:
                break
            actions = env.legal_actions()
            action = None
            own_view = env.engine.probe.observation(0)
            dekoichi = next((card for card in own_view.field
                             if card.code == DEKOICHI), None)
            if dekoichi and dekoichi.attack is not None:
                seen_atk.add(dekoichi.attack)
            if observation.acting_player == 0 and observation.phase == "main1":
                if not summoned:
                    action = next((candidate for candidate in actions
                                   if candidate.kind == "normal_summon"
                                   and candidate.parameters.get("code") == DEKOICHI), None)
                    summoned |= action is not None
                elif limiter_activations < 2:
                    action = next((candidate for candidate in actions
                                   if candidate.kind == "activate"
                                   and candidate.parameters.get("code") == LIMITER_GOAT), None)
                    if action:
                        limiter_activations += 1
                elif book_before_end and not book_activated:
                    action = next((candidate for candidate in actions
                                   if candidate.kind == "activate"
                                   and candidate.parameters.get("code") == BOOK_OF_MOON), None)
                    book_activated |= action is not None
            if book_activated and not targeted and actions[0].kind == "select_card":
                action = next((candidate for candidate in actions
                               if candidate.parameters.get("code") == DEKOICHI
                               and candidate.parameters.get("controller") == 0), None)
                targeted |= action is not None
            if action is None:
                action = next((candidate for candidate in actions
                               if candidate.kind in ("pass", "place", "end_phase")),
                              actions[0])
            observation = env.step(action)

        assert observation.turn == 2
        assert limiter_activations == 2
        assert {1400, 2800, 5600} <= seen_atk
        assert env.engine.probe.loaded_script_sha256[LIMITER_SCRIPT] == LIMITER_SHA256
        own_view = env.engine.probe.observation(0)
        if book_before_end:
            assert book_activated and targeted
            assert any(card.code == DEKOICHI and card.position == "facedown"
                       for card in own_view.field)
            assert DEKOICHI not in {card.code for card in own_view.graveyards[0]}
        else:
            assert not any(card.code == DEKOICHI for card in own_view.field)
            assert DEKOICHI in {card.code for card in own_view.graveyards[0]}

        agents = (RandomAgent(411), RandomAgent(412))
        for _ in range(5000):
            if env.is_terminal():
                break
            actions = env.legal_actions()
            observation = env.step(agents[observation.acting_player].select_action(
                observation, actions))
        assert env.is_terminal(), "Limiter Removal duel exceeded 5000 decisions"
        trajectory = env.trajectory()
        path = tmp_path / f"limiter_book_{book_before_end}.json"
        write_trajectory(path, trajectory)
        assert verify_trajectory(read_trajectory(path),
                                 ExperimentalOcgcoreEngine(root)) == len(
                                     trajectory.decisions)
        assert audit_trajectory_visibility(trajectory)["decisions"] == len(
            trajectory.decisions)
