"""Book chained to Spy's Flip Effect preserves the recruit and resets Spy."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SPY = 504700044
GUARD = 37101832
BOOK = 14087893


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_book_chained_to_spy_flip_preserves_recruit_and_reflips_next_turn(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{SPY}.lua", f"official/c{GUARD}.lua",
               f"official/c{BOOK}.lua"}
    if any(not (root / "scripts" / relative).is_file() for relative in scripts):
        pytest.skip("required card script not installed")
    owner = tmp_path / "spy.ydk"
    owner.write_text("#main\n" + "\n".join(map(str, (
        *([SPY] * 3), *([GUARD] * 3), *VANILLA_DECK[6:])))
        + "\n#extra\n!side\n")
    opponent = tmp_path / "book.ydk"
    opponent.write_text("#main\n" + "\n".join(map(str, (
        *([BOOK] * 3), *VANILLA_DECK[3:])))
        + "\n#extra\n!side\n")

    with GoatEnvironment(str(owner), str(opponent), seed=11,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert SPY in {c.code for c in obs.hand}
        assert BOOK in {c.code for c in env.engine.probe.observation(1).hand}
        spy_set = book_set = first_flip = book_chained = book_targeted = False
        first_recruit = first_checked = second_flip = second_recruit = checked = False
        agents = (RandomAgent(11), RandomAgent(12))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / "spy_book_chain.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not spy_set:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == SPY), None)
                spy_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not book_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == BOOK), None)
                book_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not first_flip:
                action = next((a for a in actions if a.kind == "flip_summon"
                               and a.parameters.get("code") == SPY), None)
                first_flip |= action is not None
            if first_flip and obs.acting_player == 1 and not book_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK), None)
                if action is not None:
                    assert [link.card_code for link in obs.chain] == [SPY]
                    book_chained = True
            if book_chained and not book_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == SPY
                               and a.parameters.get("controller") == 0), None)
                book_targeted |= action is not None
            if book_targeted and not first_recruit and action is None \
                    and actions[0].kind == "select_card":
                assert obs.acting_player == 0
                assert any(c.code == SPY and c.position == "facedown" for c in obs.field)
                action = next((a for a in actions if a.parameters.get("code") == GUARD
                               and a.parameters.get("location") == 1), None)
                first_recruit |= action is not None
            if first_recruit and not first_checked and obs.turn == 3 \
                    and not obs.chain and any(c.code == GUARD for c in obs.field):
                other = env.engine.probe.observation(1)
                hidden = next(c for c in other.field if c.controller == 0
                              and c.zone == "monster" and c.position == "facedown")
                assert hidden.code is None
                assert (0, "monster", hidden.sequence, SPY) in {
                    (c.controller, c.zone, c.sequence, c.code)
                    for c in other.known_opponent_field_cards}
                assert sum(c.code == GUARD for c in obs.field) == 1
                assert not any(a.kind == "flip_summon"
                               and a.parameters.get("code") == SPY for a in actions)
                first_checked = True
            if obs.turn == 5 and obs.acting_player == 0 and first_checked:
                if not second_flip:
                    action = next((a for a in actions if a.kind == "flip_summon"
                                   and a.parameters.get("code") == SPY), None)
                    second_flip |= action is not None
                elif not second_recruit and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == GUARD
                                   and a.parameters.get("location") == 1), None)
                    second_recruit |= action is not None
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if second_recruit and not checked \
                    and sum(c.code == GUARD for c in obs.field) == 2:
                assert first_checked and second_flip
                assert any(c.code == SPY and c.position == "faceup" for c in obs.field)
                assert obs.deck_counts[0] == 30
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail("Spy / Book chain did not finish")
