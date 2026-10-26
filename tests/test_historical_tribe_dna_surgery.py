"""A chained DNA Surgery changes Type before Tribe resolves (2004 Q&A)."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

TRIBE = 33184167
SERPENT = 511000818
GAGAGIGO = 49003308
DNA_SURGERY = 74701381
AQUA = 64
REPTILE = 524288


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_dna", [False, True])
def test_dna_surgery_chained_after_tribe_type_declaration(tmp_path, chain_dna):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"official/c{TRIBE}.lua", f"official/c{DNA_SURGERY}.lua",
               f"pre-errata/c{SERPENT}.lua")
    if any(not (root / "scripts" / path).is_file() for path in scripts):
        pytest.skip("pinned card scripts not installed")
    attacker = tmp_path / "tribe.ydk"
    defender = tmp_path / "dna.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        TRIBE, SERPENT, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    remaining = list(VANILLA_DECK)
    for code in VANILLA_DECK[:3]:
        remaining.remove(code)
    defender.write_text("#main\n" + "\n".join(map(str, (
        DNA_SURGERY, DNA_SURGERY, DNA_SURGERY, *remaining))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {TRIBE, SERPENT} <= {card.code for card in obs.hand}
        assert {DNA_SURGERY, GAGAGIGO} <= {
            card.code for card in env.engine.probe.observation(1).hand}
        summoned = opponent_summoned = dna_set = activated = discarded = declared = False
        dna_chained = dna_declared = checked = False
        random_agents = (RandomAgent(18), RandomAgent(19))
        for _ in range(3000):
            if env.is_terminal():
                break
            actions = env.legal_actions()
            action = None
            if not checked:
                if obs.turn == 1 and obs.acting_player == 0 and not summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == TRIBE), None)
                    summoned |= action is not None
                if obs.turn == 2 and obs.acting_player == 1:
                    if not opponent_summoned:
                        action = next((a for a in actions if a.kind == "normal_summon"
                                       and a.parameters.get("code") == GAGAGIGO), None)
                        opponent_summoned |= action is not None
                    if opponent_summoned and not dna_set and action is None:
                        action = next((a for a in actions if a.kind == "set_spell_trap"
                                       and a.parameters.get("code") == DNA_SURGERY), None)
                        dna_set |= action is not None
                if obs.turn == 3 and obs.acting_player == 0 and dna_set:
                    if not activated:
                        action = next((a for a in actions if a.kind == "activate"
                                       and a.parameters.get("code") == TRIBE), None)
                        activated |= action is not None
                    elif not discarded and actions[0].kind == "select_card":
                        action = next((a for a in actions if a.parameters.get("code")
                                       == SERPENT), None)
                        discarded |= action is not None
                    elif discarded and not declared and actions[0].kind == "announce_race":
                        assert {a.parameters["race"] for a in actions} == {AQUA, REPTILE}
                        assert {(c.code, c.race) for c in obs.field
                                if c.zone == "monster"} == {
                                    (TRIBE, AQUA), (GAGAGIGO, REPTILE)}
                        action = next(a for a in actions
                                      if a.parameters["race"] == REPTILE)
                        declared = True
                if declared and obs.acting_player == 1 and not dna_chained:
                    option = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == DNA_SURGERY), None)
                    if option is not None:
                        if chain_dna:
                            action = option
                            dna_chained = True
                        else:
                            action = next(a for a in actions if a.kind == "pass")
                if (dna_chained and not dna_declared
                        and actions[0].kind == "announce_race"):
                    action = next(a for a in actions
                                  if a.parameters["race"] == AQUA)
                    dna_declared = True
            if action is None:
                action = (next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0]) if not checked else
                    random_agents[obs.acting_player].select_action(obs, actions))
            obs = env.step(action)
            if declared and not checked and not obs.chain and obs.turn == 3 \
                    and obs.phase == "main1" and obs.acting_player == 0:
                own = env.engine.probe.observation(0)
                opponent_view = env.engine.probe.observation(1)
                assert TRIBE in {c.code for c in own.field}
                assert (GAGAGIGO in {c.code for c in own.field}) == chain_dna
                assert {c.race for c in own.field if c.zone == "monster"} == {AQUA}
                assert {(c.controller, c.sequence, c.race) for c in own.field
                        if c.zone == "monster"} == {
                            (c.controller, c.sequence, c.race)
                            for c in opponent_view.field if c.zone == "monster"}
                assert (GAGAGIGO in {c.code for c in own.graveyards[1]}) != chain_dna
                assert (DNA_SURGERY in {c.code for c in own.field}) == chain_dna
                assert SERPENT in {c.code for c in own.graveyards[0]}
                assert obs.life_points == (8000, 8000)
                if chain_dna:
                    assert dna_chained and dna_declared
                checked = True
        assert checked and env.is_terminal(), "Tribe/DNA duel did not complete"
        expected_scripts = set(scripts if chain_dna else (scripts[0], scripts[2]))
        assert expected_scripts <= env.engine.probe.loaded_script_sha256.keys()
        path = tmp_path / f"tribe_dna_{chain_dna}.json"
        write_trajectory(path, env.trajectory())
    assert verify_trajectory(read_trajectory(path), ExperimentalOcgcoreEngine(root)) > 0
