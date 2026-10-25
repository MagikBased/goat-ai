"""Ring destroys Chaos Sorcerer after its banish effect enters the chain."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SORCERER = 9596126
GRACEFUL = 79571449
RING = 511000824  # pre-errata variant
LIGHT = 15025844
DARK = 7359741


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("use_ring", [False, True])
def test_ring_chained_to_sorcerer_banish_does_not_stop_banish(tmp_path, use_ring):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{SORCERER}.lua", f"official/c{GRACEFUL}.lua",
               f"pre-errata/c{RING}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    lights = (LIGHT, 62651957)
    darks = (49881766, DARK)
    filler = [code for code in VANILLA_DECK if code not in (*lights, *darks)]
    chaos_cards = (GRACEFUL, SORCERER,
                   *(code for code in lights for _ in range(3)),
                   *(code for code in darks for _ in range(3)), *filler[:26])
    chaos_deck = tmp_path / "sorcerer.ydk"
    chaos_deck.write_text("#main\n" + "\n".join(map(str, chaos_cards))
                          + "\n#extra\n!side\n")
    ring_deck = tmp_path / "ring.ydk"
    ring_deck.write_text("#main\n" + "\n".join(map(str, (
        RING, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(chaos_deck), str(ring_deck), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {SORCERER, GRACEFUL, LIGHT, DARK} <= {card.code for card in obs.hand}
        assert RING in {card.code for card in env.engine.probe.observation(1).hand}
        graceful = discarded = ring_set = defender_summoned = summoned = False
        effect_used = target_selected = responded = ring_targeted = checked = False
        costs = set()
        defender_code = None
        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"sorcerer_ring_{use_ring}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    graceful |= action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {card["code"] for card in
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
                                   and a.parameters.get("code") == SORCERER), None)
                    summoned |= action is not None
                if summoned and len(costs) < 2 and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   in ({LIGHT, DARK} - costs)), action)
                    if action is not None and action.kind == "select_card":
                        costs.add(action.parameters["code"])
                if summoned and len(costs) == 2 and not effect_used:
                    option = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == SORCERER), None)
                    if option is not None:
                        assert not obs.chain
                        action = option
                        effect_used = True
                if effect_used and not target_selected and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == defender_code and a.parameters.get("controller") == 1),
                                  None)
                    target_selected |= action is not None
            if target_selected and obs.acting_player == 1 and not responded \
                    and [link.card_code for link in obs.chain] == [SORCERER]:
                ring = next((a for a in actions if a.kind == "chain"
                             and a.parameters.get("code") == RING), None)
                assert ring is not None
                action = ring if use_ring else next(a for a in actions if a.kind == "pass")
                responded = True
            if use_ring and responded and not ring_targeted \
                    and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 0
                               and a.parameters.get("code") == SORCERER), None)
                ring_targeted |= action is not None
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if responded and not checked and not obs.chain and defender_code in {
                    card.code for card in obs.banished[1]}:
                assert costs == {LIGHT, DARK}
                assert target_selected
                assert obs.life_points == ((5700, 5700) if use_ring else (8000, 8000))
                assert (SORCERER in {card.code for card in obs.graveyards[0]}) == use_ring
                assert (SORCERER in {card.code for card in obs.field}) != use_ring
                assert (RING in {card.code for card in obs.graveyards[1]}) == use_ring
                assert {f"official/c{SORCERER}.lua", f"official/c{GRACEFUL}.lua"} \
                    <= env.engine.probe.loaded_script_sha256.keys()
                if use_ring:
                    assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                    assert ring_targeted
                checked = True
    pytest.fail("Sorcerer / Ring duel did not finish")
