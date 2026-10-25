"""GOAT Mystic Tomato's optional battle recruiter and Deck-search boundary."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

TOMATO = 504700142  # GOAT variant
SANGAN = 504700178  # GOAT variant
GEMINI_ELF = 69140098


def _deck(path, cards):
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("recruit", [False, True])
def test_tomato_destroyed_in_battle_can_decline_or_recruit_sangan(tmp_path, recruit):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (TOMATO, SANGAN):
        if not (root / f"scripts/goat/c{code}.lua").is_file():
            pytest.skip(f"GOAT script for {code} not installed")
    attacker = _deck(tmp_path / "attacker.ydk", (
        *([GEMINI_ELF] * 3), *(c for c in VANILLA_DECK if c != GEMINI_ELF)))
    defender = _deck(tmp_path / "defender.ydk", (
        *([TOMATO] * 3), SANGAN, *VANILLA_DECK[4:]))
    with GoatEnvironment(attacker, defender, seed=11,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        summoned = set_tomato = battle = attacked = targeted = prompted = False
        selected = False
        deck_before = None
        for _ in range(65):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == GEMINI_ELF), None)
                summoned |= action is not None
            if observation.turn == 2 and observation.acting_player == 1 and not set_tomato:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == TOMATO), None)
                set_tomato |= action is not None
            if (observation.turn == 3 and observation.acting_player == 0
                    and observation.phase == "main1" and not battle):
                action = next((a for a in actions if a.kind == "battle_phase"), None)
                battle |= action is not None
            if (battle and observation.turn == 3 and observation.acting_player == 0
                    and observation.phase == "battle_start" and not attacked):
                action = next((a for a in actions if a.kind == "attack"
                               and a.parameters.get("code") == GEMINI_ELF), None)
                attacked |= action is not None
            if attacked and not targeted and actions[0].kind == "select_card":
                assert observation.acting_player == 0
                assert any(c.controller == 1 and c.code is None
                           and c.position == "facedown" for c in observation.field)
                targets = [a for a in actions if a.kind == "select_card"]
                assert len(targets) == 1
                assert "code" not in targets[0].parameters
                action = targets[0]
                targeted = True
            if targeted and not prompted and any(a.kind == "yes" for a in actions):
                assert observation.acting_player == observation.viewer == 1
                assert observation.phase == "damage_step"
                assert any(c.code == TOMATO for c in observation.graveyards[1])
                assert observation.life_points == (8000, 8000)
                deck_before = observation.deck_counts[1]
                action = next(a for a in actions if a.kind == ("yes" if recruit else "no"))
                prompted = True
            if recruit and prompted and not selected and actions[0].kind == "select_card":
                assert observation.acting_player == observation.viewer == 1
                assert observation.phase == "damage_step"
                assert Counter(a.parameters["code"] for a in actions) == {
                    TOMATO: 2, SANGAN: 1}
                assert all(a.parameters["location"] == 1
                           and "sequence" not in a.parameters for a in actions)
                attacker_view = env.engine.probe.observation(0)
                assert not attacker_view.private_reveals
                assert not any(c.code == SANGAN for c in attacker_view.field)
                action = next(a for a in actions if a.parameters["code"] == SANGAN)
                selected = True
            if prompted and observation.turn == 3 and observation.phase == "battle_step":
                if recruit and selected and any(c.code == SANGAN for c in observation.field):
                    assert observation.deck_counts[1] == deck_before - 1
                    assert any(c.code == SANGAN and c.controller == 1
                               and c.orientation == "attack" and c.position == "faceup"
                               for c in observation.field)
                    assert any(c.code == SANGAN for c in env.engine.probe.observation(0).field)
                    assert f"goat/c{SANGAN}.lua" in env.engine.probe.loaded_script_sha256
                    assert f"goat/c{TOMATO}.lua" in env.engine.probe.loaded_script_sha256
                    return
                if not recruit:
                    assert observation.deck_counts[1] == deck_before
                    assert not any(c.code == SANGAN for c in observation.field)
                    assert f"goat/c{TOMATO}.lua" in env.engine.probe.loaded_script_sha256
                    return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
    pytest.fail(f"Mystic Tomato battle line did not finish (recruit={recruit})")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_tomato_recruit_can_attack_in_same_battle_phase(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (TOMATO, SANGAN):
        if not (root / f"scripts/goat/c{code}.lua").is_file():
            pytest.skip(f"GOAT script for {code} not installed")
    own = _deck(tmp_path / "tomato.ydk", (
        *([TOMATO] * 3), SANGAN, *VANILLA_DECK[4:]))
    opposing = _deck(tmp_path / "gemini.ydk", (
        *([GEMINI_ELF] * 3), *(c for c in VANILLA_DECK if c != GEMINI_ELF)))
    with GoatEnvironment(own, opposing, seed=11,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        tomato = gemini = battle = attacked = accepted = selected = False
        for _ in range(65):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not tomato:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == TOMATO), None)
                tomato |= action is not None
            if observation.turn == 2 and observation.acting_player == 1 and not gemini:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == GEMINI_ELF), None)
                gemini |= action is not None
            if observation.turn == 3 and observation.acting_player == 0 \
                    and observation.phase == "main1" and not battle:
                action = next((a for a in actions if a.kind == "battle_phase"), None)
                battle |= action is not None
            if battle and observation.turn == 3 and observation.acting_player == 0 \
                    and observation.phase == "battle_start" and not attacked:
                action = next((a for a in actions if a.kind == "attack"
                               and a.parameters.get("code") == TOMATO), None)
                attacked |= action is not None
            if attacked and not accepted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == GEMINI_ELF),
                              None)
            if attacked and not accepted and any(a.kind == "yes" for a in actions):
                assert observation.life_points == (7500, 8000)
                assert any(c.code == TOMATO for c in observation.graveyards[0])
                action = next(a for a in actions if a.kind == "yes")
                accepted = True
            if accepted and not selected and actions[0].kind == "select_card":
                assert {a.parameters["code"] for a in actions} == {TOMATO, SANGAN}
                action = next(a for a in actions if a.parameters["code"] == SANGAN)
                selected = True
            if selected and observation.turn == 3 and observation.phase == "battle_step":
                assert any(c.code == SANGAN and c.controller == 0
                           and c.orientation == "attack" for c in observation.field)
                assert any(a.kind == "attack" and a.parameters.get("code") == SANGAN
                           for a in actions)
                assert any(a.kind == "main2" for a in actions)
                assert observation.life_points == (7500, 8000)
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
    pytest.fail("Tomato's recruited Sangan could not attack before Main Phase 2")
