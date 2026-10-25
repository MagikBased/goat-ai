"""Tsukuyomi creates a Nobleman target from face-up GOAT BLS."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

BLS = 504700118
GRACEFUL = 79571449
TSUKUYOMI = 34853266
NOBLEMAN = 504700116
LIGHT = 15025844
DARK = 7359741


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_tsukuyomi_sets_bls_for_nobleman_without_deck_verification(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{BLS}.lua", f"official/c{GRACEFUL}.lua",
               f"official/c{TSUKUYOMI}.lua", f"goat/c{NOBLEMAN}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required GOAT card scripts not installed")
    lights = (LIGHT, 62651957)
    darks = (49881766, DARK)
    filler = [c for c in VANILLA_DECK if c not in (*lights, *darks)]
    boss_deck = tmp_path / "bls.ydk"
    boss_deck.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL, BLS, *(code for code in lights for _ in range(3)),
        *(code for code in darks for _ in range(3)), *filler[:26])))
        + "\n#extra\n!side\n")
    removal_deck = tmp_path / "tsuk_nobleman.ydk"
    removal_deck.write_text("#main\n" + "\n".join(map(str, (
        *([TSUKUYOMI] * 3), *([NOBLEMAN] * 2), *VANILLA_DECK[5:])))
        + "\n#extra\n!side\n")

    with GoatEnvironment(str(boss_deck), str(removal_deck), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, BLS, LIGHT, DARK} <= {c.code for c in obs.hand}
        assert {TSUKUYOMI, NOBLEMAN} <= {
            c.code for c in env.engine.probe.observation(1).hand}
        graceful = discarded = summoned = tsuk_summoned = tsuk_target = False
        set_bls = nobleman = nobleman_target = False
        costs = set()
        deck_counts_before = None
        for _ in range(100):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    graceful |= action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"] for c in
                                   a.parameters["cards"]} == {LIGHT, DARK}), None)
                    discarded |= action is not None
                if discarded and not summoned and action is None:
                    action = next((a for a in actions if a.kind == "special_summon"
                                   and a.parameters.get("code") == BLS), None)
                    summoned |= action is not None
                if summoned and len(costs) < 2 and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   in ({LIGHT, DARK} - costs)), action)
                    if action is not None and action.kind == "select_card":
                        costs.add(action.parameters["code"])
            if obs.turn == 2 and obs.acting_player == 1 and summoned:
                if costs == {LIGHT, DARK} and not tsuk_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == TSUKUYOMI), None)
                    tsuk_summoned |= action is not None
                if tsuk_summoned and not tsuk_target \
                        and actions[0].kind == "select_card":
                    assert [link.card_code for link in obs.chain] == [TSUKUYOMI]
                    action = next((a for a in actions if a.parameters.get("code") == BLS
                                   and a.parameters.get("controller") == 0), None)
                    tsuk_target |= action is not None
                if tsuk_target and not obs.chain and not set_bls:
                    hidden = next((c for c in obs.field if c.controller == 0
                                   and c.zone == "monster"
                                   and c.position == "facedown"), None)
                    if hidden is not None:
                        set_bls = True
                        assert hidden.code is None
                        assert (0, "monster", hidden.sequence, BLS) in {
                            (c.controller, c.zone, c.sequence, c.code)
                            for c in obs.known_opponent_field_cards}
                if set_bls and not nobleman and action is None:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == NOBLEMAN), None)
                    nobleman |= action is not None
                if nobleman and not nobleman_target \
                        and actions[0].kind == "select_card":
                    assert all("code" not in a.parameters for a in actions)
                    deck_counts_before = obs.deck_counts
                    action = next((a for a in actions if a.parameters.get("controller")
                                   == 0 and a.parameters.get("location") == 4), None)
                    nobleman_target |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if nobleman_target and BLS in {c.code for c in obs.banished[0]}:
                assert graceful and discarded and summoned and costs == {LIGHT, DARK}
                assert tsuk_summoned and tsuk_target and set_bls and nobleman
                assert BLS not in {c.code for c in obs.graveyards[0]}
                assert not any(c.code == BLS for c in obs.field)
                assert obs.deck_counts == deck_counts_before
                assert not obs.private_reveals
                assert not env.engine.probe.observation(0).private_reveals
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                agents = (RandomAgent(100), RandomAgent(101))
                for _ in range(5000):
                    if env.is_terminal():
                        break
                    obs = env.step(agents[obs.acting_player].select_action(
                        obs, env.legal_actions()))
                else:
                    pytest.fail("Tsukuyomi / Nobleman continuation exceeded 5000 decisions")
                path = tmp_path / "tsukuyomi_nobleman_bls.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                                             env.trajectory().decisions)
                return
    pytest.fail(f"Tsukuyomi / Nobleman / BLS stalled: turn={obs.turn} phase={obs.phase} "
                f"setup={graceful}/{discarded}/{summoned}/{costs} "
                f"Tsuk={tsuk_summoned}/{tsuk_target} Set={set_bls} "
                f"Nobleman={nobleman}/{nobleman_target}")
