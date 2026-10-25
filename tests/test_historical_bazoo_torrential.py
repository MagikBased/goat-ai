"""Bazoo may pay its banish cost before Torrential destroys it."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

BAZOO = 40133511
GRACEFUL = 79571449
RETURN = 27174286
TORRENTIAL = 53582587
FIRST = 62651957
SECOND = 97590747


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("use_priority", [False, True])
def test_bazoo_priority_cost_before_torrential(tmp_path, use_priority):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (BAZOO, GRACEFUL, TORRENTIAL)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card scripts not installed")
    attacker = tmp_path / "bazoo.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL, *([BAZOO] * 3), *([RETURN] * 3), *VANILLA_DECK[7:])))
        + "\n#extra\n!side\n")
    defender_cards = list(VANILLA_DECK)
    defender_cards[3] = TORRENTIAL
    defender = tmp_path / "torrential.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, defender_cards))
                        + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, BAZOO, FIRST, SECOND} <= {c.code for c in obs.hand}
        assert TORRENTIAL in {c.code for c in env.engine.probe.observation(1).hand}
        graceful = discarded = trap_set = summoned = priority_seen = False
        effect_used = cost_paid = torrential_used = False
        for _ in range(110):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    graceful |= action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"] for c in
                                   a.parameters["cards"]} == {FIRST, SECOND}), None)
                    discarded |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not trap_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == TORRENTIAL), None)
                trap_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and trap_set:
                if not summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == BAZOO), None)
                    summoned |= action is not None
                if summoned and not priority_seen:
                    option = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == BAZOO), None)
                    if option is not None:
                        assert obs.chain == ()
                        assert any(c.code == BAZOO and c.attack == 1600
                                   for c in obs.field)
                        assert {FIRST, SECOND} <= {c.code for c in obs.graveyards[0]}
                        assert any(c.controller == 1 and c.zone == "spell_trap"
                                   and c.position == "facedown" and c.code is None
                                   for c in obs.field)
                        action = option if use_priority else next(
                            a for a in actions if a.kind == "pass")
                        priority_seen = True
                        effect_used = use_priority
                if effect_used and not cost_paid:
                    action = next((a for a in actions if {c["code"] for c in
                                   a.parameters.get("cards", ())} == {FIRST, SECOND}),
                                  action)
                    cost_paid |= action is not None and action.kind == "select_cards"
            if priority_seen and obs.acting_player == 1 and not torrential_used:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == TORRENTIAL), None)
                if option is not None:
                    assert (len(obs.chain) == 1) == use_priority
                    if use_priority:
                        assert obs.chain[0].card_code == BAZOO
                        assert {FIRST, SECOND} <= {c.code for c in obs.banished[0]}
                    action = option
                    torrential_used = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if torrential_used and TORRENTIAL in {c.code for c in obs.graveyards[1]}:
                assert priority_seen and trap_set and summoned
                assert effect_used == cost_paid == use_priority
                assert obs.chain == ()
                assert BAZOO in {c.code for c in obs.graveyards[0]}
                assert not any(c.code == BAZOO for c in obs.field)
                assert {FIRST, SECOND} <= {c.code for c in (
                    obs.banished[0] if use_priority else obs.graveyards[0])}
                assert not any(c.code in {FIRST, SECOND} for c in (
                    obs.graveyards[0] if use_priority else obs.banished[0]))
                assert obs.life_points == (8000, 8000)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                agents = (RandomAgent(3), RandomAgent(4))
                for _ in range(3000):
                    if env.is_terminal():
                        break
                    obs = env.step(agents[obs.acting_player].select_action(
                        obs, env.legal_actions()))
                assert env.is_terminal()
                path = tmp_path / f"bazoo_torrential_{use_priority}.json"
                write_trajectory(path, env.trajectory())
                trajectory = read_trajectory(path)
                assert audit_trajectory_visibility(trajectory)["decisions"] == len(
                    trajectory.decisions)
                assert verify_trajectory(trajectory,
                                         ExperimentalOcgcoreEngine(root)) == len(
                                             trajectory.decisions)
                return
    pytest.fail(f"Bazoo / Torrential did not resolve: turn={obs.turn} "
                f"phase={obs.phase} setup={graceful}/{discarded}/{trap_set}/"
                f"{summoned} priority={priority_seen}/{cost_paid}/{torrential_used}")
