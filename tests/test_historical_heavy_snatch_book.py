"""Book chained to Heavy preserves control of a Snatch-stolen monster."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

HEAVY = 19613556
SNATCH = 45986603
BOOK = 14087893


def _deck(path, cards):
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_book", [False, True])
def test_book_chained_to_heavy_keeps_stolen_monster(chain_book, tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (HEAVY, SNATCH, BOOK)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card scripts not installed")
    attacker = _deck(tmp_path / "snatch_heavy.ydk", (
        SNATCH, HEAVY, *VANILLA_DECK[2:]))
    defender = _deck(tmp_path / "book.ydk", (
        BOOK, *VANILLA_DECK[1:]))

    with GoatEnvironment(attacker, defender, seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {SNATCH, HEAVY} <= {c.code for c in obs.hand}
        defender_hand = env.engine.probe.observation(1).hand
        assert BOOK in {c.code for c in defender_hand}
        monster_code = next(c.code for c in defender_hand if c.code != BOOK)
        summoned = book_set = snatch_used = snatch_targeted = stolen = False
        heavy_used = response_made = book_targeted = checked = False
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"heavy_snatch_book_{chain_book}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1:
                if not summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == monster_code), None)
                    summoned = action is not None
                elif not book_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOOK), None)
                    book_set = action is not None
            if obs.turn == 3 and obs.acting_player == 0 and book_set \
                    and not snatch_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SNATCH), None)
                snatch_used = action is not None
            if snatch_used and not snatch_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == monster_code
                               and a.parameters.get("controller") == 1), None)
                snatch_targeted = action is not None
            if obs.turn == 5 and obs.acting_player == 0 and stolen \
                    and not heavy_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == HEAVY), None)
                heavy_used = action is not None
            if heavy_used and not response_made and obs.acting_player == 1:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK), None)
                if option is not None:
                    assert [link.card_code for link in obs.chain] == [HEAVY]
                    action = option if chain_book else next(a for a in actions
                                                             if a.kind == "pass")
                    response_made = True
            if chain_book and response_made and not book_targeted \
                    and actions[0].kind == "select_card":
                assert [link.card_code for link in obs.chain] == [HEAVY, BOOK]
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == monster_code
                               and a.parameters.get("controller") == 0), None)
                book_targeted = action is not None
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if snatch_targeted and not stolen and not obs.chain:
                monster = next((c for c in obs.field if c.code == monster_code
                                and c.zone == "monster"), None)
                if monster is not None and monster.controller == 0:
                    assert any(c.code == SNATCH for c in obs.field)
                    stolen = True
            if response_made and not checked and not obs.chain and \
                    HEAVY in {c.code for c in obs.graveyards[0]}:
                own = env.engine.probe.observation(0)
                monster = next(c for c in own.field if c.code == monster_code
                               and c.zone == "monster")
                assert monster.controller == (0 if chain_book else 1)
                assert monster.position == ("facedown" if chain_book else "faceup")
                assert all(not any(c.code == code for c in own.field)
                           for code in (HEAVY, SNATCH, BOOK))
                assert SNATCH in {c.code for c in own.graveyards[0]}
                assert HEAVY in {c.code for c in own.graveyards[0]}
                assert BOOK in {c.code for c in own.graveyards[1]}
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail("Heavy / Snatch / Book duel did not complete")
