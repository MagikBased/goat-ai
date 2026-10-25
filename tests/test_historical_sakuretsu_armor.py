"""Sakuretsu Armor destroys an attacker unless Book of Moon sets it first."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

SAKURETSU_ARMOR = 56120475
BOOK_OF_MOON = 14087893
DD_WARRIOR_LADY = 7572887


def _deck(path, code):
    path.write_text("#main\n" + "\n".join(map(str, (
        *([code] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("book_response", [False, True])
def test_sakuretsu_attack_response_and_book_of_moon_chain(tmp_path, book_response):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (SAKURETSU_ARMOR, BOOK_OF_MOON):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    attacker = _deck(tmp_path / "attacker.ydk", BOOK_OF_MOON)
    defender = _deck(tmp_path / "defender.ydk", SAKURETSU_ARMOR)
    with GoatEnvironment(attacker, defender, seed=11,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        summoned = set_trap = battle = attacked = chained_trap = chained_book = False
        attacker_code = None
        for _ in range(65):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    attacker_code = action.parameters["code"]
                    summoned = True
            if observation.turn == 2 and observation.acting_player == 1 and not set_trap:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SAKURETSU_ARMOR), None)
                set_trap |= action is not None
            if observation.turn == 3 and observation.acting_player == 0 \
                    and observation.phase == "main1" and not battle:
                action = next((a for a in actions if a.kind == "battle_phase"), None)
                battle |= action is not None
            if battle and observation.turn == 3 and observation.acting_player == 0 \
                    and observation.phase == "battle_start" and not attacked:
                action = next((a for a in actions if a.kind == "attack"
                               and a.parameters.get("code") == attacker_code), None)
                attacked |= action is not None
            if attacked and observation.acting_player == 1 and not chained_trap:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SAKURETSU_ARMOR), None)
                if action is not None:
                    assert observation.phase == "battle_step"
                    other = env.engine.probe.observation(0)
                    assert any(c.controller == 1 and c.zone == "spell_trap"
                               and c.position == "facedown" and c.code is None
                               for c in other.field)
                    chained_trap = True
            if chained_trap and observation.acting_player == 0 and book_response \
                    and not chained_book:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK_OF_MOON), None)
                chained_book |= action is not None
            if chained_book and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == attacker_code), None)
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if chained_trap and any(c.code == SAKURETSU_ARMOR
                                    for c in observation.graveyards[1]):
                own_monsters = [c for c in observation.field
                                if c.controller == 0 and c.zone == "monster"]
                if book_response:
                    assert chained_book
                    assert len(own_monsters) == 1
                    assert own_monsters[0].code == attacker_code
                    assert own_monsters[0].position == "facedown"
                    other = env.engine.probe.observation(1)
                    assert any(c.controller == 0 and c.code is None
                               and c.position == "facedown" for c in other.field)
                    assert any(c.controller == 0 and c.code == attacker_code
                               for c in other.known_opponent_field_cards)
                    assert BOOK_OF_MOON in {c.code for c in observation.graveyards[0]}
                else:
                    assert not own_monsters
                    assert attacker_code in {c.code for c in observation.graveyards[0]}
                assert observation.life_points == (8000, 8000)
                assert f"official/c{SAKURETSU_ARMOR}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail(f"Sakuretsu response did not resolve (book={book_response})")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_sakuretsu_stops_warrior_lady_before_damage_step_banish(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (SAKURETSU_ARMOR, DD_WARRIOR_LADY):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    attacker = tmp_path / "warrior_lady.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        DD_WARRIOR_LADY, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    defender = _deck(tmp_path / "sakuretsu.ydk", SAKURETSU_ARMOR)

    with GoatEnvironment(str(attacker), defender, seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert DD_WARRIOR_LADY in {c.code for c in obs.hand}
        summoned = trap_set = battle = attacked = trap_used = False
        for _ in range(70):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == DD_WARRIOR_LADY), None)
                summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not trap_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SAKURETSU_ARMOR), None)
                trap_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and obs.phase == "main1" \
                    and not battle:
                action = next((a for a in actions if a.kind == "battle_phase"), None)
                battle |= action is not None
            if battle and obs.turn == 3 and obs.acting_player == 0 \
                    and obs.phase == "battle_start" and not attacked:
                action = next((a for a in actions if a.kind == "attack"
                               and a.parameters.get("code") == DD_WARRIOR_LADY), None)
                attacked |= action is not None
            if attacked and obs.acting_player == 1 and not trap_used:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SAKURETSU_ARMOR), None)
                if action is not None:
                    assert obs.phase == "battle_step"
                    trap_used = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "main2", "end_phase")), actions[0])
            obs = env.step(action)
            if trap_used and SAKURETSU_ARMOR in {c.code for c in obs.graveyards[1]}:
                assert DD_WARRIOR_LADY in {c.code for c in obs.graveyards[0]}
                assert not any(c.code == DD_WARRIOR_LADY for c in obs.field)
                assert not any(c.code == DD_WARRIOR_LADY for pile in obs.banished
                               for c in pile)
                assert not any(a.parameters.get("code") == DD_WARRIOR_LADY
                               and a.kind in ("yes", "chain") for a in env.legal_actions())
                assert obs.life_points == (8000, 8000)
                assert {f"official/c{code}.lua" for code in (
                    SAKURETSU_ARMOR, DD_WARRIOR_LADY)}.issubset(
                        env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Sakuretsu did not stop Warrior Lady before damage calculation")
