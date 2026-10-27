"""An aged Skill Drain cannot be chained to an attacked Jar's Flip Effect."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

MORPHING_JAR = 33508719
SKILL_DRAIN = 82732705
GEMINI_ELF = 69140098


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
@pytest.mark.parametrize("activate_before_attack", [False, True])
def test_skill_drain_timing_when_morphing_jar_is_attacked(
        tmp_path, activate_before_attack):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (MORPHING_JAR, SKILL_DRAIN)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("Morphing Jar / Skill Drain scripts not installed")
    paths = []
    for name, code in (("jar", MORPHING_JAR), ("drain", SKILL_DRAIN)):
        path = tmp_path / f"{name}.ydk"
        path.write_text("#main\n" + "\n".join(map(str, (code, *VANILLA_DECK[1:])))
                        + "\n#extra\n!side\n")
        paths.append(str(path))

    with GoatEnvironment(*paths, seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert MORPHING_JAR in {card.code for card in obs.hand}
        assert {SKILL_DRAIN, GEMINI_ELF} <= {
            card.code for card in env.engine.probe.observation(1).hand}
        jar_set = drain_set = elf_summoned = attacked = False
        drain_activated = jar_chain_seen = checked = False
        before_hands = before_decks = None
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"jar_damage_drain_{activate_before_attack}.json"
                write_trajectory(path, env.trajectory())
                trajectory = read_trajectory(path)
                assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) == len(
                    trajectory.decisions)
                audit_trajectory_visibility(trajectory)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not jar_set:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == MORPHING_JAR), None)
                jar_set |= action is not None
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
                        other = env.engine.probe.observation(0)
                        before_hands = (len(other.hand), len(obs.hand))
                        before_decks = obs.deck_counts
            if attacked and not jar_chain_seen and any(
                    link.card_code == MORPHING_JAR for link in obs.chain):
                jar_chain_seen = True
                assert obs.phase.startswith("damage")
                assert not any(a.kind in ("activate", "chain") and
                               a.parameters.get("code") == SKILL_DRAIN for a in actions)
            if action is None and attacked:
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("controller") == 0
                               and a.parameters.get("location") == 4), None)
            if action is None and obs.turn < 4:
                action = next((a for a in actions if a.kind == "end_phase"), None)
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), None)
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if jar_chain_seen and not checked and not obs.chain \
                    and any(card.code == MORPHING_JAR
                            for card in obs.graveyards[0]):
                assert jar_set and drain_set and elf_summoned and attacked
                assert before_hands is not None and before_decks is not None
                if activate_before_attack:
                    assert drain_activated
                    assert obs.life_points == (8000, 7000)
                    assert obs.deck_counts == before_decks
                    own = env.engine.probe.observation(0)
                    other = env.engine.probe.observation(1)
                    assert (len(own.hand), len(other.hand)) == before_hands
                else:
                    assert obs.life_points == (8000, 8000)
                    assert obs.deck_counts == (before_decks[0] - 5,
                                               before_decks[1] - 5)
                    own = env.engine.probe.observation(0)
                    other = env.engine.probe.observation(1)
                    assert len(own.hand) == len(other.hand) == 5
                    assert not drain_activated
                checked = True
    pytest.fail("attacked Morphing Jar / Skill Drain fixture did not finish")
