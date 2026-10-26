"""Book on a defending Warrior Lady changes battle damage, not her trigger."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

BOOK = 14087893
WARRIOR_LADY = 7572887
GEMINI_ELF = 69140098


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("use_book", [False, True])
def test_book_on_defending_warrior_lady_preserves_damage_step_banish(tmp_path, use_book):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (BOOK, WARRIOR_LADY)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    attacker = tmp_path / "gemini.ydk"
    attacker_cards = list(VANILLA_DECK)
    attacker_cards[0], attacker_cards[6] = attacker_cards[6], attacker_cards[0]
    attacker.write_text("#main\n" + "\n".join(map(str, attacker_cards))
                        + "\n#extra\n!side\n")
    defender = tmp_path / "warrior_book.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        WARRIOR_LADY, *VANILLA_DECK[1:-1], BOOK))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert GEMINI_ELF in {c.code for c in obs.hand}
        assert {WARRIOR_LADY, BOOK} <= {
            c.code for c in env.engine.probe.observation(1).hand}
        gemini_summoned = lady_summoned = book_set = attacked = targeted = False
        book_decided = book_used = book_targeted = effect_chosen = checked = False
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                trajectory = env.trajectory()
                path = tmp_path / f"book_warrior_lady_{use_book}.json"
                write_trajectory(path, trajectory)
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    trajectory.decisions)
                assert audit_trajectory_visibility(trajectory)["decisions"] == len(
                    trajectory.decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not gemini_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == GEMINI_ELF), None)
                gemini_summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not lady_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == WARRIOR_LADY), None)
                    lady_summoned |= action is not None
                elif not book_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOOK), None)
                    book_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and book_set and not attacked:
                action = next((a for a in actions if a.kind in ("battle_phase", "attack")
                               and (a.kind != "attack" or a.parameters.get("code")
                                    == GEMINI_ELF)), action)
                attacked |= action is not None and action.kind == "attack"
            if attacked and not targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("code") == WARRIOR_LADY), None)
                targeted |= action is not None
            if targeted and obs.acting_player == 1 and not book_decided:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK), None)
                if option is not None:
                    assert obs.phase == "battle_step"
                    assert any(c.code == WARRIOR_LADY and c.position == "faceup"
                               for c in obs.field)
                    action = option if use_book else next(
                        a for a in actions if a.kind == "pass")
                    book_decided = True
                    book_used = use_book
            if book_used and not book_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == WARRIOR_LADY and a.parameters.get("controller") == 1), None)
                book_targeted |= action is not None
            if targeted and book_decided and not effect_chosen \
                    and obs.acting_player == 1:
                option = next((a for a in actions if a.kind in ("yes", "chain")
                               and a.parameters.get("code") == WARRIOR_LADY), None)
                if option is not None:
                    assert obs.phase == "damage_step"
                    action = option
                    effect_chosen = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "main2", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if effect_chosen and not checked and WARRIOR_LADY in {
                    c.code for c in obs.banished[1]} and GEMINI_ELF in {
                        c.code for c in obs.banished[0]}:
                assert obs.public_history.count("attack") == 1
                assert obs.life_points == (8000, 8000 if use_book else 7600)
                assert not any(c.code in (WARRIOR_LADY, GEMINI_ELF) for c in obs.field)
                assert (BOOK in {c.code for c in obs.graveyards[1]}) == use_book
                loaded = env.engine.probe.loaded_script_sha256
                assert f"official/c{WARRIOR_LADY}.lua" in loaded
                if use_book:
                    assert scripts <= loaded.keys()
                checked = True
    pytest.fail("Book / Warrior Lady battle did not finish")
