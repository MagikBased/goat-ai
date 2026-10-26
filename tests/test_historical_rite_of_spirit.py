"""Rite of Spirit revives a Gravekeeper through historical Necrovalley."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

GRACEFUL = 79571449
SPY = 504700044  # GOAT variant
NECROVALLEY = 511002998  # pre-errata variant
RITE = 30450531


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_rite_revives_spy_through_necrovalley_and_replays(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{GRACEFUL}.lua", f"goat/c{SPY}.lua",
               f"pre-errata/c{NECROVALLEY}.lua", f"official/c{RITE}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required historical scripts not installed")

    # Seed 100 draws positions 2, 13, 1, 9, 17, 0 from this 40-card list.
    cards = list(VANILLA_DECK)
    for index, code in ((2, GRACEFUL), (1, SPY), (9, NECROVALLEY), (0, RITE)):
        cards[index] = code
    deck = tmp_path / "rite_spy_necrovalley.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert {GRACEFUL, SPY, NECROVALLEY, RITE} <= {
            card.code for card in observation.hand}
        graceful = discarded = necrovalley = rite_set = rite_chained = targeted = False
        for _ in range(80):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate" and
                                   a.parameters.get("code") == GRACEFUL), None)
                    graceful |= action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if SPY in {
                        card["code"] for card in a.parameters["cards"]} and
                        {NECROVALLEY, RITE}.isdisjoint(
                            card["code"] for card in a.parameters["cards"])), None)
                    discarded |= action is not None
                if discarded and not necrovalley and action is None:
                    action = next((a for a in actions if a.kind == "activate" and
                                   a.parameters.get("code") == NECROVALLEY), None)
                    necrovalley |= action is not None
                if necrovalley and not rite_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap" and
                                   a.parameters.get("code") == RITE), None)
                    rite_set |= action is not None
            if observation.turn == 2 and observation.acting_player == 0:
                if rite_set and not rite_chained:
                    action = next((a for a in actions if a.kind == "chain" and
                                   a.parameters.get("code") == RITE), None)
                    if action is not None:
                        assert SPY in {card.code for card in observation.graveyards[0]}
                        assert any(card.code == NECROVALLEY and card.position == "faceup"
                                   for card in observation.field)
                        rite_chained = True
                if rite_chained and not targeted and actions[0].kind == "select_card":
                    assert {a.parameters["code"] for a in actions} == {SPY}
                    action = next(a for a in actions if a.parameters["code"] == SPY)
                    targeted = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if targeted and any(card.code == SPY for card in observation.field):
                assert any(card.code == SPY and card.controller == 0 and
                           card.position == "faceup" for card in observation.field)
                assert SPY not in {card.code for card in observation.graveyards[0]}
                assert RITE in {card.code for card in observation.graveyards[0]}
                assert any(card.code == NECROVALLEY and card.position == "faceup"
                           for card in observation.field)
                opponent = env.engine.probe.observation(1)
                assert any(card.code == SPY and card.position == "faceup"
                           for card in opponent.field)
                assert not opponent.private_reveals
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                break
        else:
            pytest.fail("Rite did not revive Spy through Necrovalley")

        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(5000):
            if env.is_terminal():
                break
            legal = env.legal_actions()
            observation = env.step(
                agents[observation.acting_player].select_action(observation, legal))
        assert env.is_terminal(), "Rite duel exceeded 5000 decisions"
        trajectory = env.trajectory()
        path = tmp_path / "rite_spy_necrovalley.json"
        write_trajectory(path, trajectory)
        assert verify_trajectory(read_trajectory(path),
                                 ExperimentalOcgcoreEngine(root)) == len(
                                     trajectory.decisions)
        assert audit_trajectory_visibility(trajectory)["decisions"] == len(
            trajectory.decisions)
