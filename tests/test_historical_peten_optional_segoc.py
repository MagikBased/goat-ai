"""Simultaneous optional Peten triggers follow GOAT turn-player order."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory


PETEN = 504700084  # GOAT variant
TORRENTIAL = 53582587


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_both_players_peten_optional_triggers_after_torrential(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    required = (f"goat/c{PETEN}.lua", f"official/c{TORRENTIAL}.lua")
    if any(not (root / "scripts" / script).is_file() for script in required):
        pytest.skip("required GOAT card script not installed")
    decks = []
    for name, cards in (
        ("turn_player", [PETEN] * 3 + list(VANILLA_DECK[3:])),
        ("trap_player", [PETEN] * 3 + [TORRENTIAL] + list(VANILLA_DECK[4:])),
    ):
        path = tmp_path / f"{name}.ydk"
        path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
        decks.append(str(path))

    with GoatEnvironment(*decks, seed=316,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert PETEN in {card.code for card in obs.hand}
        assert {PETEN, TORRENTIAL} <= {
            card.code for card in env.engine.probe.observation(1).hand}
        flags = set()
        search_order = []
        two_link_seen = completed = False
        agents = (RandomAgent(316), RandomAgent(317))
        for _ in range(5000):
            if env.is_terminal():
                break
            actions = env.legal_actions()

            def choose(kind, code=None):
                return next((action for action in actions if action.kind == kind
                             and (code is None or action.parameters.get("code") == code)), None)

            if len(obs.chain) == 2 and all(link.card_code == PETEN for link in obs.chain):
                assert [link.controller for link in obs.chain] == [0, 1]
                two_link_seen = True
            if two_link_seen and len(search_order) < 2 and actions[0].kind == "select_card":
                assert obs.acting_player == 1 - len(search_order)
                action = choose("select_card", PETEN)
                assert action is not None
                search_order.append(obs.acting_player)
            else:
                action = None
                if obs.turn == 1 and obs.acting_player == 0 and "first" not in flags:
                    action = choose("normal_summon", PETEN)
                    if action:
                        flags.add("first")
                if obs.turn == 2 and obs.acting_player == 1:
                    if "second" not in flags:
                        action = choose("normal_summon", PETEN)
                        if action:
                            flags.add("second")
                    if action is None and "trap_set" not in flags:
                        action = choose("set_spell_trap", TORRENTIAL)
                        if action:
                            flags.add("trap_set")
                if obs.turn == 3 and obs.acting_player == 0 and "third" not in flags:
                    action = next((item for item in actions if item.kind == "normal_summon"
                                   and item.parameters.get("code") != PETEN), None)
                    if action:
                        flags.add("third")
                if action is None and "third" in flags and obs.acting_player == 1 \
                        and "torrential" not in flags:
                    action = choose("chain", TORRENTIAL)
                    if action:
                        flags.add("torrential")
                if action is None and "torrential" in flags:
                    action = choose("yes", PETEN) or choose("chain", PETEN)
                if action is None and not completed:
                    action = (choose("place") or choose("select_position")
                              or choose("pass") or choose("end_phase") or actions[0])
                if action is None:
                    action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if not completed and search_order == [1, 0] and not obs.chain:
                assert all(any(card.code == PETEN and card.controller == player
                               for card in obs.field) for player in (0, 1))
                assert all(any(card.code == PETEN for card in obs.banished[player])
                           for player in (0, 1))
                assert set(required) <= env.engine.probe.loaded_script_sha256.keys()
                completed = True
        assert env.is_terminal() and completed and two_link_seen
        path = tmp_path / "peten_optional_segoc.json"
        write_trajectory(path, env.trajectory())
        trajectory = read_trajectory(path)
        audit_trajectory_visibility(trajectory)
        assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) == len(
            trajectory.decisions)
