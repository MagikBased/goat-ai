"""Tribe can pay a fresh cost to name another represented Type in one turn."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import verify_trajectory

TRIBE = 33184167
SCAPEGOAT = 504700123
GAGAGIGO = 49003308
SHEEP = {73915052, 73915053, 73915054, 73915055}
AQUA = 64
BEAST = 16384
REPTILE = 524288


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_tribe_can_clear_two_types_with_separate_discard_costs(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    required = {f"official/c{TRIBE}.lua", f"goat/c{SCAPEGOAT}.lua"}
    if any(not (root / "scripts" / relative).is_file() for relative in required):
        pytest.skip("required pinned scripts not installed")
    attacker = tmp_path / "tribe_twice.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        TRIBE, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    defender = tmp_path / "goats_reptile.ydk"
    defender_cards = list(VANILLA_DECK)
    defender_cards[0], defender_cards[12] = defender_cards[12], defender_cards[0]
    defender_cards[2] = SCAPEGOAT
    defender.write_text("#main\n" + "\n".join(map(str, defender_cards))
                        + "\n#extra\n!side\n")
    agent = RandomAgent(18)
    with GoatEnvironment(str(attacker), str(defender), seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert TRIBE in {card.code for card in obs.hand}
        assert {GAGAGIGO, SCAPEGOAT} <= {
            card.code for card in env.engine.probe.observation(1).hand}
        tribe_summoned = goats_summoned = reptile_summoned = False
        activations = discards = announcements = 0
        resolved_twice = False
        for _ in range(3000):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not tribe_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == TRIBE), None)
                tribe_summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not goats_summoned:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                goats_summoned |= action is not None
            if obs.turn == 4 and obs.acting_player == 1 and not reptile_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == GAGAGIGO), None)
                reptile_summoned |= action is not None
            if (obs.turn == 5 and obs.acting_player == 0 and reptile_summoned
                    and activations < 2 and action is None):
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == TRIBE), None)
                activations += action is not None
            if (activations > discards and action is None
                    and actions[0].kind == "select_card"):
                action = next((a for a in actions
                               if a.parameters.get("location") == 2), None)
                discards += action is not None
            if (discards > announcements and action is None
                    and actions[0].kind == "announce_race"):
                expected = {AQUA, BEAST, REPTILE} if announcements == 0 else {
                    AQUA, REPTILE}
                assert {a.parameters["race"] for a in actions} == expected
                wanted = BEAST if announcements == 0 else REPTILE
                action = next(a for a in actions if a.parameters["race"] == wanted)
                announcements += 1
            if action is None:
                action = (agent.select_action(obs, actions) if resolved_twice else
                          next((a for a in actions if a.kind in (
                              "place", "pass", "end_phase")), actions[0]))
            obs = env.step(action)
            if announcements == 1 and not obs.chain and obs.turn == 5:
                assert not any(card.code in SHEEP for card in obs.field)
                assert GAGAGIGO in {card.code for card in obs.field}
                assert TRIBE in {card.code for card in obs.field}
            if announcements == 2 and not obs.chain and not resolved_twice:
                assert not any(card.code in SHEEP for card in obs.field)
                assert GAGAGIGO in {card.code for card in obs.graveyards[1]}
                assert TRIBE in {card.code for card in obs.field}
                assert obs.life_points == (8000, 8000)
                assert len(obs.graveyards[0]) >= 2
                assert required <= env.engine.probe.loaded_script_sha256.keys()
                resolved_twice = True
            if env.is_terminal():
                assert all((tribe_summoned, goats_summoned, reptile_summoned,
                            activations == 2, discards == 2,
                            announcements == 2, resolved_twice))
                trajectory = env.trajectory()
                assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) \
                       == len(trajectory.decisions)
                audit_trajectory_visibility(trajectory)
                return
    pytest.fail("repeated Tribe activation did not reach a terminal duel")
