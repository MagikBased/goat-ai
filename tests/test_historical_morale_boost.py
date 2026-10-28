"""Morale Boost uses the Equip Card's field controller when it leaves play."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import verify_trajectory

MORALE_BOOST = 93671934
SNATCH_STEAL = 45986603
MYSTICAL_SPACE_TYPHOON = 5318639
LOADED_MORALE_SHA256 = "3cda0dc2671fb47d6b2dcb212e7f99bff1bc5e142686e7c35b0c6ded7dc65c20"


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_morale_boost_recovers_and_damages_equip_controller(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (MORALE_BOOST, SNATCH_STEAL, MYSTICAL_SPACE_TYPHOON):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    deck = tmp_path / "morale.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        MORALE_BOOST, SNATCH_STEAL, MYSTICAL_SPACE_TYPHOON,
        *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {MORALE_BOOST, SNATCH_STEAL, MYSTICAL_SPACE_TYPHOON} <= {
            card.code for card in obs.hand}
        morale = summoned = snatch = mst = healed = damaged = False
        random_agent = RandomAgent(100)
        for _ in range(3000):
            if env.is_terminal():
                assert healed and damaged
                trajectory = env.trajectory()
                assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) == len(
                    trajectory.decisions)
                assert audit_trajectory_visibility(trajectory)["decisions"] == len(
                    trajectory.decisions)
                return
            actions = env.legal_actions()
            action = None
            if snatch and not healed and obs.life_points[0] == 9000:
                assert any(card.code == SNATCH_STEAL and card.controller == 0
                           for card in obs.field)
                assert any(card.zone == "monster" and card.controller == 0
                           for card in obs.field)
                healed = True
            if mst and not damaged and obs.life_points[0] == 8000 \
                    and SNATCH_STEAL in {card.code for card in obs.graveyards[0]}:
                assert any(card.code == MORALE_BOOST for card in obs.field)
                assert any(card.zone == "monster" and card.controller == 1
                           for card in obs.field)
                assert env.engine.probe.loaded_script_sha256[
                    "official/c93671934.lua"] == LOADED_MORALE_SHA256
                damaged = True
            if not damaged:
                if obs.acting_player == 0 and obs.turn == 1 and not morale:
                    action = next((candidate for candidate in actions
                                   if candidate.kind == "activate"
                                   and candidate.parameters.get("code") == MORALE_BOOST), None)
                    morale |= action is not None
                if obs.acting_player == 1 and obs.turn == 2 and not summoned:
                    action = next((candidate for candidate in actions
                                   if candidate.kind == "normal_summon"), None)
                    summoned |= action is not None
                if obs.acting_player == 0 and obs.turn >= 3 and summoned:
                    if not snatch:
                        action = next((candidate for candidate in actions
                                       if candidate.kind == "activate"
                                       and candidate.parameters.get("code") == SNATCH_STEAL),
                                      None)
                        snatch |= action is not None
                    elif healed and not mst:
                        action = next((candidate for candidate in actions
                                       if candidate.kind == "activate"
                                       and candidate.parameters.get("code")
                                       == MYSTICAL_SPACE_TYPHOON), None)
                        mst |= action is not None
                if action is None and actions[0].kind == "select_card":
                    target = (SNATCH_STEAL if mst else next((card.code for card in obs.field
                                                            if card.zone == "monster"
                                                            and card.controller == 1), None))
                    action = next((candidate for candidate in actions
                                   if candidate.parameters.get("code") == target), None)
                if action is None:
                    action = next((candidate for candidate in actions if candidate.kind
                                   in ("pass", "place", "end_phase", "cancel")), actions[0])
            else:
                action = random_agent.select_action(obs, actions)
            obs = env.step(action)
    pytest.fail("Morale Boost Equip interaction did not finish a duel")
