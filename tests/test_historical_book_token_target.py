"""Book of Moon offers face-up monsters but never Sheep Tokens as targets."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

BOOK = 14087893
SCAPEGOAT = 504700123
TOKENS = {73915052, 73915053, 73915054, 73915055}


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("summon_own_monster", [False, True])
def test_book_target_choices_exclude_sheep_tokens(tmp_path, summon_own_monster):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"official/c{BOOK}.lua", f"goat/c{SCAPEGOAT}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    book_deck = tmp_path / "book.ydk"
    book_deck.write_text("#main\n" + "\n".join(map(str, (
        *([BOOK] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    goat_deck = tmp_path / "goat.ydk"
    goat_deck.write_text("#main\n" + "\n".join(map(str, (
        *([SCAPEGOAT] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(book_deck), str(goat_deck), seed=11,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert BOOK in {c.code for c in obs.hand}
        assert SCAPEGOAT in {c.code for c in env.engine.probe.observation(1).hand}
        own_monster = None
        goat_set = goat_used = book_used = checked = False
        agents = (RandomAgent(11), RandomAgent(12))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"book_token_target_{summon_own_monster}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if summon_own_monster and obs.turn == 1 and obs.acting_player == 0 \
                    and own_monster is None:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") not in (BOOK, SCAPEGOAT)), None)
                if action is not None:
                    own_monster = action.parameters["code"]
            if obs.turn == 2 and obs.acting_player == 1 and not goat_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SCAPEGOAT), action)
                goat_set |= action is not None and action.kind == "set_spell_trap"
            if goat_set and obs.turn == 3 and obs.acting_player == 1 and not goat_used:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SCAPEGOAT), action)
                goat_used |= action is not None and action.kind == "chain"
            token_count = sum(c.code in TOKENS for c in obs.field)
            if goat_used and token_count == 4 and obs.acting_player == 0 \
                    and obs.phase == "main1" and not book_used and not checked:
                book_option = next((a for a in actions if a.kind == "activate"
                                    and a.parameters.get("code") == BOOK), None)
                if summon_own_monster:
                    action = book_option
                    book_used = book_option is not None
                else:
                    assert BOOK in {c.code for c in obs.hand}
                    assert not any(c.zone == "monster" and c.controller == 0
                                   for c in obs.field)
                    assert book_option is None
                    assert obs.life_points == (8000, 8000)
                    checked = True
            if book_used and not checked and actions[0].kind == "select_card":
                assert token_count == 4
                assert len(actions) == 1
                assert all(a.parameters.get("code") not in TOKENS for a in actions)
                assert all(a.parameters.get("controller") == 0 for a in actions)
                assert actions[0].parameters.get("code") == own_monster
                action = actions[0]
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if book_used and not checked and BOOK in {c.code for c in obs.graveyards[0]}:
                assert sum(c.code in TOKENS for c in obs.field) == 4
                assert any(c.controller == 0 and c.code == own_monster
                           and c.position == "facedown" for c in obs.field)
                assert obs.life_points == (8000, 8000)
                assert {f"official/c{BOOK}.lua", f"goat/c{SCAPEGOAT}.lua"} <= (
                    env.engine.probe.loaded_script_sha256.keys())
                checked = True
    pytest.fail("Book / Sheep Token target choices were not reached")
