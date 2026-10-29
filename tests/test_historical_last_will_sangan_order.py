"""Pre-errata Last Will and Sangan share a controller-selectable trigger time."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.ocgcore_probe import UPSTREAM_GOAT_LAST_WILL_SHA256
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

LAST_WILL = 504700147
SANGAN = 504700178
CANNON_SOLDIER = 11384280


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("first_trigger", [LAST_WILL, SANGAN])
def test_last_will_and_sangan_controller_can_order_same_time_effects(tmp_path,
                                                                    first_trigger):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if any(not (root / "scripts" / "goat" / f"c{code}.lua").is_file()
           for code in (LAST_WILL, SANGAN)):
        pytest.skip("full GOAT card script checkout not installed")
    deck = tmp_path / "last_will_sangan.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        *([LAST_WILL] * 3), SANGAN, *([CANNON_SOLDIER] * 3),
        *VANILLA_DECK[7:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert {LAST_WILL, SANGAN, CANNON_SOLDIER} <= {
            card.code for card in observation.hand}
        cannon_summoned = sangan_summoned = will_activated = tributed = False
        order_choice_seen = False
        pair_built = False
        before_deck = None
        for _ in range(70):
            actions = env.legal_actions()

            def select(kind, code=None):
                return next((action for action in actions if action.kind == kind and (
                    code is None or action.parameters.get("code") == code)), None)

            if tributed and observation.chain and {
                    link.card_code for link in observation.chain} == {LAST_WILL, SANGAN}:
                assert order_choice_seen
                assert tuple(link.card_code for link in observation.chain) == (
                    first_trigger, SANGAN if first_trigger == LAST_WILL else LAST_WILL)
                pair_built = True
            if pair_built and not observation.chain and before_deck is not None \
                    and observation.deck_counts[0] == before_deck - 2:
                break

            action = None
            if tributed and not order_choice_seen and {
                    LAST_WILL, SANGAN} <= {
                    candidate.parameters.get("code") for candidate in actions
                    if candidate.kind == "chain"}:
                order_choice_seen = True
                before_deck = observation.deck_counts[0]
                action = select("chain", first_trigger)
            if observation.turn == 1 and observation.acting_player == 0 and not cannon_summoned:
                action = select("normal_summon", CANNON_SOLDIER)
                cannon_summoned |= action is not None
            if observation.turn == 3 and observation.acting_player == 0:
                if not sangan_summoned:
                    action = select("normal_summon", SANGAN)
                    sangan_summoned |= action is not None
                if action is None and sangan_summoned and not will_activated:
                    action = select("activate", LAST_WILL)
                    will_activated |= action is not None
                if action is None and will_activated and not tributed:
                    action = select("activate", CANNON_SOLDIER)
                    tributed |= action is not None
            if action is None:
                action = (select("yes") if pair_built else None)
            if action is None:
                action = (select("select_card", SANGAN) or select("select_card")
                          or select("place")
                          or select("select_position") or select("pass")
                          or select("end_phase") or actions[0])
            observation = env.step(action)
        else:
            pytest.fail("Last Will / Sangan trigger pair did not resolve")
        assert pair_built and order_choice_seen
        assert sum(card.controller == 0 and card.zone == "monster"
                   for card in observation.field) == 2

        agents = (RandomAgent(18), RandomAgent(19))
        for _ in range(3000):
            if env.is_terminal():
                break
            observation = env.step(agents[observation.acting_player].select_action(
                observation, env.legal_actions()))
        assert env.is_terminal()
        path = tmp_path / f"last_will_sangan_{first_trigger}.json"
        write_trajectory(path, env.trajectory())
        trajectory = read_trajectory(path)
        assert trajectory.asset_sha256[
            "scripts/goat/c504700147.lua"] != UPSTREAM_GOAT_LAST_WILL_SHA256
        audit_trajectory_visibility(trajectory)
        assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) == len(
            trajectory.decisions)
