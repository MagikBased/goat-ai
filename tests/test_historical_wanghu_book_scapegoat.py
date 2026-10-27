"""Book turns Wanghu face-down before its Sheep Token destruction resolves."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

WANGHU = 504700143  # GOAT variant
SCAPEGOAT = 504700123  # GOAT variant
BOOK = 14087893
SHEEP_TOKENS = {73915052, 73915053, 73915054, 73915055}


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("book_response", [False, True])
def test_book_on_wanghu_preserves_new_sheep_tokens(tmp_path, book_response):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{WANGHU}.lua", f"goat/c{SCAPEGOAT}.lua",
               f"official/c{BOOK}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    wanghu_deck = tmp_path / "wanghu_book.ydk"
    wanghu_deck.write_text("#main\n" + "\n".join(map(str, (
        *([WANGHU] * 3), *([BOOK] * 3), *VANILLA_DECK[6:])))
        + "\n#extra\n!side\n")
    goat_deck = tmp_path / "scapegoat.ydk"
    goat_deck.write_text("#main\n" + "\n".join(map(str, (
        *([SCAPEGOAT] * 3), *VANILLA_DECK[3:])))
        + "\n#extra\n!side\n")

    with GoatEnvironment(str(wanghu_deck), str(goat_deck), seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {WANGHU, BOOK} <= {card.code for card in obs.hand}
        assert SCAPEGOAT in {card.code for card in env.engine.probe.observation(1).hand}
        summoned = book_set = goat_used = response_made = target_chosen = False
        checked = False
        agents = (RandomAgent(15), RandomAgent(16))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"wanghu_book_{book_response}.json"
                write_trajectory(path, env.trajectory())
                trajectory = read_trajectory(path)
                assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) \
                    == len(trajectory.decisions)
                assert audit_trajectory_visibility(trajectory)["decisions"] == len(
                    trajectory.decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == WANGHU), None)
                    summoned |= action is not None
                if summoned and not book_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOOK), None)
                    book_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not goat_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SCAPEGOAT), action)
                goat_used |= action is not None and action.kind == "activate"
            if goat_used and not response_made and obs.acting_player == 0 \
                    and any(link.card_code == WANGHU for link in obs.chain):
                book = next((a for a in actions if a.kind == "chain"
                             and a.parameters.get("code") == BOOK), None)
                if book is not None:
                    action = book if book_response else next(a for a in actions
                                                             if a.kind == "pass")
                    response_made = True
            if book_response and response_made and not target_chosen \
                    and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == WANGHU
                               and a.parameters.get("controller") == 0), None)
                target_chosen |= action is not None
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if response_made and not checked and SCAPEGOAT in {
                    card.code for card in obs.graveyards[1]} and not obs.chain:
                sheep = [card for card in obs.field if card.controller == 1
                         and card.code in SHEEP_TOKENS]
                assert len(sheep) == (4 if book_response else 0)
                own_monsters = [card for card in obs.field if card.controller == 0
                                and card.zone == "monster"]
                assert len(own_monsters) == 1
                assert own_monsters[0].position == (
                    "facedown" if book_response else "faceup")
                if book_response:
                    assert own_monsters[0].code is None
                else:
                    assert own_monsters[0].code == WANGHU
                assert (BOOK in {card.code for card in obs.graveyards[0]}) == book_response
                assert obs.life_points == (8000, 8000)
                assert scripts - {f"official/c{BOOK}.lua"} <= \
                    env.engine.probe.loaded_script_sha256.keys()
                if book_response:
                    assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail("Wanghu / Book / Scapegoat duel did not finish")
