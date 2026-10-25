"""Book on an attack target keeps the attack and Dekoichi's Flip Effect."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

BOOK = 14087893
DEKOICHI = 87621407
GEMINI_ELF = 69140098


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_book_sets_attack_target_without_replay_and_dekoichi_draws(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (BOOK, DEKOICHI):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    attacker = tmp_path / "attacker.ydk"
    defender = tmp_path / "defender.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, VANILLA_DECK))
                        + "\n#extra\n!side\n")
    defender.write_text("#main\n" + "\n".join(map(str, (
        DEKOICHI, BOOK, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=98,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert GEMINI_ELF in {c.code for c in obs.hand}
        assert {DEKOICHI, BOOK} <= {c.code for c in env.engine.probe.observation(1).hand}
        summoned_attacker = summoned_defender = book_set = attacked = book_used = False
        target_chosen = resolved = False
        deck_before = None
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(5000):
            if env.is_terminal():
                assert resolved
                path = tmp_path / "book_defending_dekoichi.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not summoned_attacker:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == GEMINI_ELF), None)
                summoned_attacker |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not summoned_defender:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == DEKOICHI), None)
                    summoned_defender |= action is not None
                elif not book_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOOK), None)
                    book_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and book_set and not attacked:
                action = next((a for a in actions if a.kind in ("battle_phase", "attack")
                               and (a.kind != "attack" or a.parameters.get("code")
                                    == GEMINI_ELF)), action)
                attacked |= action is not None and action.kind == "attack"
            if attacked and not target_chosen and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("code") == DEKOICHI), None)
                target_chosen |= action is not None
            if target_chosen and obs.acting_player == 1 and not book_used:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK), None)
                if action is not None:
                    assert obs.phase == "battle_step"
                    book_used = True
                    deck_before = obs.deck_counts[1]
            if book_used and actions[0].kind == "select_card" and not resolved:
                action = next((a for a in actions if a.parameters.get("code")
                               == DEKOICHI and a.parameters.get("controller") == 1), action)
            if action is None and not resolved:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "main2", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if book_used and not resolved and DEKOICHI in {
                    c.code for c in obs.graveyards[1]}:
                assert target_chosen
                assert obs.public_history.count("attack") == 1
                assert obs.deck_counts[1] == deck_before - 1
                assert obs.life_points == (8000, 8000)
                assert GEMINI_ELF in {c.code for c in obs.field}
                assert {f"official/c{BOOK}.lua", f"official/c{DEKOICHI}.lua"} <= (
                    env.engine.probe.loaded_script_sha256.keys())
                resolved = True
    pytest.fail("Book / defending Dekoichi attack did not resolve")
