"""Both Sangan searches after Torrential follow GOAT mandatory-trigger order."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SANGAN = 504700178  # GOAT variant
TORRENTIAL = 53582587
MYSTICAL_ELF = 15025844


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_torrential_destroys_both_sangans_and_opponent_searches_first(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{SANGAN}.lua", f"official/c{TORRENTIAL}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required GOAT card script not installed")
    filler = [code for code in VANILLA_DECK if code != MYSTICAL_ELF]
    decks = []
    for name, cards in (
            ("turn_player", (SANGAN, *([MYSTICAL_ELF] * 3), *filler[:36])),
            ("trap_player", (*([MYSTICAL_ELF] * 3), SANGAN, TORRENTIAL,
                             *filler[:35]))):
        deck = tmp_path / f"{name}.ydk"
        deck.write_text("#main\n" + "\n".join(map(str, cards))
                        + "\n#extra\n!side\n")
        decks.append(str(deck))

    with GoatEnvironment(*decks, seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert SANGAN in {card.code for card in obs.hand}
        assert {SANGAN, TORRENTIAL} <= {
            card.code for card in env.engine.probe.observation(1).hand}
        first_sangan = trap_set = second_sangan = third_summon = torrential = False
        chain_seen = checked = False
        search_order = []
        agents = (RandomAgent(3), RandomAgent(4))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / "both_sangans_torrential.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not first_sangan:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == SANGAN), None)
                first_sangan |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not trap_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == TORRENTIAL), None)
                    trap_set |= action is not None
                if trap_set and not second_sangan and action is None:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == SANGAN), None)
                    second_sangan |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not third_summon:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") != SANGAN), None)
                third_summon |= action is not None
            if third_summon and obs.acting_player == 1 and not torrential:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == TORRENTIAL), action)
                torrential |= action is not None and action.kind == "chain"
            if torrential and not chain_seen and len(obs.chain) == 2 \
                    and [link.card_code for link in obs.chain] == [SANGAN, SANGAN]:
                assert [link.controller for link in obs.chain] == [0, 1]
                assert SANGAN in {card.code for card in obs.graveyards[0]}
                assert SANGAN in {card.code for card in obs.graveyards[1]}
                chain_seen = True
            if chain_seen and actions[0].kind == "select_card" \
                    and len(search_order) < 2:
                assert obs.acting_player == 1 - len(search_order)
                action = next((a for a in actions if a.parameters.get("code")
                               == MYSTICAL_ELF and a.parameters.get("location") == 1),
                              None)
                assert action is not None
                assert "sequence" not in action.parameters
                search_order.append(obs.acting_player)
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if chain_seen and not checked and not obs.chain and search_order == [1, 0]:
                views = (env.engine.probe.observation(0),
                         env.engine.probe.observation(1))
                assert all(MYSTICAL_ELF in {card.code for card in view.hand}
                           for view in views)
                assert all(MYSTICAL_ELF in view.known_opponent_hand_cards
                           for view in views)
                assert obs.life_points == (8000, 8000)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail("Sangan / Torrential simultaneous trigger line did not finish")
