"""GOAT Shining Angel recruitment and the Deck-search information boundary."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

ANGEL = 504700170  # pinned GOAT variant
WARRIOR_LADY = 7572887
GEMINI_ELF = 69140098


def _deck(path, cards):
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("recruit", [False, True])
def test_angel_battle_recruitment_and_hidden_deck_boundary(tmp_path, recruit):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{ANGEL}.lua", f"official/c{WARRIOR_LADY}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    attacker = _deck(tmp_path / "attacker.ydk", (
        *([GEMINI_ELF] * 3), *(c for c in VANILLA_DECK if c != GEMINI_ELF)))
    defender = _deck(tmp_path / "defender.ydk", (
        *([ANGEL] * 3), WARRIOR_LADY, *VANILLA_DECK[4:]))
    with GoatEnvironment(attacker, defender, seed=11,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        summoned = set_angel = battle = attacked = targeted = prompted = selected = False
        deck_before = None
        for _ in range(65):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == GEMINI_ELF), None)
                summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not set_angel:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == ANGEL), None)
                set_angel |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 \
                    and obs.phase == "main1" and not battle:
                action = next((a for a in actions if a.kind == "battle_phase"), None)
                battle |= action is not None
            if battle and obs.turn == 3 and obs.acting_player == 0 \
                    and obs.phase == "battle_start" and not attacked:
                action = next((a for a in actions if a.kind == "attack"
                               and a.parameters.get("code") == GEMINI_ELF), None)
                attacked |= action is not None
            if attacked and not targeted and actions[0].kind == "select_card":
                assert obs.acting_player == 0
                assert any(c.controller == 1 and c.code is None
                           and c.position == "facedown" for c in obs.field)
                targets = [a for a in actions if a.kind == "select_card"]
                assert len(targets) == 1
                assert "code" not in targets[0].parameters
                action = targets[0]
                targeted = True
            if targeted and not prompted and any(a.kind == "yes" for a in actions):
                assert obs.acting_player == obs.viewer == 1
                assert obs.phase == "damage_step"
                assert any(c.code == ANGEL for c in obs.graveyards[1])
                assert obs.life_points == (8000, 8000)
                deck_before = obs.deck_counts[1]
                action = next(a for a in actions if a.kind == ("yes" if recruit else "no"))
                prompted = True
            if recruit and prompted and not selected and actions[0].kind == "select_card":
                assert obs.acting_player == obs.viewer == 1
                assert obs.phase == "damage_step"
                assert Counter(a.parameters["code"] for a in actions) == {
                    ANGEL: 2, WARRIOR_LADY: 1, 15025844: 2}
                assert all(a.parameters["location"] == 1
                           and "sequence" not in a.parameters for a in actions)
                attacker_view = env.engine.probe.observation(0)
                assert not attacker_view.private_reveals
                assert not any(c.code == WARRIOR_LADY for c in attacker_view.field)
                action = next(a for a in actions if a.parameters["code"] == WARRIOR_LADY)
                selected = True
            if prompted and obs.turn == 3 and obs.phase == "battle_step":
                if recruit and selected and any(c.code == WARRIOR_LADY for c in obs.field):
                    assert obs.deck_counts[1] == deck_before - 1
                    assert any(c.code == WARRIOR_LADY and c.controller == 1
                               and c.orientation == "attack" and c.position == "faceup"
                               for c in obs.field)
                    assert any(c.code == WARRIOR_LADY
                               for c in env.engine.probe.observation(0).field)
                    assert f"goat/c{ANGEL}.lua" in env.engine.probe.loaded_script_sha256
                    return
                if not recruit:
                    assert obs.deck_counts[1] == deck_before
                    assert not any(c.code == WARRIOR_LADY for c in obs.field)
                    assert f"goat/c{ANGEL}.lua" in env.engine.probe.loaded_script_sha256
                    return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
    pytest.fail(f"Shining Angel battle line did not finish (recruit={recruit})")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_angel_recruit_can_attack_in_same_battle_phase(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{ANGEL}.lua", f"official/c{WARRIOR_LADY}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    own = _deck(tmp_path / "angel.ydk", (
        *([ANGEL] * 3), WARRIOR_LADY, *VANILLA_DECK[4:]))
    opposing = _deck(tmp_path / "gemini.ydk", (
        *([GEMINI_ELF] * 3), *(c for c in VANILLA_DECK if c != GEMINI_ELF)))
    with GoatEnvironment(own, opposing, seed=11,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        angel = gemini = battle = attacked = accepted = selected = False
        for _ in range(65):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not angel:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == ANGEL), None)
                angel |= action is not None
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
                               and a.parameters.get("code") == ANGEL), None)
                attacked |= action is not None
            if attacked and not accepted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == GEMINI_ELF),
                              None)
            if attacked and not accepted and any(a.kind == "yes" for a in actions):
                assert observation.life_points == (7500, 8000)
                assert any(c.code == ANGEL for c in observation.graveyards[0])
                action = next(a for a in actions if a.kind == "yes")
                accepted = True
            if accepted and not selected and actions[0].kind == "select_card":
                assert {a.parameters["code"] for a in actions} == {ANGEL, WARRIOR_LADY, 15025844}
                action = next(a for a in actions if a.parameters["code"] == WARRIOR_LADY)
                selected = True
            if selected and observation.turn == 3 and observation.phase == "battle_step":
                assert any(c.code == WARRIOR_LADY and c.controller == 0
                           and c.orientation == "attack" for c in observation.field)
                assert any(a.kind == "attack" and a.parameters.get("code") == WARRIOR_LADY
                           for a in actions)
                assert any(a.kind == "main2" for a in actions)
                assert observation.life_points == (7500, 8000)
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
    pytest.fail("Shining Angel's recruited Warrior Lady could not attack before Main Phase 2")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_angel_empty_search_verifies_deck_only_to_opponent(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/goat/c{ANGEL}.lua").is_file():
        pytest.skip("GOAT Shining Angel script not installed")
    # Remove the fixture's other eligible LIGHT monsters; keep the Angel as
    # the only target and use legal unrestricted Spells/Traps for 40 cards.
    book = 14087893
    sakuretsu = 56120475
    remaining = [c for c in VANILLA_DECK if c not in (15025844, 62651957)]
    defender = _deck(tmp_path / "only_angel.ydk", (
        ANGEL, *remaining, *([book] * 3), *([sakuretsu] * 2)))
    attacker = _deck(tmp_path / "gemini.ydk", (
        *([GEMINI_ELF] * 3), *(c for c in VANILLA_DECK if c != GEMINI_ELF)))
    with GoatEnvironment(attacker, defender, seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert ANGEL in {c.code for c in env.engine.probe.observation(1).hand}
        gemini = set_angel = battle = attacked = target = accepted = False
        deck_before = None
        for _ in range(65):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not gemini:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == GEMINI_ELF), None)
                gemini |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not set_angel:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == ANGEL), None)
                set_angel |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 \
                    and obs.phase == "main1" and not battle:
                action = next((a for a in actions if a.kind == "battle_phase"), None)
                battle |= action is not None
            if battle and obs.turn == 3 and obs.acting_player == 0 \
                    and obs.phase == "battle_start" and not attacked:
                action = next((a for a in actions if a.kind == "attack"
                               and a.parameters.get("code") == GEMINI_ELF), None)
                attacked |= action is not None
            if attacked and not target and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 1),
                              None)
                assert action is not None and "code" not in action.parameters
                target = True
            if target and not accepted and any(a.kind == "yes" for a in actions):
                assert obs.acting_player == obs.viewer == 1
                assert obs.phase == "damage_step"
                deck_before = obs.deck_counts[1]
                action = next(a for a in actions if a.kind == "yes")
                accepted = True
            if accepted:
                owner = env.engine.probe.observation(1)
                opponent = env.engine.probe.observation(0)
                if opponent.private_reveals:
                    assert not owner.private_reveals
                    assert not any(a.kind == "select_card" for a in actions)
                    assert owner.deck_counts[1] == deck_before
                    assert not any(c.controller == 1 for c in owner.field)
                    reveal = opponent.private_reveals[0]
                    assert reveal.recipient == 0 and reveal.turn == 3
                    assert len(reveal.cards) == deck_before
                    assert all(c.controller == 1 and c.location == 1
                               for c in reveal.cards)
                    assert Counter(c.code for c in reveal.cards) == Counter(
                        c.code for c in env.engine.probe._query_location(1, 1))
                    assert f"goat/c{ANGEL}.lua" in env.engine.probe.loaded_script_sha256
                    return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
    pytest.fail("Shining Angel's empty search did not verify the Deck")
