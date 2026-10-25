"""Blade Knight's visible ATK bonus and conditional Flip Effect negation."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

BLADE_KNIGHT = 39507162
DEKOICHI = 87621407
BACKROW = (14087893, 60082869, 56120475, 4178474, 64697231)


def _deck(path, cards):
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_blade_knight_attack_bonus_is_visible_when_hand_reaches_one(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{BLADE_KNIGHT}.lua").is_file():
        pytest.skip("Blade Knight script not installed")
    deck = _deck(tmp_path / "blade_backrow.ydk", (
        BLADE_KNIGHT, *(code for code in BACKROW for _ in range(3)),
        *VANILLA_DECK[16:]))
    with GoatEnvironment(deck, "examples/decks/vanilla_probe.ydk", seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        summoned = False
        set_cards = 0
        for _ in range(25):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == BLADE_KNIGHT), None)
                summoned |= action is not None
            if (summoned and observation.acting_player == 0 and set_cards < 4
                    and action is None and any(c.code == BLADE_KNIGHT
                                               for c in observation.field)):
                option = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") in BACKROW), None)
                if option is not None:
                    if set_cards == 0:
                        assert len(observation.hand) == 5
                        assert any(c.code == BLADE_KNIGHT and c.attack == 1600
                                   for c in observation.field)
                    action = option
                    set_cards += 1
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if set_cards == 4 and len(observation.hand) == 1:
                knight = next(c for c in observation.field if c.code == BLADE_KNIGHT)
                assert knight.attack == 2000 and knight.defense == 1000
                opponent = env.engine.probe.observation(1)
                assert any(c.code == BLADE_KNIGHT and c.attack == 2000
                           for c in opponent.field)
                assert sum(c.controller == 0 and c.zone == "spell_trap"
                           and c.position == "facedown" and c.code is None
                           for c in opponent.field) == 4
                return
    pytest.fail("Blade Knight did not reach its one-card ATK bonus")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("ally_position", ["none", "faceup", "facedown"])
def test_blade_knight_negates_destroyed_flip_only_while_alone(tmp_path, ally_position):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (BLADE_KNIGHT, DEKOICHI):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    attacker = _deck(tmp_path / "blade.ydk", (
        *([BLADE_KNIGHT] * 3), *VANILLA_DECK[3:]))
    defender = _deck(tmp_path / "dekoichi.ydk", (
        *([DEKOICHI] * 3), *VANILLA_DECK[3:]))
    with GoatEnvironment(attacker, defender, seed=11,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        knight_summoned = dekoichi_set = ally_summoned = battle = attacked = False
        targeted = False
        before_hand = before_deck = None
        for _ in range(70):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 \
                    and not knight_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == BLADE_KNIGHT), None)
                knight_summoned |= action is not None
            if observation.turn == 2 and observation.acting_player == 1 \
                    and not dekoichi_set:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == DEKOICHI), None)
                dekoichi_set |= action is not None
            if (ally_position != "none" and observation.turn == 3
                    and observation.acting_player == 0 and not ally_summoned):
                ally_kind = "set_monster" if ally_position == "facedown" else "normal_summon"
                action = next((a for a in actions if a.kind == ally_kind
                               and a.parameters.get("code") != BLADE_KNIGHT), action)
                ally_summoned |= action is not None and action.kind == ally_kind
            if observation.turn == 3 and observation.acting_player == 0 \
                    and observation.phase == "main1" and not battle \
                    and action is None and (ally_position == "none" or (
                        ally_summoned and sum(c.controller == 0 and c.zone == "monster"
                                                for c in observation.field) == 2)):
                action = next((a for a in actions if a.kind == "battle_phase"), action)
                battle |= action is not None and action.kind == "battle_phase"
            if battle and observation.phase == "battle_start" and not attacked:
                assert len(observation.hand) > 1
                assert any(c.code == BLADE_KNIGHT and c.attack == 1600
                           for c in observation.field)
                assert sum(c.controller == 0 and c.zone == "monster"
                           for c in observation.field) == (1 if ally_position == "none" else 2)
                if ally_position == "facedown":
                    ally = next(c for c in observation.field if c.controller == 0
                                and c.zone == "monster" and c.code != BLADE_KNIGHT)
                    assert ally.position == "facedown"
                    other_view = env.engine.probe.observation(1)
                    assert any(c.controller == 0 and c.zone == "monster"
                               and c.sequence == ally.sequence and c.code is None
                               for c in other_view.field)
                before = env.engine.probe.observation(1)
                before_hand = len(before.hand)
                before_deck = before.deck_counts[1]
                action = next((a for a in actions if a.kind == "attack"
                               and a.parameters.get("code") == BLADE_KNIGHT), None)
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
                    "select_card", "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if (targeted and observation.phase == "battle_step"
                    and observation.acting_player == 0
                    and any(c.code == DEKOICHI for c in observation.graveyards[1])):
                other = env.engine.probe.observation(1)
                expected_draw = int(ally_position != "none")
                assert len(other.hand) == before_hand + expected_draw
                assert other.deck_counts[1] == before_deck - expected_draw
                assert observation.life_points == (8000, 8000)
                assert f"official/c{BLADE_KNIGHT}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail(f"Blade Knight/Dekoichi line failed (ally={ally_position})")
