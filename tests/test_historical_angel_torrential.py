"""Shining Angel's Damage Step recruit cannot be answered by Torrential."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

ANGEL = 504700170
WARRIOR_LADY = 7572887
GEMINI_ELF = 69140098
TORRENTIAL = 53582587


def _deck(path: Path, cards: tuple[int, ...]) -> str:
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
def test_angel_recruit_cannot_trigger_set_torrential(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for script in (f"goat/c{ANGEL}.lua", f"official/c{TORRENTIAL}.lua"):
        if not (root / "scripts" / script).is_file():
            pytest.skip(f"script {script} not installed")
    angel_deck = _deck(tmp_path / "angel.ydk", (
        *([ANGEL] * 3), WARRIOR_LADY, *VANILLA_DECK[4:]))
    defender_deck = _deck(tmp_path / "defender.ydk", (
        TORRENTIAL, *([GEMINI_ELF] * 3),
        *(code for code in VANILLA_DECK if code != GEMINI_ELF)))

    with GoatEnvironment(angel_deck, defender_deck, seed=72,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert ANGEL in {card.code for card in obs.hand}
        assert {GEMINI_ELF, TORRENTIAL} <= {
            card.code for card in env.engine.probe.observation(1).hand}
        angel = gemini = torrential_set = battle = attacked = accepted = recruited = False
        damage_prompts = 0
        agents = (RandomAgent(72), RandomAgent(73))
        for _ in range(3000):
            if env.is_terminal():
                assert angel and gemini and torrential_set and battle and attacked
                assert accepted and recruited and damage_prompts > 0
                path = tmp_path / "angel_torrential.json"
                write_trajectory(path, env.trajectory())
                saved = read_trajectory(path)
                assert audit_trajectory_visibility(saved)["decisions"] == len(
                    saved.decisions)
                assert verify_trajectory(saved, ExperimentalOcgcoreEngine(root)) == len(
                    saved.decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not angel:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == ANGEL), None)
                angel |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not torrential_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == TORRENTIAL), None)
                torrential_set |= action is not None
            if (action is None and obs.turn == 2 and obs.acting_player == 1
                    and not gemini):
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == GEMINI_ELF), None)
                gemini |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and obs.phase == "main1" \
                    and not battle:
                action = next((a for a in actions if a.kind == "battle_phase"), None)
                battle |= action is not None
            if battle and obs.turn == 3 and obs.acting_player == 0 \
                    and obs.phase == "battle_start" and not attacked:
                action = next((a for a in actions if a.kind == "attack"
                               and a.parameters.get("code") == ANGEL), None)
                attacked |= action is not None
            if attacked and not accepted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == GEMINI_ELF), None)
            if attacked and not accepted and any(a.kind == "yes" for a in actions):
                assert obs.acting_player == 0 and obs.phase == "damage_step"
                action = next(a for a in actions if a.kind == "yes")
                accepted = True
            if accepted and not recruited and actions[0].kind == "select_card":
                assert obs.acting_player == 0 and obs.phase == "damage_step"
                assert all("sequence" not in a.parameters for a in actions)
                action = next(a for a in actions if a.kind == "select_card"
                              and a.parameters.get("code") == WARRIOR_LADY)
                recruited = True
            if accepted and obs.phase == "damage_step":
                if obs.acting_player == 1:
                    damage_prompts += 1
                assert not any(a.parameters.get("code") == TORRENTIAL
                               and a.kind in ("activate", "chain") for a in actions)
            if recruited and obs.turn == 3 and obs.phase == "battle_step":
                assert any(card.code == WARRIOR_LADY and card.controller == 0
                           for card in obs.field)
                defender = env.engine.probe.observation(1)
                assert any(card.code == TORRENTIAL and card.position == "facedown"
                           for card in defender.field)
            if action is None and not recruited:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
    pytest.fail("Angel/Torrential Damage Step duel did not reach terminal")
