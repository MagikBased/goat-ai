"""A chained Dust Tornado escapes Breaker's targeted destruction."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

BREAKER = 71413901
HEAVY_STORM = 19613556
DUST_TORNADO = 60082869


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_dust", [False, True])
def test_breaker_dust_response_changes_which_backrow_survives(tmp_path, chain_dust):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in
               (BREAKER, HEAVY_STORM, DUST_TORNADO)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")

    decks = []
    for name, replacements in (("breaker", (BREAKER, HEAVY_STORM)),
                               ("dust", (DUST_TORNADO,))):
        cards = list(VANILLA_DECK)
        cards[:len(replacements)] = replacements
        path = tmp_path / f"{name}.ydk"
        path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
        decks.append(str(path))

    with GoatEnvironment(*decks, seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {BREAKER, HEAVY_STORM} <= {card.code for card in obs.hand}
        assert DUST_TORNADO in {card.code for card in
                                env.engine.probe.observation(1).hand}
        storm_set = dust_set = breaker_summoned = breaker_used = False
        dust_targeted = responded = resolved = False
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(5000):
            if env.is_terminal():
                assert resolved, (storm_set, dust_set, breaker_summoned, breaker_used,
                                  dust_targeted, responded, obs.turn)
                path = tmp_path / f"breaker_dust_{chain_dust}.json"
                write_trajectory(path, env.trajectory())
                trajectory = read_trajectory(path)
                assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) \
                    == len(trajectory.decisions)
                audit_trajectory_visibility(trajectory)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not storm_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == HEAVY_STORM), None)
                storm_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not dust_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == DUST_TORNADO), None)
                dust_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not breaker_summoned:
                assert storm_set and dust_set
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == BREAKER), None)
                breaker_summoned |= action is not None
            if breaker_summoned and not breaker_used and obs.acting_player == 0 \
                    and action is None:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == BREAKER), None)
                breaker_used |= action is not None
            if breaker_used and not dust_targeted and actions[0].kind == "select_card":
                assert any(card.controller == 1 and card.zone == "spell_trap"
                           and card.position == "facedown" and card.code is None
                           for card in obs.field)
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 8
                               and "code" not in a.parameters), None)
                dust_targeted |= action is not None
            if dust_targeted and not responded and obs.acting_player == 1:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == DUST_TORNADO), None)
                if option is not None:
                    assert [link.card_code for link in obs.chain] == [BREAKER]
                    action = option if chain_dust else next(
                        a for a in actions if a.kind == "pass")
                    responded = True
            if responded and chain_dust and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 0
                               and a.parameters.get("location") == 8
                               and "code" not in a.parameters), None)
            if action is None and not resolved:
                action = next((a for a in actions if a.kind in
                               ("place", "pass", "end_phase", "no")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if responded and not resolved and obs.turn == 3 and obs.phase == "main1" \
                    and obs.acting_player == 0 and not obs.chain:
                breaker = next(card for card in obs.field if card.code == BREAKER)
                assert (breaker.attack, breaker.counters) == (1600, ())
                assert (HEAVY_STORM in {card.code for card in obs.graveyards[0]}) \
                    == chain_dust
                assert DUST_TORNADO in {card.code for card in obs.graveyards[1]}
                assert (HEAVY_STORM in {card.code for card in obs.field}) \
                    != chain_dust
                assert obs.life_points == (8000, 8000)
                assert {f"official/c{BREAKER}.lua", f"official/c{DUST_TORNADO}.lua"} \
                    <= env.engine.probe.loaded_script_sha256.keys()
                resolved = True
    pytest.fail("Breaker/Dust interaction did not complete")
