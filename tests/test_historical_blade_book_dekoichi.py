"""Book on an attacking Blade stops battle before Set Dekoichi flips."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

BLADE = 39507162
BOOK = 14087893
DEKOICHI = 87621407


def _deck(path, cards):
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("use_book", [False, True])
def test_book_stops_blade_attack_before_dekoichi_flips(tmp_path, use_book):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (BLADE, BOOK, DEKOICHI)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card scripts not installed")
    attacker = _deck(tmp_path / "blade.ydk", (
        *([BLADE] * 3), *VANILLA_DECK[3:]))
    defender = _deck(tmp_path / "defender.ydk", (
        DEKOICHI, BOOK, *VANILLA_DECK[2:]))

    with GoatEnvironment(attacker, defender, seed=72,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert BLADE in {c.code for c in obs.hand}
        assert {DEKOICHI, BOOK} <= {c.code for c in
                                    env.engine.probe.observation(1).hand}
        blade_summoned = dekoichi_set = book_set = attacked = target_chosen = False
        response_seen = book_targeted = checked = False
        deck_before = None
        agents = (RandomAgent(72), RandomAgent(73))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"blade_book_dekoichi_{use_book}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not blade_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == BLADE), None)
                blade_summoned = action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not dekoichi_set:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == DEKOICHI), None)
                    dekoichi_set = action is not None
                elif not book_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOOK), None)
                    book_set = action is not None
            if obs.turn == 3 and obs.acting_player == 0 and book_set and not attacked:
                action = next((a for a in actions if a.kind in ("battle_phase", "attack")
                               and (a.kind != "attack" or a.parameters.get("code")
                                    == BLADE)), action)
                attacked = action is not None and action.kind == "attack"
            if attacked and not target_chosen and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 4
                               and "code" not in a.parameters), None)
                if action is not None:
                    deck_before = obs.deck_counts[1]
                    target_chosen = True
            if target_chosen and obs.acting_player == 1 and not response_seen:
                book = next((a for a in actions if a.kind == "chain"
                             and a.parameters.get("code") == BOOK), None)
                if book is not None:
                    assert obs.phase == "battle_step"
                    action = book if use_book else next(
                        a for a in actions if a.kind == "pass")
                    response_seen = True
            if use_book and response_seen and not book_targeted \
                    and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 0
                               and a.parameters.get("code") == BLADE), None)
                book_targeted = action is not None
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "main2", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if response_seen and not checked and (
                    use_book and BOOK in {c.code for c in obs.graveyards[1]}
                    or not use_book and DEKOICHI in {c.code for c in obs.graveyards[1]}):
                assert obs.deck_counts[1] == deck_before
                assert obs.life_points == (8000, 8000)
                assert obs.public_history.count("attack") == 1
                if use_book:
                    assert book_targeted
                    assert DEKOICHI not in {c.code for c in obs.graveyards[1]}
                    assert any(c.code == DEKOICHI and c.position == "facedown"
                               for c in env.engine.probe.observation(1).field)
                    assert any(c.code == BLADE and c.position == "facedown"
                               for c in obs.field)
                    hidden = [c for c in env.engine.probe.observation(1).field
                              if c.controller == 0 and c.zone == "monster"]
                    assert len(hidden) == 1 and hidden[0].code is None
                else:
                    assert not book_targeted
                    assert any(c.code == BLADE and c.position == "faceup"
                               for c in obs.field)
                    assert any(c.code == BOOK for c in
                               env.engine.probe.observation(1).field)
                assert {f"official/c{BLADE}.lua",
                        f"official/c{DEKOICHI}.lua"} <= (
                            env.engine.probe.loaded_script_sha256.keys())
                checked = True
    pytest.fail("Blade / Book / Dekoichi battle did not finish")
