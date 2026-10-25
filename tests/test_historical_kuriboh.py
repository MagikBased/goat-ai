"""Kuriboh discards from the defender's private hand at damage calculation."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

KURIBOH = 40640057
GEMINI_ELF = 69140098
MECHANICALCHASER = 7359741


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("use_kuriboh", [False, True])
def test_kuriboh_prevents_direct_battle_damage_when_discarded(tmp_path, use_kuriboh):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    script = f"official/c{KURIBOH}.lua"
    if not (root / "scripts" / script).is_file():
        pytest.skip("Kuriboh script not installed")
    defender = tmp_path / "kuriboh.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        KURIBOH, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment("examples/decks/vanilla_probe.ydk", str(defender),
                         seed=7, engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert GEMINI_ELF in {c.code for c in obs.hand}
        assert KURIBOH in {c.code for c in env.engine.probe.observation(1).hand}
        elf_summoned = attacked = response_seen = False
        defender_hand_before = None
        for _ in range(75):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not elf_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == GEMINI_ELF), None)
                elf_summoned |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not attacked:
                if obs.phase == "main1":
                    action = next((a for a in actions if a.kind == "battle_phase"),
                                  action)
                elif obs.phase in ("battle_start", "battle_step"):
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == GEMINI_ELF),
                                  action)
                    if action is not None and action.kind == "attack":
                        assert obs.known_opponent_hand_cards == ()
                        assert not any(c.controller == 1 and c.zone == "monster"
                                       for c in obs.field)
                        defender_hand_before = len(env.engine.probe.observation(1).hand)
                        attacked = True
            if attacked and obs.acting_player == 1 and not response_seen:
                kuriboh = next((a for a in actions if a.kind == "chain"
                                and a.parameters.get("code") == KURIBOH), None)
                if kuriboh is not None:
                    assert obs.phase == "damage_step"
                    action = kuriboh if use_kuriboh else next(
                        a for a in actions if a.kind == "pass")
                    response_seen = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "main2", "end_phase")), actions[0])
            obs = env.step(action)
            if response_seen and obs.turn == 3 and obs.phase == "battle_step" \
                    and obs.acting_player == 0 \
                    and any(a.kind == "main2" for a in env.legal_actions()):
                own_view = env.engine.probe.observation(0)
                defender_view = env.engine.probe.observation(1)
                assert own_view.life_points == (8000, 8000 if use_kuriboh else 6100)
                assert (KURIBOH in {c.code for c in own_view.graveyards[1]}) \
                    == use_kuriboh
                assert (KURIBOH in {c.code for c in defender_view.hand}) \
                    != use_kuriboh
                assert len(defender_view.hand) == (
                    defender_hand_before - int(use_kuriboh))
                assert script in env.engine.probe.loaded_script_sha256
                agents = (RandomAgent(7), RandomAgent(8))
                for _ in range(5000):
                    obs = env.step(agents[obs.acting_player].select_action(
                        obs, env.legal_actions()))
                    if env.is_terminal():
                        path = tmp_path / f"kuriboh_{use_kuriboh}.json"
                        write_trajectory(path, env.trajectory())
                        assert verify_trajectory(read_trajectory(path),
                                                 ExperimentalOcgcoreEngine(root)) == len(
                                                     env.trajectory().decisions)
                        return
                pytest.fail("Kuriboh duel did not finish")
    pytest.fail("Kuriboh direct-attack response did not resolve")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_kuriboh_prevents_damage_but_not_battle_destruction(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    script = f"official/c{KURIBOH}.lua"
    if not (root / "scripts" / script).is_file():
        pytest.skip("Kuriboh script not installed")
    defender = tmp_path / "kuriboh_monster.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        KURIBOH, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment("examples/decks/vanilla_probe.ydk", str(defender),
                         seed=7, engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert GEMINI_ELF in {c.code for c in obs.hand}
        assert {KURIBOH, MECHANICALCHASER} <= {
            c.code for c in env.engine.probe.observation(1).hand}
        elf_summoned = chaser_summoned = attacked = used = False
        target_chosen = False
        for _ in range(90):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not elf_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == GEMINI_ELF), None)
                elf_summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not chaser_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == MECHANICALCHASER), None)
                chaser_summoned |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not attacked:
                if obs.phase == "main1":
                    action = next((a for a in actions if a.kind == "battle_phase"),
                                  action)
                elif obs.phase in ("battle_start", "battle_step"):
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == GEMINI_ELF),
                                  action)
                    attacked |= action is not None and action.kind == "attack"
            if attacked and not target_chosen and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == MECHANICALCHASER and a.parameters.get("controller") == 1),
                              None)
                assert action is not None
                target_chosen = True
            if attacked and obs.acting_player == 1 and not used:
                kuriboh = next((a for a in actions if a.kind == "chain"
                                and a.parameters.get("code") == KURIBOH), None)
                if kuriboh is not None:
                    assert obs.phase == "damage_step"
                    action = kuriboh
                    used = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "main2", "end_phase")), actions[0])
            obs = env.step(action)
            if used and obs.turn == 3 and obs.phase == "battle_step" \
                    and obs.acting_player == 0 \
                    and any(a.kind == "main2" for a in env.legal_actions()):
                assert obs.life_points == (8000, 8000)
                assert KURIBOH in {c.code for c in obs.graveyards[1]}
                assert MECHANICALCHASER in {c.code for c in obs.graveyards[1]}
                assert not any(c.code == MECHANICALCHASER for c in obs.field)
                assert any(c.code == GEMINI_ELF for c in obs.field)
                assert script in env.engine.probe.loaded_script_sha256
                agents = (RandomAgent(7), RandomAgent(8))
                for _ in range(5000):
                    obs = env.step(agents[obs.acting_player].select_action(
                        obs, env.legal_actions()))
                    if env.is_terminal():
                        path = tmp_path / "kuriboh_battle.json"
                        write_trajectory(path, env.trajectory())
                        assert verify_trajectory(read_trajectory(path),
                                                 ExperimentalOcgcoreEngine(root)) == len(
                                                     env.trajectory().decisions)
                        return
                pytest.fail("Kuriboh battle duel did not finish")
    pytest.fail("Kuriboh did not preserve damage without preserving the monster")
