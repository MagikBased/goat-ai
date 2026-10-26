"""D.D. Assailant's mandatory battle banish versus Mirror Force removal."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

ASSAILANT = 70074904
GEMINI_ELF = 69140098
MIRROR_FORCE = 44095762


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("use_mirror", [False, True])
def test_assailant_banishes_battle_winner_only_when_destroyed_by_battle(
    tmp_path, use_mirror,
):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (ASSAILANT, MIRROR_FORCE)}
    if any(not (root / "scripts" / path).is_file() for path in scripts):
        pytest.skip("required official script not installed")
    attacker = tmp_path / "assailant.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        ASSAILANT, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    defender = tmp_path / "gemini_mirror.ydk"
    defender_cards = list(VANILLA_DECK)
    defender_cards[0], defender_cards[6] = defender_cards[6], defender_cards[0]
    defender_cards[-1] = MIRROR_FORCE
    defender.write_text("#main\n" + "\n".join(map(str, defender_cards))
                        + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert ASSAILANT in {card.code for card in obs.hand}
        assert {GEMINI_ELF, MIRROR_FORCE} <= {
            card.code for card in env.engine.probe.observation(1).hand}
        assailant_summoned = elf_summoned = mirror_set = attacked = False
        mirror_answered = checked = False
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                trajectory = env.trajectory()
                path = tmp_path / f"assailant_mirror_{use_mirror}.json"
                write_trajectory(path, trajectory)
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                                             trajectory.decisions)
                assert audit_trajectory_visibility(trajectory)["decisions"] == len(
                    trajectory.decisions)
                return
            actions = env.legal_actions()
            if attacked and not checked:
                assert not any(a.kind in ("yes", "no") and
                               a.parameters.get("code") == ASSAILANT for a in actions)
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not assailant_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == ASSAILANT), None)
                assailant_summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not elf_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == GEMINI_ELF), None)
                    elf_summoned |= action is not None
                elif not mirror_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == MIRROR_FORCE), None)
                    mirror_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and mirror_set and not attacked:
                action = next((a for a in actions if a.kind in ("battle_phase", "attack")
                               and (a.kind != "attack" or a.parameters.get("code")
                                    == ASSAILANT)), None)
                attacked |= action is not None and action.kind == "attack"
            if attacked and obs.acting_player == 1 and not mirror_answered:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == MIRROR_FORCE), None)
                if option is not None:
                    assert obs.phase == "battle_step"
                    action = option if use_mirror else next(a for a in actions
                                                             if a.kind == "pass")
                    mirror_answered = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "select_position", "pass",
                    "main2", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if mirror_answered and not checked:
                if use_mirror and MIRROR_FORCE in {c.code for c in obs.graveyards[1]}:
                    assert ASSAILANT in {c.code for c in obs.graveyards[0]}
                    assert not any(c.code == ASSAILANT for c in obs.banished[0])
                    assert GEMINI_ELF in {c.code for c in obs.field}
                    assert obs.life_points == (8000, 8000)
                    checked = True
                elif not use_mirror and ASSAILANT in {
                        c.code for c in obs.banished[0]}:
                    assert GEMINI_ELF in {c.code for c in obs.banished[1]}
                    assert not any(c.code in (ASSAILANT, GEMINI_ELF)
                                   for pile in obs.graveyards for c in pile)
                    assert obs.life_points == (7800, 8000)
                    checked = True
                if checked:
                    assert f"official/c{ASSAILANT}.lua" in \
                        env.engine.probe.loaded_script_sha256
                    if use_mirror:
                        assert scripts <= env.engine.probe.loaded_script_sha256.keys()
    pytest.fail("D.D. Assailant battle did not finish")
