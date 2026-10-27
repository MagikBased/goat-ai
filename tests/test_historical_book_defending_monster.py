"""Book on the defender changes battle position without replaying the attack."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

ARCHFIEND_SOLDIER = 49881766  # 1900 ATK
MYSTICAL_ELF = 15025844  # 800 ATK, 2000 DEF
BOOK_OF_MOON = 14087893


def _deck(path, cards):
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("use_book", [False, True])
def test_book_on_defending_monster_keeps_attack_and_uses_defense(tmp_path, use_book):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{BOOK_OF_MOON}.lua").is_file():
        pytest.skip("Book of Moon script not installed")
    attacker = _deck(tmp_path / "attacker.ydk", (
        *([ARCHFIEND_SOLDIER] * 3),
        *tuple(code for code in VANILLA_DECK if code != ARCHFIEND_SOLDIER)[:37]))
    defender = _deck(tmp_path / "defender.ydk", (
        *([MYSTICAL_ELF] * 3), *([BOOK_OF_MOON] * 3),
        *tuple(code for code in VANILLA_DECK if code != MYSTICAL_ELF)[:34]))

    with GoatEnvironment(attacker, defender, seed=11,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert ARCHFIEND_SOLDIER in {card.code for card in obs.hand}
        assert {MYSTICAL_ELF, BOOK_OF_MOON} <= {
            card.code for card in env.engine.probe.observation(1).hand}
        attacker_summoned = defender_summoned = book_set = attacked = False
        book_chained = book_targeted = damage_seen = checked = False
        agents = (RandomAgent(11), RandomAgent(12))
        for _ in range(5000):
            if env.is_terminal():
                assert attacker_summoned and defender_summoned and book_set
                assert attacked and checked
                trajectory = env.trajectory()
                path = tmp_path / f"book_defender_{use_book}.json"
                write_trajectory(path, trajectory)
                loaded = read_trajectory(path)
                assert verify_trajectory(loaded, ExperimentalOcgcoreEngine(root)) == len(
                    trajectory.decisions)
                audit_trajectory_visibility(loaded)
                if use_book:
                    assert f"official/c{BOOK_OF_MOON}.lua" in (
                        env.engine.probe.loaded_script_sha256)
                return
            actions = env.legal_actions()
            action = None
            if not checked:
                if obs.turn == 1 and obs.acting_player == 0 and not attacker_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == ARCHFIEND_SOLDIER), None)
                    attacker_summoned |= action is not None
                if obs.turn == 2 and obs.acting_player == 1:
                    if not defender_summoned:
                        action = next((a for a in actions if a.kind == "normal_summon"
                                       and a.parameters.get("code") == MYSTICAL_ELF), None)
                        defender_summoned |= action is not None
                    elif not book_set:
                        action = next((a for a in actions if a.kind == "set_spell_trap"
                                       and a.parameters.get("code") == BOOK_OF_MOON), None)
                        book_set |= action is not None
                if obs.turn == 3 and obs.acting_player == 0 and not attacked:
                    action = next((a for a in actions if a.kind == "battle_phase"), action)
                    if obs.phase == "battle_start":
                        action = next((a for a in actions if a.kind == "attack"
                                       and a.parameters.get("code") == ARCHFIEND_SOLDIER), None)
                        attacked |= action is not None
                if attacked and not damage_seen and obs.acting_player == 1 \
                        and obs.phase == "battle_step" \
                        and not book_chained:
                    book = next((a for a in actions if a.kind == "chain"
                                 and a.parameters.get("code") == BOOK_OF_MOON), None)
                    if book is not None:
                        action = book if use_book else next(a for a in actions
                                                             if a.kind == "pass")
                        book_chained = use_book
                if book_chained and not book_targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.kind == "select_card"
                                   and a.parameters.get("code") == MYSTICAL_ELF), None)
                    book_targeted |= action is not None
            if action is None:
                if checked:
                    action = agents[obs.acting_player].select_action(obs, actions)
                else:
                    action = next((a for a in actions if a.kind in (
                        "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if attacked and not damage_seen and obs.life_points != (8000, 8000):
                damage_seen = True
                assert obs.life_points == ((7900, 8000) if use_book else (8000, 6900))
            if damage_seen and not checked and obs.phase != "damage_step":
                if use_book:
                    assert book_chained and book_targeted
                    assert obs.life_points == (7900, 8000)
                    assert any(card.controller == 1 and card.code == MYSTICAL_ELF
                               and card.position == "faceup" for card in obs.field)
                    assert MYSTICAL_ELF not in {card.code for card in obs.graveyards[1]}
                    assert BOOK_OF_MOON in {card.code for card in obs.graveyards[1]}
                else:
                    assert not book_chained
                    assert obs.life_points == (8000, 6900)
                    assert MYSTICAL_ELF in {card.code for card in obs.graveyards[1]}
                assert any(card.controller == 0 and card.code == ARCHFIEND_SOLDIER
                           for card in obs.field)
                assert obs.public_history.count("attack") == 1
                checked = True
    pytest.fail("Book-of-Moon defending battle did not finish")
