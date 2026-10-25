"""Ring and Book responses to BLS's pending banish effect."""

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
RING = 511000824
BOOK = 14087893
LIGHT = 15025844
DARK = 7359741


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("response", ["pass", "ring_target", "ring_bls",
                                         "book_bls"])
def test_ring_chained_to_bls_banish(tmp_path, response):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{BLS}.lua", f"official/c{GRACEFUL}.lua",
               f"pre-errata/c{RING}.lua", f"official/c{BOOK}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required GOAT card scripts not installed")
    lights = (LIGHT, 62651957)
    darks = (49881766, DARK)
    filler = [BOOK if code == 23771716 else code for code in VANILLA_DECK
              if code not in (*lights, *darks)]
    attacker = tmp_path / "bls.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL, BLS, *(code for code in lights for _ in range(3)),
        *(code for code in darks for _ in range(3)), *filler[:26])))
        + "\n#extra\n!side\n")
    defender = tmp_path / "ring.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        RING, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {BLS, GRACEFUL, BOOK, LIGHT, DARK} <= {card.code for card in obs.hand}
        graceful = discarded = ring_set = defender_summoned = False
        summoned = priority_seen = banish_targeted = responded = ring_targeted = False
        book_chained = book_targeted = False
        defender_code = defender_attack = None
        costs = set()
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
                                   a.parameters["cards"]} == {LIGHT, DARK}), None)
                    discarded |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not ring_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == RING), None)
                    ring_set |= action is not None
                if ring_set and not defender_summoned and action is None:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        defender_code = action.parameters["code"]
                        defender_summoned = True
            if obs.turn == 3 and obs.acting_player == 0 and defender_summoned:
                if not summoned:
                    action = next((a for a in actions if a.kind == "special_summon"
                                   and a.parameters.get("code") == BLS), None)
                    summoned |= action is not None
                if summoned and len(costs) < 2 and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   in ({LIGHT, DARK} - costs)), action)
                    if action is not None and action.kind == "select_card":
                        costs.add(action.parameters["code"])
                if summoned and len(costs) == 2 and not priority_seen:
                    action = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == BLS), None)
                    if action is not None:
                        assert obs.chain == ()
                        assert any(c.controller == 1 and c.zone == "spell_trap"
                                   and c.position == "facedown" and c.code is None
                                   for c in obs.field)
                        priority_seen = True
                if priority_seen and not banish_targeted \
                        and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == defender_code and a.parameters.get("controller") == 1),
                                  None)
                    banish_targeted |= action is not None
                    if banish_targeted:
                        defender_attack = next(c.attack for c in obs.field
                                               if c.code == defender_code
                                               and c.controller == 1)
            if banish_targeted and obs.acting_player == 1 and not responded:
                assert obs.chain[0].card_code == BLS
                ring = next((a for a in actions if a.kind == "chain"
                             and a.parameters.get("code") == RING), None)
                assert ring is not None
                action = ring if response != "pass" else next(
                    a for a in actions if a.kind == "pass")
                responded = True
            if response != "pass" and responded and not ring_targeted \
                    and actions[0].kind == "select_card":
                ring_code = defender_code if response == "ring_target" else BLS
                ring_controller = 1 if response == "ring_target" else 0
                action = next((a for a in actions if a.parameters.get("code")
                               == ring_code and a.parameters.get("controller")
                               == ring_controller), None)
                ring_targeted |= action is not None
            if response == "book_bls" and ring_targeted and obs.acting_player == 0 \
                    and not book_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK), None)
                book_chained |= action is not None
            if book_chained and not book_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == BLS
                               and a.parameters.get("controller") == 0), None)
                book_targeted |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if responded and not obs.chain and defender_code in {
                    c.code for c in (obs.graveyards[1] if response == "ring_target"
                                     else obs.banished[1])}:
                assert costs == {LIGHT, DARK} and priority_seen and banish_targeted
                assert ring_targeted == (response != "pass")
                assert book_chained == book_targeted == (response == "book_bls")
                assert (RING in {c.code for c in obs.graveyards[1]}) == (
                    response != "pass")
                assert (BOOK in {c.code for c in obs.graveyards[0]}) == (
                    response == "book_bls")
                own_bls = next((c for c in obs.field if c.code == BLS), None)
                assert (BLS in {c.code for c in obs.graveyards[0]}) == (
                    response == "ring_bls")
                assert (own_bls is None) == (response == "ring_bls")
                if response == "book_bls":
                    assert own_bls.position == "facedown"
                elif own_bls is not None:
                    assert own_bls.position == "faceup"
                assert (defender_code in {c.code for c in obs.banished[1]}) == (
                    response != "ring_target")
                assert (defender_code in {c.code for c in obs.graveyards[1]}) == (
                    response == "ring_target")
                damage = {"pass": 0, "ring_target": defender_attack,
                          "ring_bls": 3000, "book_bls": 0}[response]
                assert obs.life_points == (8000 - damage,) * 2
                expected_scripts = {f"goat/c{BLS}.lua", f"official/c{GRACEFUL}.lua"}
                if response != "pass":
                    expected_scripts.add(f"pre-errata/c{RING}.lua")
                if response == "book_bls":
                    expected_scripts.add(f"official/c{BOOK}.lua")
                assert expected_scripts <= env.engine.probe.loaded_script_sha256.keys()
                agents = (RandomAgent(100), RandomAgent(101))
                for _ in range(5000):
                    if env.is_terminal():
                        break
                    obs = env.step(agents[obs.acting_player].select_action(
                        obs, env.legal_actions()))
                else:
                    pytest.fail("BLS / Ring continuation exceeded 5000 decisions")
                trajectory = env.trajectory()
                path = tmp_path / f"bls_ring_{response}.json"
                write_trajectory(path, trajectory)
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                                             trajectory.decisions)
                return
    pytest.fail(f"BLS / Ring line stalled: turn={obs.turn} phase={obs.phase} "
                f"setup={graceful}/{discarded}/{ring_set}/{defender_summoned} "
                f"summon={summoned}/{costs} priority={priority_seen}/{banish_targeted} "
                f"response={response}/{responded}/{ring_targeted} "
                f"book={book_chained}/{book_targeted}")
