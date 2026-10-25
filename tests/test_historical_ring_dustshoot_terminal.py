"""Lethal Ring chained to Dustshoot ends the duel before the hand reveal."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

RING = 511000824
DUSTSHOOT = 64697231
WALL = 17078030
ARCHFIEND_SOLDIER = 49881766


def _deck(path, cards):
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("lethal", [False, True])
def test_ring_lethal_chain_stops_dustshoot_reveal(tmp_path, lethal):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"pre-errata/c{RING}.lua",
               f"official/c{DUSTSHOOT}.lua", f"official/c{WALL}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card scripts not installed")
    own = _deck(tmp_path / "ring_wall.ydk", (
        RING, WALL, *VANILLA_DECK[2:]))
    other = _deck(tmp_path / "dustshoot.ydk", (
        DUSTSHOOT, *VANILLA_DECK[1:]))

    with GoatEnvironment(own, other, seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {RING, WALL, ARCHFIEND_SOLDIER} <= {c.code for c in obs.hand}
        assert DUSTSHOOT in {c.code for c in env.engine.probe.observation(1).hand}
        soldier = ring_set = wall_set = dust_set = wall_used = cost_paid = False
        dust_used = ring_used = target_chosen = hand_chosen = checked = False
        hand_before = deck_before = selected_code = None
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"ring_dustshoot_{lethal}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not soldier:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == ARCHFIEND_SOLDIER), None)
                    soldier = action is not None
                elif not ring_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == RING), None)
                    ring_set = action is not None
                elif not wall_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == WALL), None)
                    wall_set = action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not dust_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                dust_set = action is not None
            if lethal and obs.turn == 2 and obs.acting_player == 0 \
                    and wall_set and not wall_used:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == WALL), action)
                wall_used = action is not None and action.kind == "chain"
            if wall_used and not cost_paid and actions[0].kind == "announce_number":
                action = next((a for a in actions if a.parameters.get("number")
                               == 7000), None)
                cost_paid = action is not None
            if obs.turn == 3 and obs.acting_player == 1 and dust_set \
                    and not dust_used:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                if option is not None:
                    assert obs.opponent_hand_count == 4
                    assert obs.life_points[0] == (1000 if lethal else 8000)
                    action = option
                    dust_used = True
                    hand_before = Counter(c.code for c in
                                          env.engine.probe.observation(0).hand)
                    deck_before = obs.deck_counts[0]
            if dust_used and obs.acting_player == 0 and not ring_used:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == RING), None)
                if option is not None:
                    assert [link.card_code for link in obs.chain] == [DUSTSHOOT]
                    action = option
                    ring_used = True
            if ring_used and not target_chosen and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == ARCHFIEND_SOLDIER and a.parameters.get("controller")
                               == 0), None)
                target_chosen = action is not None
            if not lethal and target_chosen and not hand_chosen \
                    and actions[0].kind == "select_card" and obs.acting_player == 1:
                assert [link.card_code for link in obs.chain] == [DUSTSHOOT, RING]
                assert Counter(obs.known_opponent_hand_cards) == hand_before
                assert len(obs.private_reveals) == 1
                action = actions[0]
                selected_code = action.parameters["code"]
                hand_chosen = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if lethal and target_chosen and env.is_terminal():
                assert env.result() == 1
                assert obs.life_points == (0, 6100)
                assert not env.engine.probe.observation(1, terminal=True).private_reveals
                assert not hand_chosen
                assert obs.deck_counts[0] == deck_before
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
            if not lethal and hand_chosen and not checked and not obs.chain \
                    and DUSTSHOOT in {c.code for c in obs.graveyards[1]}:
                assert obs.life_points == (6100, 6100)
                assert obs.deck_counts[0] == deck_before + 1
                assert Counter(c.code for c in
                               env.engine.probe.observation(0).hand) == (
                    hand_before - Counter((selected_code,)))
                assert Counter(env.engine.probe.observation(1)
                               .known_opponent_hand_cards) == (
                    hand_before - Counter((selected_code,)))
                assert {f"pre-errata/c{RING}.lua", f"official/c{DUSTSHOOT}.lua"} \
                    <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail("Ring / Dustshoot terminal chain did not complete")
