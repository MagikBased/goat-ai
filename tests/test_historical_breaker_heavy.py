"""Breaker can destroy a Set Heavy Storm, which cannot chain as a Normal Spell."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

BREAKER = 71413901
HEAVY_STORM = 19613556


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_breaker_destroys_set_heavy_without_a_normal_spell_response(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (BREAKER, HEAVY_STORM)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    decks = []
    for name, code in (("breaker", BREAKER), ("storm", HEAVY_STORM)):
        path = tmp_path / f"{name}.ydk"
        path.write_text("#main\n" + "\n".join(map(str, (
            code, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
        decks.append(str(path))

    with GoatEnvironment(*decks, seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert BREAKER in {card.code for card in obs.hand}
        assert HEAVY_STORM in {card.code for card in env.engine.probe.observation(1).hand}
        storm_set = breaker_summoned = counter_placed = breaker_used = False
        target_chosen = response_checked = resolved = False
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(5000):
            if env.is_terminal():
                assert resolved
                path = tmp_path / "breaker_heavy.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1 and not storm_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == HEAVY_STORM), None)
                storm_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not breaker_summoned:
                assert storm_set
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == BREAKER), None)
                breaker_summoned |= action is not None
            if breaker_summoned and not counter_placed and any(
                    card.code == BREAKER and card.counters == ((1, 1),)
                    for card in obs.field):
                counter_placed = True
            if counter_placed and obs.acting_player == 0 and not breaker_used:
                action = next((a for a in actions if a.kind in ("activate", "chain")
                               and a.parameters.get("code") == BREAKER), None)
                breaker_used |= action is not None
            if breaker_used and not target_chosen and actions[0].kind == "select_card":
                assert any(card.controller == 1 and card.zone == "spell_trap"
                           and card.position == "facedown" and card.code is None
                           for card in obs.field)
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 8
                               and "code" not in a.parameters), None)
                target_chosen |= action is not None
            if target_chosen and not response_checked and obs.acting_player == 1:
                assert tuple(link.card_code for link in obs.chain) == (BREAKER,)
                assert not any(a.kind == "chain" and a.parameters.get("code") == HEAVY_STORM
                               for a in actions)
                response_checked = True
            if action is None and not resolved:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if target_chosen and response_checked and not resolved and not obs.chain \
                    and HEAVY_STORM in {card.code for card in obs.graveyards[1]}:
                breaker = next(card for card in obs.field if card.code == BREAKER)
                assert (breaker.attack, breaker.counters) == (1600, ())
                assert not any(card.zone == "spell_trap" for card in obs.field)
                assert obs.life_points == (8000, 8000)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                resolved = True
    pytest.fail("Breaker did not resolve against Set Heavy Storm")
