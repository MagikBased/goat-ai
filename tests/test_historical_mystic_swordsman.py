"""GOAT Mystic Swordsman LV2 destroys a set Flip monster before it flips."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

MYSTIC_SWORDSMAN = 504700077
DEKOICHI = 87621407


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_swordsman_destroys_set_dekoichi_without_flip_or_battle_damage(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{MYSTIC_SWORDSMAN}.lua", f"official/c{DEKOICHI}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    attacker = tmp_path / "swordsman.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        *([MYSTIC_SWORDSMAN] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    defender = tmp_path / "dekoichi.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        *([DEKOICHI] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=11,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        swordsman_summoned = dekoichi_set = battle = attacked = targeted = False
        destroyed = False
        defender_hand = defender_deck = None
        for _ in range(65):
            actions = env.legal_actions()
            if destroyed:
                assert not any(a.kind in ("yes", "chain")
                               and a.parameters.get("code") == MYSTIC_SWORDSMAN
                               for a in actions)
                if observation.turn >= 4:
                    return
            action = None
            if observation.turn == 1 and observation.acting_player == 0 \
                    and not swordsman_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == MYSTIC_SWORDSMAN), None)
                swordsman_summoned |= action is not None
            if observation.turn == 2 and observation.acting_player == 1 \
                    and not dekoichi_set:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == DEKOICHI), None)
                dekoichi_set |= action is not None
            if (observation.turn == 3 and observation.acting_player == 0
                    and observation.phase == "main1" and not battle):
                action = next((a for a in actions if a.kind == "battle_phase"), None)
                battle |= action is not None
            if battle and observation.turn == 3 and observation.acting_player == 0 \
                    and observation.phase == "battle_start" and not attacked:
                other = env.engine.probe.observation(1)
                defender_hand = len(other.hand)
                defender_deck = other.deck_counts[1]
                assert any(c.controller == 1 and c.zone == "monster"
                           and c.position == "facedown" and c.code is None
                           for c in observation.field)
                action = next((a for a in actions if a.kind == "attack"
                               and a.parameters.get("code") == MYSTIC_SWORDSMAN), None)
                attacked |= action is not None
            if attacked and not targeted and actions[0].kind == "select_card":
                targets = [a for a in actions if a.kind == "select_card"
                           and a.parameters.get("controller") == 1
                           and a.parameters.get("location") == 4]
                assert len(targets) == 1 and "code" not in targets[0].parameters
                action = targets[0]
                targeted = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "select_position", "pass", "end_phase")),
                    actions[0])
            observation = env.step(action)
            if targeted and not destroyed and any(
                    c.code == DEKOICHI for c in observation.graveyards[1]):
                other = env.engine.probe.observation(1)
                assert len(other.hand) == defender_hand
                assert other.deck_counts[1] == defender_deck
                assert observation.life_points == (8000, 8000)
                assert not any(c.controller == 1 and c.zone == "monster"
                               for c in observation.field)
                assert any(c.code == MYSTIC_SWORDSMAN and c.controller == 0
                           for c in observation.field)
                assert f"goat/c{MYSTIC_SWORDSMAN}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                destroyed = True
    pytest.fail("Swordsman did not finish the no-level-up attack line")
