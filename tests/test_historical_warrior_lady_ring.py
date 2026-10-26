"""Ring at attack declaration prevents Warrior Lady's Damage Step choice."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

WARRIOR_LADY = 7572887
RING = 511000824
GEMINI_ELF = 69140098


def _deck(path, cards):
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("activate_ring", [False, True])
def test_ring_attack_response_prevents_warrior_lady_battle_effect(tmp_path, activate_ring):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{WARRIOR_LADY}.lua", f"pre-errata/c{RING}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("Warrior Lady or historical Ring script not installed")
    own = _deck(tmp_path / "warrior_lady.ydk", (
        WARRIOR_LADY, *VANILLA_DECK[1:]))
    others = list(VANILLA_DECK[2:])
    others[others.index(GEMINI_ELF)] = VANILLA_DECK[0]
    other = _deck(tmp_path / "elf_ring.ydk", (
        GEMINI_ELF, RING, *others))

    with GoatEnvironment(own, other, seed=103,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert WARRIOR_LADY in {c.code for c in obs.hand}
        assert {GEMINI_ELF, RING} <= {
            c.code for c in env.engine.probe.observation(1).hand}
        lady_summoned = elf_summoned = ring_set = attacked = responded = False
        ring_targeted = lady_effect = checked = False
        for _ in range(100):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not lady_summoned:
                action = next((a for a in actions if a.kind == "normal_summon" and
                               a.parameters.get("code") == WARRIOR_LADY), None)
                lady_summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not elf_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon" and
                                   a.parameters.get("code") == GEMINI_ELF), None)
                    elf_summoned |= action is not None
                elif not ring_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap" and
                                   a.parameters.get("code") == RING), None)
                    ring_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not attacked:
                if obs.phase == "main1":
                    action = next((a for a in actions if a.kind == "battle_phase"), action)
                elif obs.phase in ("battle_start", "battle_step"):
                    action = next((a for a in actions if a.kind == "attack" and
                                   a.parameters.get("code") == WARRIOR_LADY), action)
                    attacked |= action is not None and action.kind == "attack"
            if attacked and obs.acting_player == 1 and not responded:
                option = next((a for a in actions if a.kind == "chain" and
                               a.parameters.get("code") == RING), None)
                if option is not None:
                    assert obs.phase == "battle_step"
                    action = option if activate_ring else next(
                        a for a in actions if a.kind == "pass")
                    responded = True
            if activate_ring and responded and not ring_targeted and \
                    actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") ==
                               WARRIOR_LADY and a.parameters.get("controller") == 0), None)
                ring_targeted |= action is not None
            if attacked and not activate_ring and obs.phase == "damage_step":
                assert not any(a.parameters.get("code") == RING for a in actions)
                if obs.acting_player == 0 and not lady_effect:
                    action = next((a for a in actions if a.kind == "yes" and
                                   a.parameters.get("code") == WARRIOR_LADY), action)
                    lady_effect |= action is not None and action.kind == "yes"
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "main2", "end_phase")), actions[0])
            obs = env.step(action)
            own_view = env.engine.probe.observation(0)
            if activate_ring and ring_targeted and RING in {
                    c.code for c in own_view.graveyards[1]}:
                assert responded and not lady_effect
                assert own_view.life_points == (6500, 6500)
                assert WARRIOR_LADY in {c.code for c in own_view.graveyards[0]}
                assert not any(c.code == WARRIOR_LADY for c in own_view.banished[0])
                assert any(c.code == GEMINI_ELF for c in own_view.field)
                checked = True
                break
            if not activate_ring and lady_effect and obs.phase == "main2":
                assert responded and not ring_targeted
                assert own_view.life_points == (7600, 8000)
                assert WARRIOR_LADY in {c.code for c in own_view.banished[0]}
                assert GEMINI_ELF in {c.code for c in own_view.banished[1]}
                assert any(c.code == RING and c.position == "facedown"
                           for c in env.engine.probe.observation(1).field)
                assert any(c.code is None and c.position == "facedown" and
                           c.controller == 1 and c.zone == "spell_trap"
                           for c in own_view.field)
                checked = True
                break
        assert checked, "Warrior Lady / Ring battle branch did not resolve"
        assert f"official/c{WARRIOR_LADY}.lua" in env.engine.probe.loaded_script_sha256
        if activate_ring:
            assert scripts <= env.engine.probe.loaded_script_sha256.keys()

        agents = (RandomAgent(103), RandomAgent(104))
        for _ in range(5000):
            if env.is_terminal():
                break
            legal = env.legal_actions()
            obs = env.step(agents[obs.acting_player].select_action(obs, legal))
        assert env.is_terminal(), "Warrior Lady / Ring duel exceeded 5000 decisions"
        trajectory = env.trajectory()
        path = tmp_path / f"warrior_lady_ring_{activate_ring}.json"
        write_trajectory(path, trajectory)
        assert verify_trajectory(read_trajectory(path),
                                 ExperimentalOcgcoreEngine(root)) == len(trajectory.decisions)
        assert audit_trajectory_visibility(trajectory)["decisions"] == len(
            trajectory.decisions)
