"""Torrential timing around Gravekeeper's Spy's Flip Effect."""

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
TORRENTIAL = 53582587


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_torrential_on_spy_flip_summon_does_not_stop_recruit(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{SPY}.lua", f"official/c{GUARD}.lua",
               f"official/c{TORRENTIAL}.lua"}
    if any(not (root / "scripts" / relative).is_file() for relative in scripts):
        pytest.skip("required card script not installed")
    spy_deck = tmp_path / "spy.ydk"
    spy_deck.write_text("#main\n" + "\n".join(map(str, (
        *([SPY] * 3), *([GUARD] * 3), *VANILLA_DECK[6:])))
        + "\n#extra\n!side\n")
    trap_deck = tmp_path / "torrential.ydk"
    trap_deck.write_text("#main\n" + "\n".join(map(str, (
        TORRENTIAL, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(spy_deck), str(trap_deck), seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert SPY in {c.code for c in obs.hand}
        assert TORRENTIAL in {c.code for c in env.engine.probe.observation(1).hand}
        spy_set = trap_set = flipped = chained = recruited = checked = False
        agents = (RandomAgent(15), RandomAgent(16))
        deck_before = None
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / "spy_torrential.json"
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
            if obs.turn == 2 and obs.acting_player == 1 and not trap_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == TORRENTIAL), None)
                trap_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not flipped:
                action = next((a for a in actions if a.kind == "flip_summon"
                               and a.parameters.get("code") == SPY), None)
                if action is not None:
                    deck_before = obs.deck_counts[0]
                    flipped = True
            if flipped and obs.acting_player == 1 and not chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == TORRENTIAL), None)
                if action is not None:
                    assert [link.card_code for link in obs.chain] == [SPY]
                    chained = True
            if chained and not recruited and actions[0].kind == "select_card":
                assert obs.acting_player == 0
                assert SPY in {c.code for c in obs.graveyards[0]}
                assert not any(c.zone == "monster" for c in obs.field)
                assert any(a.parameters.get("code") == GUARD
                           and a.parameters.get("location") == 1 for a in actions)
                action = next((a for a in actions if a.parameters.get("code") == GUARD
                               and a.parameters.get("location") == 1), None)
                recruited |= action is not None
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if recruited and not checked and any(c.code == GUARD for c in obs.field):
                assert SPY in {c.code for c in obs.graveyards[0]}
                assert TORRENTIAL in {c.code for c in obs.graveyards[1]}
                assert sum(c.code == GUARD for c in obs.field) == 1
                assert obs.deck_counts[0] == deck_before - 1
                assert any(c.code == GUARD and c.position == "faceup"
                           for c in env.engine.probe.observation(1).field)
                assert obs.life_points == (8000, 8000)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail("Spy / Torrential duel did not finish")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_torrential_after_spy_recruits_destroys_both_monsters(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{SPY}.lua", f"official/c{GUARD}.lua",
               f"official/c{TORRENTIAL}.lua"}
    if any(not (root / "scripts" / relative).is_file() for relative in scripts):
        pytest.skip("required card script not installed")
    spy_deck = tmp_path / "spy.ydk"
    spy_deck.write_text("#main\n" + "\n".join(map(str, (
        *([SPY] * 3), *([GUARD] * 3), *VANILLA_DECK[6:])))
        + "\n#extra\n!side\n")
    trap_deck = tmp_path / "torrential.ydk"
    trap_deck.write_text("#main\n" + "\n".join(map(str, (
        TORRENTIAL, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(spy_deck), str(trap_deck), seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert SPY in {c.code for c in obs.hand}
        assert TORRENTIAL in {c.code for c in env.engine.probe.observation(1).hand}
        spy_set = trap_set = flipped = recruited = chained = checked = False
        deck_before = None
        agents = (RandomAgent(15), RandomAgent(16))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / "spy_torrential_late.json"
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
            if obs.turn == 2 and obs.acting_player == 1 and not trap_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == TORRENTIAL), None)
                trap_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not flipped:
                action = next((a for a in actions if a.kind == "flip_summon"
                               and a.parameters.get("code") == SPY), None)
                if action is not None:
                    deck_before = obs.deck_counts[0]
                    flipped = True
            if flipped and not recruited and obs.acting_player == 1:
                if obs.chain:
                    assert [link.card_code for link in obs.chain] == [SPY]
                    assert any(a.kind == "chain" and a.parameters.get("code") == TORRENTIAL
                               for a in actions)
                action = next(a for a in actions if a.kind == "pass")
            if flipped and not recruited and actions[0].kind == "select_card":
                assert obs.acting_player == 0
                assert SPY in {c.code for c in obs.field}
                assert any(a.parameters.get("code") == GUARD
                           and a.parameters.get("location") == 1 for a in actions)
                action = next(a for a in actions if a.parameters.get("code") == GUARD
                              and a.parameters.get("location") == 1)
                recruited = True
            if recruited and not chained and obs.acting_player == 1:
                if SPY in {c.code for c in obs.field} and GUARD in {
                        c.code for c in obs.field}:
                    assert obs.deck_counts[0] == deck_before - 1
                    assert not obs.chain
                    action = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == TORRENTIAL), None)
                    assert action is not None, "Torrential missing after Spy recruits Guard"
                    chained = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if chained and not checked and TORRENTIAL in {
                    c.code for c in obs.graveyards[1]}:
                assert SPY in {c.code for c in obs.graveyards[0]}
                assert GUARD in {c.code for c in obs.graveyards[0]}
                assert not any(c.zone == "monster" for c in obs.field)
                assert obs.life_points == (8000, 8000)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail("Spy / late Torrential duel did not finish")
