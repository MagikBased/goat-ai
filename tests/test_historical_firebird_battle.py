"""GOAT Firebird's pinned battle callback and Winged Beast trigger."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory
from scripts.probe_random_decks import probe

FIREBIRD = 504700151
HARPIE_LADY = 76812113
MYSTICAL_ELF = 15025844
GEMINI_ELF = 69140098


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("attacker,expected_attack,expected_lp", [
    (HARPIE_LADY, 1500, 7400), (MYSTICAL_ELF, 1000, 6900),
])
def test_firebird_gains_attack_only_after_friendly_winged_beast_battle_loss(
        tmp_path, attacker, expected_attack, expected_lp):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    script = f"goat/c{FIREBIRD}.lua"
    if not (root / "scripts" / script).is_file():
        pytest.skip("GOAT Firebird script not installed")
    own = tmp_path / "firebird.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        *([FIREBIRD] * 3), *([HARPIE_LADY] * 3), *VANILLA_DECK[6:])))
        + "\n#extra\n!side\n")
    enemy = tmp_path / "gemini.ydk"
    enemy.write_text("#main\n" + "\n".join(map(str, (
        *([GEMINI_ELF] * 3),
        *(code for code in VANILLA_DECK if code != GEMINI_ELF))))
        + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(enemy), seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {FIREBIRD, attacker} <= {card.code for card in obs.hand}
        assert GEMINI_ELF in {card.code for card in env.engine.probe.observation(1).hand}
        firebird_summoned = gemini_summoned = attacker_summoned = attacked = False
        checked = False
        agents = (RandomAgent(15), RandomAgent(16))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                assert script in env.engine.probe.loaded_script_sha256
                path = tmp_path / f"firebird_{attacker}.json"
                write_trajectory(path, env.trajectory())
                replay = read_trajectory(path)
                assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(
                    replay.decisions)
                audit_trajectory_visibility(replay)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not firebird_summoned:
                action = next((choice for choice in actions
                               if choice.kind == "normal_summon"
                               and choice.parameters.get("code") == FIREBIRD), None)
                firebird_summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not gemini_summoned:
                action = next((choice for choice in actions
                               if choice.kind == "normal_summon"
                               and choice.parameters.get("code") == GEMINI_ELF), None)
                gemini_summoned |= action is not None
            if obs.turn == 3 and obs.acting_player == 0:
                if not attacker_summoned:
                    action = next((choice for choice in actions
                                   if choice.kind == "normal_summon"
                                   and choice.parameters.get("code") == attacker), None)
                    attacker_summoned |= action is not None
                elif not attacked:
                    if obs.phase == "main1":
                        action = next((choice for choice in actions
                                       if choice.kind == "battle_phase"), None)
                    elif obs.phase in ("battle_start", "battle_step"):
                        action = next((choice for choice in actions
                                       if choice.kind == "attack"
                                       and choice.parameters.get("code") == attacker), None)
                        attacked |= action is not None
            if action is None and not checked:
                action = next((choice for choice in actions if choice.kind in (
                    "place", "pass", "end_phase", "main2")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if attacked and not checked and obs.phase == "battle_step" \
                    and obs.acting_player == 0 \
                    and attacker in {card.code for card in obs.graveyards[0]}:
                firebird = next(card for card in obs.field if card.code == FIREBIRD)
                assert firebird.controller == 0
                assert firebird.attack == expected_attack
                assert obs.life_points == (expected_lp, 8000)
                assert GEMINI_ELF in {card.code for card in obs.field}
                checked = True
    pytest.fail("Firebird battle duel did not terminate")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("seed", (10030, 10062, 10122))
def test_firebird_battle_callback_completes_seeded_duel(tmp_path, seed):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    report = probe(root, tmp_path / str(seed), seed, 1, 3000,
                   distinct_opponents=True, verify_replays=True)
    game, = report["games"]
    assert game["error"] is None
    assert game["terminal"]
    assert game["replay_verified_decisions"] == game["decisions"]
    assert "scripts/goat/c504700151.lua" in report["loaded_asset_sha256"]
