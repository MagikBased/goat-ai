"""Mirror Force and Sakuretsu are distinct legal attack responses."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

MIRROR = 44095762
SAKURETSU = 56120475


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chosen_trap", [MIRROR, SAKURETSU])
def test_both_attack_traps_are_legal_with_distinct_outcomes(tmp_path, chosen_trap):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (MIRROR, SAKURETSU)}
    if any(not (root / "scripts" / relative).is_file() for relative in scripts):
        pytest.skip("Mirror Force or Sakuretsu script not installed")
    defender = tmp_path / "defender.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        MIRROR, *([SAKURETSU] * 3), *VANILLA_DECK[4:])))
                        + "\n#extra\n!side\n")

    with GoatEnvironment("examples/decks/vanilla_probe.ydk", str(defender), seed=7,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert {MIRROR, SAKURETSU}.issubset(
            c.code for c in env.engine.probe.observation(1).hand)
        summons = 0
        mirror_set = sakuretsu_set = battle = attacked = trap_used = False
        for _ in range(85):
            actions = env.legal_actions()
            action = None
            if observation.acting_player == 0 and observation.turn in (1, 3) \
                    and summons < (1 if observation.turn == 1 else 2):
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                summons += action is not None
            if observation.turn == 2 and observation.acting_player == 1:
                if not mirror_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == MIRROR), None)
                    mirror_set |= action is not None
                if mirror_set and not sakuretsu_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == SAKURETSU), None)
                    sakuretsu_set |= action is not None
            if observation.turn == 3 and observation.acting_player == 0 \
                    and summons == 2 and not battle and action is None:
                action = next((a for a in actions if a.kind == "battle_phase"), None)
                battle |= action is not None
            if battle and observation.phase == "battle_start" \
                    and observation.acting_player == 0 and not attacked:
                action = next((a for a in actions if a.kind == "attack"), None)
                attacked |= action is not None
            if attacked and observation.acting_player == 1 and not trap_used:
                trap_options = {a.parameters.get("code"): a for a in actions
                                if a.kind == "chain" and a.parameters.get("code")
                                in (MIRROR, SAKURETSU)}
                if trap_options:
                    assert observation.phase == "battle_step"
                    assert set(trap_options) == {MIRROR, SAKURETSU}
                    assert sum(c.zone == "monster" and c.controller == 0
                               and c.position == "faceup" for c in observation.field) == 2
                    attacker = env.engine.probe.observation(0)
                    assert sum(c.zone == "spell_trap" and c.controller == 1
                               and c.position == "facedown" and c.code is None
                               for c in attacker.field) == 2
                    action = trap_options[chosen_trap]
                    trap_used = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if trap_used and chosen_trap in {
                    c.code for c in observation.graveyards[1]}:
                assert observation.chain == ()
                survivors = [c for c in observation.field
                             if c.zone == "monster" and c.controller == 0]
                destroyed = [c for c in observation.graveyards[0]
                             if c.code in VANILLA_DECK]
                assert len(survivors) == (0 if chosen_trap == MIRROR else 1)
                assert len(destroyed) == (2 if chosen_trap == MIRROR else 1)
                assert observation.life_points == (8000, 8000)
                assert f"official/c{chosen_trap}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                agents = (RandomAgent(7), RandomAgent(8))
                for _ in range(5000):
                    action = agents[observation.acting_player].select_action(
                        observation, env.legal_actions())
                    observation = env.step(action)
                    if env.is_terminal():
                        trajectory = env.trajectory()
                        path = tmp_path / f"attack_choice_{chosen_trap}.json"
                        write_trajectory(path, trajectory)
                        assert verify_trajectory(read_trajectory(path),
                                                 ExperimentalOcgcoreEngine(root)) == len(
                                                     trajectory.decisions)
                        return
                pytest.fail("attack-choice duel did not reach terminal in 5000 decisions")
    pytest.fail(f"Attack-trap choice stalled: summons={summons} "
                f"sets={mirror_set}/{sakuretsu_set} "
                f"battle={battle}/{attacked} trap={trap_used}")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("first_trap", [MIRROR, SAKURETSU])
def test_mirror_and_sakuretsu_can_share_an_attack_response_chain(tmp_path, first_trap):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (MIRROR, SAKURETSU)}
    if any(not (root / "scripts" / relative).is_file() for relative in scripts):
        pytest.skip("Mirror Force or Sakuretsu script not installed")
    defender = tmp_path / "defender.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        MIRROR, *([SAKURETSU] * 3), *VANILLA_DECK[4:])))
                        + "\n#extra\n!side\n")

    with GoatEnvironment("examples/decks/vanilla_probe.ydk", str(defender), seed=7,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        summons = 0
        mirror_set = sakuretsu_set = attacked = False
        chain_choices = []
        checked = False
        agents = (RandomAgent(7), RandomAgent(8))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"mirror_sakuretsu_chain_{first_trap}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                                             env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.acting_player == 0 and obs.turn in (1, 3) \
                    and summons < (1 if obs.turn == 1 else 2):
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                summons += action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not mirror_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == MIRROR), None)
                    mirror_set |= action is not None
                if mirror_set and not sakuretsu_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == SAKURETSU), None)
                    sakuretsu_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and summons == 2 \
                    and not attacked and action is None:
                action = next((a for a in actions if a.kind in ("battle_phase", "attack")),
                              None)
                attacked |= action is not None and action.kind == "attack"
            if attacked and not checked:
                if obs.acting_player == 1 and len(chain_choices) < 2:
                    wanted = first_trap if not chain_choices else (
                        SAKURETSU if first_trap == MIRROR else MIRROR)
                    action = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == wanted), None)
                    if action is not None:
                        assert obs.phase == "battle_step"
                        if chain_choices:
                            assert [link.card_code for link in obs.chain] == [first_trap]
                        chain_choices.append(wanted)
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if not checked and {MIRROR, SAKURETSU}.issubset(
                    {c.code for c in obs.graveyards[1]}):
                assert chain_choices == [first_trap, SAKURETSU if first_trap == MIRROR
                                          else MIRROR]
                assert not obs.chain
                assert not any(c.controller == 0 and c.zone == "monster" for c in obs.field)
                assert sum(c.code in VANILLA_DECK for c in obs.graveyards[0]) == 2
                assert obs.life_points == (8000, 8000)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail("Mirror Force / Sakuretsu response chain did not finish")
