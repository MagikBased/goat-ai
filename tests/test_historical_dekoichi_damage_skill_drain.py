"""Skill Drain must already be active to stop an attacked Dekoichi's draw."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

DEKOICHI = 87621407
SKILL_DRAIN = 82732705
GEMINI_ELF = 69140098


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("activate_before_attack", [False, True])
def test_attacked_dekoichi_skill_drain_damage_step_timing(
        tmp_path, activate_before_attack):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (DEKOICHI, SKILL_DRAIN)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("Dekoichi / Skill Drain scripts not installed")
    paths = []
    for name, code in (("dekoichi", DEKOICHI), ("drain", SKILL_DRAIN)):
        path = tmp_path / f"{name}.ydk"
        path.write_text("#main\n" + "\n".join(map(str, (
            code, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
        paths.append(str(path))

    with GoatEnvironment(*paths, seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert DEKOICHI in {c.code for c in obs.hand}
        assert {SKILL_DRAIN, GEMINI_ELF} <= {
            c.code for c in env.engine.probe.observation(1).hand}
        dekoichi_set = drain_set = elf_summoned = attacked = False
        drain_activated = flip_chain_seen = checked = False
        deck_before = hand_before = None
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(5000):
            if env.is_terminal():
                assert dekoichi_set and drain_set and elf_summoned
                assert attacked and flip_chain_seen and checked
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                path = tmp_path / f"dekoichi_damage_drain_{activate_before_attack}.json"
                write_trajectory(path, env.trajectory())
                saved = read_trajectory(path)
                assert verify_trajectory(saved, ExperimentalOcgcoreEngine(root)) == len(
                    saved.decisions)
                assert audit_trajectory_visibility(saved)["decisions"] == len(
                    saved.decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not dekoichi_set:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == DEKOICHI), None)
                dekoichi_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not drain_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == SKILL_DRAIN), None)
                    drain_set |= action is not None
                elif not elf_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == GEMINI_ELF), None)
                    elf_summoned |= action is not None
            if obs.turn == 4 and obs.acting_player == 1 and not attacked:
                if activate_before_attack and not drain_activated:
                    action = next((a for a in actions if a.kind in ("activate", "chain")
                                   and a.parameters.get("code") == SKILL_DRAIN), action)
                    drain_activated |= action is not None and action.parameters.get(
                        "code") == SKILL_DRAIN
                if action is None and (not activate_before_attack or drain_activated):
                    action = next((a for a in actions if a.kind in (
                        "battle_phase", "attack") and (a.kind != "attack" or
                        a.parameters.get("code") == GEMINI_ELF)), None)
                    if action is not None and action.kind == "attack":
                        attacked = True
                        deck_before = obs.deck_counts[0]
                        hand_before = len(env.engine.probe.observation(0).hand)
            if attacked and not flip_chain_seen and any(
                    link.card_code == DEKOICHI for link in obs.chain):
                flip_chain_seen = True
                assert obs.phase.startswith("damage")
                assert not any(a.kind in ("activate", "chain") and
                               a.parameters.get("code") == SKILL_DRAIN for a in actions)
            if action is None and obs.turn < 4:
                action = next((a for a in actions if a.kind == "end_phase"), None)
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), None)
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if flip_chain_seen and not checked and not obs.chain \
                    and DEKOICHI in {c.code for c in obs.graveyards[0]}:
                own = env.engine.probe.observation(0)
                assert own.deck_counts[0] == deck_before - (0 if activate_before_attack else 1)
                assert len(own.hand) == hand_before + (0 if activate_before_attack else 1)
                assert own.life_points == (8000, 7000 if activate_before_attack else 8000)
                assert drain_activated == activate_before_attack
                checked = True
    pytest.fail("attacked Dekoichi / Skill Drain fixture did not finish")
