"""GOAT Sangan effects triggered at different Chain Links keep event order."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory


SANGAN = 504700178  # GOAT variant
RAIGEKI_BREAK = 4178474
MYSTICAL_ELF = 15025844


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_two_sangans_destroyed_at_different_chain_links_follow_event_time(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{SANGAN}.lua", f"official/c{RAIGEKI_BREAK}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required GOAT card script not installed")
    filler = [code for code in VANILLA_DECK if code != MYSTICAL_ELF]
    cards = ([SANGAN, *([RAIGEKI_BREAK] * 3), *([MYSTICAL_ELF] * 3)]
             + filler)[:40]
    deck = tmp_path / "sangan_break.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, cards))
                    + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), str(deck), seed=316,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {SANGAN, RAIGEKI_BREAK} <= {card.code for card in obs.hand}
        assert {SANGAN, RAIGEKI_BREAK} <= {
            card.code for card in env.engine.probe.observation(1).hand}
        flags = set()
        searches = []
        chain_seen = completed = False
        agents = (RandomAgent(316), RandomAgent(317))
        for _ in range(5000):
            if env.is_terminal():
                break
            actions = env.legal_actions()

            def choose(kind, code=None, location=None, controller=None):
                return next((item for item in actions if item.kind == kind
                             and (code is None or item.parameters.get("code") == code)
                             and (location is None or item.parameters.get("location") == location)
                             and (controller is None or item.parameters.get("controller") == controller)),
                            None)

            if len(obs.chain) == 2 and [link.card_code for link in obs.chain] == [
                    SANGAN, SANGAN]:
                # Break CL2 destroys the non-turn player's Sangan first.
                # Break CL1 destroys the turn player's Sangan later.
                assert [link.controller for link in obs.chain] == [1, 0]
                assert all(SANGAN in {card.code for card in obs.graveyards[player]}
                           for player in (0, 1))
                chain_seen = True
            action = None
            if chain_seen and len(searches) < 2 and actions[0].kind == "select_card":
                assert obs.acting_player == len(searches)
                action = choose("select_card", MYSTICAL_ELF, location=1)
                assert action is not None and "sequence" not in action.parameters
                searches.append(obs.acting_player)
            if action is None and obs.turn == 1 and obs.acting_player == 0:
                if "first_sangan" not in flags:
                    action = choose("normal_summon", SANGAN)
                    if action:
                        flags.add("first_sangan")
                if action is None and "first_break" not in flags:
                    action = choose("set_spell_trap", RAIGEKI_BREAK)
                    if action:
                        flags.add("first_break")
            if action is None and obs.turn == 2 and obs.acting_player == 1:
                if "second_sangan" not in flags:
                    action = choose("normal_summon", SANGAN)
                    if action:
                        flags.add("second_sangan")
                if action is None and "second_break" not in flags:
                    action = choose("set_spell_trap", RAIGEKI_BREAK)
                    if action:
                        flags.add("second_break")
            if action is None and obs.turn == 3 and not completed:
                if obs.acting_player == 0 and "first_activated" not in flags:
                    action = choose("chain", RAIGEKI_BREAK, location=8, controller=0)
                    if action:
                        flags.add("first_activated")
                if action is None and obs.acting_player == 1 \
                        and "first_activated" in flags and "second_activated" not in flags:
                    action = choose("chain", RAIGEKI_BREAK, location=8, controller=1)
                    if action:
                        flags.add("second_activated")
                if action is None and actions[0].kind == "select_card" and not chain_seen:
                    action = (choose("select_card", SANGAN, location=4,
                                     controller=obs.acting_player)
                              or next((item for item in actions
                                       if item.parameters.get("location") == 2), None))
            if action is None and not completed:
                action = (choose("place") or choose("pass")
                          or choose("end_phase") or actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if not completed and searches == [0, 1] and not obs.chain:
                views = [env.engine.probe.observation(player) for player in (0, 1)]
                assert all(MYSTICAL_ELF in {card.code for card in view.hand}
                           for view in views)
                assert all(MYSTICAL_ELF in view.known_opponent_hand_cards
                           for view in views)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                completed = True
        assert env.is_terminal() and chain_seen and completed
        path = tmp_path / "midchain_sangan_order.json"
        write_trajectory(path, env.trajectory())
        trajectory = read_trajectory(path)
        audit_trajectory_visibility(trajectory)
        assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) == len(
            trajectory.decisions)
