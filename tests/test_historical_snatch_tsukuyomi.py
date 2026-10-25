"""Tsukuyomi turns a Snatch Steal capture into lasting control."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SNATCH = 45986603
TSUKUYOMI = 34853266


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_tsukuyomi_sets_snatch_capture_then_it_can_flip_summon(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{SNATCH}.lua", f"official/c{TSUKUYOMI}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("Snatch Steal or Tsukuyomi script not installed")
    attacker = tmp_path / "snatch_tsukuyomi.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        SNATCH, TSUKUYOMI, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    defender = tmp_path / "monster.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, VANILLA_DECK))
                        + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {SNATCH, TSUKUYOMI} <= {c.code for c in obs.hand}
        defender_summoned = snatch = snatch_target = tsuk_summoned = False
        tsuk_target = stolen_set = flipped = False
        stolen_code = stolen_slot = None
        for _ in range(100):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1 and not defender_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    stolen_code = action.parameters["code"]
                    defender_summoned = True
            if obs.turn == 3 and obs.acting_player == 0 and defender_summoned:
                if not snatch:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == SNATCH), None)
                    snatch |= action is not None
                if snatch and not snatch_target and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == stolen_code and a.parameters.get("controller") == 1),
                                  None)
                    snatch_target |= action is not None
                if snatch_target and not obs.chain and not tsuk_summoned \
                        and any(c.code == stolen_code and c.controller == 0
                                for c in obs.field):
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == TSUKUYOMI), None)
                    tsuk_summoned |= action is not None
                if tsuk_summoned and not tsuk_target \
                        and actions[0].kind == "select_card":
                    assert [link.card_code for link in obs.chain] == [TSUKUYOMI]
                    action = next((a for a in actions if a.parameters.get("code")
                                   == stolen_code and a.parameters.get("controller") == 0),
                                  None)
                    tsuk_target |= action is not None
                if tsuk_target and not obs.chain and not stolen_set:
                    own = env.engine.probe.observation(0)
                    stolen = next((c for c in own.field if c.code == stolen_code
                                   and c.controller == 0 and c.zone == "monster"), None)
                    if stolen is not None and stolen.position == "facedown":
                        stolen_set = True
                        stolen_slot = stolen.sequence
                        assert SNATCH in {c.code for c in own.graveyards[0]}
                        assert not any(c.code == SNATCH for c in own.field)
                        opponent = env.engine.probe.observation(1)
                        hidden = next(c for c in opponent.field if c.controller == 0
                                      and c.zone == "monster"
                                      and c.sequence == stolen_slot)
                        assert hidden.position == "facedown" and hidden.code is None
                        assert (0, "monster", stolen_slot, stolen_code) in {
                            (c.controller, c.zone, c.sequence, c.code)
                            for c in opponent.known_opponent_field_cards}
                if stolen_set and not flipped and action is None:
                    action = next((a for a in actions if a.kind == "flip_summon"
                                   and a.parameters.get("code") == stolen_code), None)
                    flipped |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if flipped and obs.turn == 4 and not obs.chain:
                own = env.engine.probe.observation(0)
                stolen = next(c for c in own.field if c.code == stolen_code
                              and c.controller == 0 and c.zone == "monster")
                assert stolen.position == "faceup" and stolen.sequence == stolen_slot
                assert SNATCH in {c.code for c in own.graveyards[0]}
                assert not any(c.code == stolen_code and c.controller == 1
                               for c in own.field)
                assert TSUKUYOMI in {c.code for c in own.hand}
                assert not any(c.code == TSUKUYOMI for c in own.field)
                assert own.life_points == (8000, 8000)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                agents = (RandomAgent(18), RandomAgent(19))
                for _ in range(5000):
                    if env.is_terminal():
                        break
                    obs = env.step(agents[obs.acting_player].select_action(
                        obs, env.legal_actions()))
                else:
                    pytest.fail("Snatch / Tsukuyomi continuation exceeded 5000 decisions")
                path = tmp_path / "snatch_tsukuyomi.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                                             env.trajectory().decisions)
                return
    pytest.fail(f"Snatch / Tsukuyomi line stalled: turn={obs.turn} phase={obs.phase} "
                f"setup={defender_summoned}/{snatch}/{snatch_target} "
                f"Tsukuyomi={tsuk_summoned}/{tsuk_target} Set={stolen_set} "
                f"Flip={flipped}")
