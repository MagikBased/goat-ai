"""Two chainable GOAT staples answer Heavy Storm in the same chain."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

HEAVY_STORM = 19613556
SCAPEGOAT = 504700123
RING_OF_DESTRUCTION = 511000824
ARCHFIEND_SOLDIER = 49881766
SHEEP_CODES = {73915052, 73915053, 73915054, 73915055}


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_scapegoat_and_ring_chained_to_heavy_storm(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"official/c{HEAVY_STORM}.lua",
                     f"goat/c{SCAPEGOAT}.lua",
                     f"pre-errata/c{RING_OF_DESTRUCTION}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    storm_deck = tmp_path / "storm.ydk"
    storm_deck.write_text("#main\n" + "\n".join(map(str, (
        HEAVY_STORM, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    response_deck = tmp_path / "response.ydk"
    response_cards = list(VANILLA_DECK)
    response_cards[0] = SCAPEGOAT
    response_cards[6] = RING_OF_DESTRUCTION
    response_deck.write_text("#main\n" + "\n".join(map(str, response_cards))
                             + "\n#extra\n!side\n")

    with GoatEnvironment(str(storm_deck), str(response_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {HEAVY_STORM, ARCHFIEND_SOLDIER} <= {c.code for c in obs.hand}
        assert {SCAPEGOAT, RING_OF_DESTRUCTION} <= {
            c.code for c in env.engine.probe.observation(1).hand}
        summoned = goat_set = ring_set = storm_used = goat_chained = False
        ring_chained = ring_targeted = False
        for _ in range(90):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == ARCHFIEND_SOLDIER), None)
                summoned = action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not goat_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == SCAPEGOAT), None)
                    goat_set = action is not None
                if goat_set and not ring_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == RING_OF_DESTRUCTION), None)
                    ring_set = action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not storm_used:
                assert summoned and goat_set and ring_set
                assert len([c for c in obs.field if c.controller == 1
                            and c.zone == "spell_trap" and c.code is None]) == 2
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == HEAVY_STORM), None)
                storm_used = action is not None
            if storm_used and obs.acting_player == 1 and not goat_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                goat_chained = action is not None
            if goat_chained and obs.acting_player == 1 and not ring_chained \
                    and action is None:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == RING_OF_DESTRUCTION), None)
                if action is not None:
                    assert [link.card_code for link in obs.chain] == [
                        HEAVY_STORM, SCAPEGOAT]
                ring_chained = action is not None
            if ring_chained and not ring_targeted and actions[0].kind == "select_card":
                assert [link.card_code for link in obs.chain] == [
                    HEAVY_STORM, SCAPEGOAT, RING_OF_DESTRUCTION]
                action = next((a for a in actions if a.parameters.get("code")
                               == ARCHFIEND_SOLDIER), None)
                ring_targeted = action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_zones", "place", "select_position", "pass", "end_phase")),
                    actions[0])
            obs = env.step(action)
            if ring_targeted and HEAVY_STORM in {c.code for c in obs.graveyards[0]}:
                assert {SCAPEGOAT, RING_OF_DESTRUCTION} <= {
                    c.code for c in obs.graveyards[1]}
                assert ARCHFIEND_SOLDIER in {c.code for c in obs.graveyards[0]}
                assert {c.code for c in obs.field if c.zone == "monster"} == SHEEP_CODES
                assert not any(c.zone == "spell_trap" for c in obs.field)
                assert obs.life_points == (6100, 6100)
                assert not obs.chain
                assert {f"official/c{HEAVY_STORM}.lua",
                        f"goat/c{SCAPEGOAT}.lua",
                        f"pre-errata/c{RING_OF_DESTRUCTION}.lua"} <= (
                            env.engine.probe.loaded_script_sha256.keys())
                break
        else:
            pytest.fail("Scapegoat and Ring did not both resolve before Heavy Storm")
        agents = (RandomAgent(1), RandomAgent(1001))
        for _ in range(3000):
            action = agents[obs.acting_player].select_action(obs, env.legal_actions())
            obs = env.step(action)
            if env.is_terminal():
                break
        else:
            pytest.fail("pro Heavy fixture exceeded 3000 decisions")
        trajectory = env.trajectory()
        assert trajectory.winner in (0, 1, None)
        assert len(trajectory.decisions) > 50
    path = tmp_path / "pro_heavy.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    assert verify_trajectory(loaded, ExperimentalOcgcoreEngine(root)) == len(
        trajectory.decisions)
