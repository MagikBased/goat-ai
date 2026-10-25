"""Torrential can answer Book in the same Normal Summon response window."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

BOOK = 14087893
TORRENTIAL = 53582587


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_torrential", [False, True])
def test_torrential_chained_to_book_after_normal_summon(tmp_path, chain_torrential):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (BOOK, TORRENTIAL)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    attacker = tmp_path / "book.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        BOOK, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    defender = tmp_path / "torrential.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        TORRENTIAL, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert BOOK in {c.code for c in obs.hand}
        assert TORRENTIAL in {c.code for c in env.engine.probe.observation(1).hand}
        summons = []
        trap_set = book_used = book_targeted = response_made = checked = False
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"book_torrential_{chain_torrential}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if not checked and obs.acting_player == 0 and obs.turn in (1, 3) \
                    and len(summons) < (1 if obs.turn == 1 else 2):
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    summons.append(action.parameters["code"])
            if not checked and obs.acting_player == 1 and obs.turn == 2 \
                    and not trap_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == TORRENTIAL), None)
                trap_set = action is not None
            if not checked and trap_set and len(summons) == 2 \
                    and obs.acting_player == 0 and not book_used:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK), action)
                book_used = action is not None and action.kind == "chain"
            if book_used and not book_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == summons[0] and a.parameters.get("controller") == 0), None)
                book_targeted = action is not None
            if book_targeted and obs.acting_player == 1 and not response_made:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == TORRENTIAL), None)
                if option is not None:
                    assert [link.card_code for link in obs.chain] == [BOOK]
                    action = option if chain_torrential else next(
                        a for a in actions if a.kind == "pass")
                    response_made = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "select_position", "pass", "end_phase")),
                              actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if response_made and chain_torrential and len(obs.chain) == 2:
                assert [link.card_code for link in obs.chain] == [BOOK, TORRENTIAL]
            if response_made and not checked and obs.turn == 3 and not obs.chain \
                    and obs.phase == "main1" and obs.acting_player == 0 \
                    and BOOK in {c.code for c in obs.graveyards[0]}:
                assert book_targeted and trap_set
                assert (TORRENTIAL in {c.code for c in obs.graveyards[1]}) \
                    == chain_torrential
                if chain_torrential:
                    assert all(code in {c.code for c in obs.graveyards[0]}
                               for code in summons)
                    assert not any(c.zone == "monster" for c in obs.field)
                else:
                    own_monsters = [c for c in obs.field if c.controller == 0
                                    and c.zone == "monster"]
                    assert len(own_monsters) == 2
                    assert any(c.code == summons[0] and c.position == "facedown"
                               for c in own_monsters)
                assert obs.life_points == (8000, 8000)
                loaded = env.engine.probe.loaded_script_sha256
                assert f"official/c{BOOK}.lua" in loaded
                if chain_torrential:
                    assert scripts <= loaded.keys()
                checked = True
    pytest.fail("Book / Torrential response did not complete")
