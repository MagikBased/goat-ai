"""GOAT Apprentice Magician's battle recruiter and revealed facedown identity."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

APPRENTICE = 504700013  # GOAT variant
FAITH = 31560081
OLD_VINDICTIVE = 45141844
GEMINI_ELF = 69140098


def _deck(path, cards):
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("recruit", [False, True])
def test_apprentice_battle_recruits_revealed_facedown_spellcaster(tmp_path, recruit):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/goat/c{APPRENTICE}.lua").is_file():
        pytest.skip("GOAT Apprentice script not installed")
    attacker = _deck(tmp_path / "attacker.ydk", (
        *([GEMINI_ELF] * 3), *(c for c in VANILLA_DECK if c != GEMINI_ELF)))
    defender = _deck(tmp_path / "defender.ydk", (
        *([APPRENTICE] * 3), *([FAITH] * 3), *([OLD_VINDICTIVE] * 3),
        *VANILLA_DECK[9:]))
    with GoatEnvironment(attacker, defender, seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        summoned = set_apprentice = battle = attacked = targeted = prompted = False
        selected = False
        deck_before = None
        for _ in range(70):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == GEMINI_ELF), None)
                summoned |= action is not None
            if observation.turn == 2 and observation.acting_player == 1 and not set_apprentice:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == APPRENTICE), None)
                set_apprentice |= action is not None
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
                assert any(c.controller == 1 and c.code is None
                           and c.position == "facedown" for c in observation.field)
                targets = [a for a in actions if a.kind == "select_card"]
                assert len(targets) == 1 and "code" not in targets[0].parameters
                action = targets[0]
                targeted = True
            if targeted and not prompted and any(a.kind == "yes" for a in actions):
                assert observation.acting_player == observation.viewer == 1
                assert observation.phase == "damage_step"
                assert observation.life_points == (8000, 8000)
                deck_before = observation.deck_counts[1]
                action = next(a for a in actions if a.kind == ("yes" if recruit else "no"))
                prompted = True
            if recruit and prompted and not selected and actions[0].kind == "select_card":
                assert Counter(a.parameters["code"] for a in actions) == {
                    APPRENTICE: 1, FAITH: 3, OLD_VINDICTIVE: 2}
                assert all(a.parameters["location"] == 1
                           and "sequence" not in a.parameters for a in actions)
                other = env.engine.probe.observation(0)
                assert not other.private_reveals
                assert not other.known_opponent_field_cards
                action = next(a for a in actions if a.parameters["code"] == FAITH)
                selected = True
            if recruit and selected and observation.acting_player == 1 \
                    and observation.phase == "damage_step" \
                    and any(c.code == FAITH and c.position == "facedown"
                            for c in observation.field):
                other = env.engine.probe.observation(0)
                recruited = [c for c in other.field if c.controller == 1
                             and c.position == "facedown" and c.sequence == 1]
                assert len(recruited) == 1 and recruited[0].code is None
                assert {(c.controller, c.zone, c.sequence, c.code)
                        for c in other.known_opponent_field_cards} == {
                            (1, "monster", 1, FAITH)}
                assert any(reveal.recipient == 0 and any(card.code == FAITH
                           for card in reveal.cards) for reveal in other.private_reveals)
                assert not observation.private_reveals
                assert observation.deck_counts[1] == deck_before - 1
                assert f"goat/c{APPRENTICE}.lua" in env.engine.probe.loaded_script_sha256
                return
            if prompted and not recruit and observation.phase == "battle_step":
                assert observation.deck_counts[1] == deck_before
                assert f"goat/c{APPRENTICE}.lua" in env.engine.probe.loaded_script_sha256
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
    pytest.fail(f"Apprentice battle line did not finish (recruit={recruit})")
