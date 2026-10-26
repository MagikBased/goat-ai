"""Breaker cannot spend its counter until a Spell/Trap target exists."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

BREAKER = 71413901
BOOK = 14087893


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_breaker_effect_is_gated_until_opponent_sets_backrow(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (BREAKER, BOOK)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    attacker = tmp_path / "breaker.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        BREAKER, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    defender = tmp_path / "book.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        BOOK, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert BREAKER in {c.code for c in obs.hand}
        assert BOOK in {c.code for c in env.engine.probe.observation(1).hand}
        summoned = empty_gate = book_set = used = target = checked = False
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / "breaker_target_gate.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == BREAKER), None)
                summoned |= action is not None
            if summoned and not empty_gate and obs.turn == 1 \
                    and obs.phase == "main1" and obs.acting_player == 0 \
                    and not obs.chain and any(c.code == BREAKER
                                              and c.counters == ((1, 1),)
                                              for c in obs.field):
                assert not any(c.zone == "spell_trap" for c in obs.field)
                assert not any(a.kind in ("activate", "chain")
                               and a.parameters.get("code") == BREAKER for a in actions)
                empty_gate = True
            if obs.turn == 2 and obs.acting_player == 1 and not book_set:
                assert empty_gate
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == BOOK), None)
                book_set |= action is not None
            if book_set and obs.turn == 3 and obs.acting_player == 0 and not used:
                assert any(c.controller == 1 and c.zone == "spell_trap"
                           and c.position == "facedown" and c.code is None
                           for c in obs.field)
                action = next((a for a in actions if a.kind in ("activate", "chain")
                               and a.parameters.get("code") == BREAKER), None)
                used |= action is not None
            if used and not target and actions[0].kind == "select_card":
                assert all("code" not in a.parameters for a in actions)
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 8), None)
                target |= action is not None
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if target and not checked and BOOK in {c.code for c in obs.graveyards[1]}:
                breaker = next(c for c in obs.field if c.code == BREAKER)
                assert (breaker.attack, breaker.counters) == (1600, ())
                assert not any(c.zone == "spell_trap" for c in obs.field)
                assert obs.life_points == (8000, 8000)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail("Breaker target-gate duel did not finish")
