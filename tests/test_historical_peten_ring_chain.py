"""The historical Pot/Ring/Peten missed-timing example in a native duel."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

PETEN = 504700084  # Pinned GOAT variant.
POT = 55144522
RING = 511000824  # Pinned pre-errata variant.


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_peten_destroyed_by_ring_chained_to_pot_misses_timing(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{PETEN}.lua", f"official/c{POT}.lua",
               f"pre-errata/c{RING}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required historical card scripts not installed")

    own = tmp_path / "peten_pot.ydk"
    other = tmp_path / "ring.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        PETEN, PETEN, PETEN, POT, *VANILLA_DECK[4:]))) + "\n#extra\n!side\n")
    other.write_text("#main\n" + "\n".join(map(str, (
        RING, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(other), seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {PETEN, POT} <= {card.code for card in obs.hand}
        assert RING in {card.code for card in env.engine.probe.observation(1).hand}
        summoned = ring_set = pot_used = ring_chained = targeted = checked = False
        deck_before_pot = None
        agents = (RandomAgent(15), RandomAgent(16))
        for _ in range(5000):
            if env.is_terminal():
                break
            actions = env.legal_actions()

            def choose(kind, code=None):
                return next((action for action in actions if action.kind == kind
                             and (code is None or action.parameters.get("code") == code)), None)

            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not summoned:
                action = choose("normal_summon", PETEN)
                summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not ring_set:
                action = choose("set_spell_trap", RING)
                ring_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and ring_set and not pot_used:
                action = choose("activate", POT) or action
                pot_used |= action is not None and action.kind == "activate" \
                    and action.parameters.get("code") == POT
                if pot_used:
                    deck_before_pot = obs.deck_counts[0]
            if pot_used and obs.acting_player == 1 and not ring_chained:
                option = choose("chain", RING)
                if option is not None:
                    assert [link.card_code for link in obs.chain] == [POT]
                    action = option
                    ring_chained = True
            if ring_chained and not targeted and actions[0].kind == "select_card":
                action = next((item for item in actions if item.kind == "select_card"
                               and item.parameters.get("code") == PETEN
                               and item.parameters.get("controller") == 0), None)
                assert action is not None
                targeted = True
            if targeted and not checked and not obs.chain \
                    and any(card.code == PETEN for card in obs.graveyards[0]):
                assert obs.life_points == (7500, 7500)
                assert obs.deck_counts[0] == deck_before_pot - 2
                assert {POT, RING} <= {card.code for pile in obs.graveyards
                                       for card in pile}
                assert not any(item.kind in ("yes", "chain")
                               and item.parameters.get("code") == PETEN
                               for item in actions)
                assert not obs.banished[0]
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
            if action is None:
                action = (choose("pass") or choose("end_phase") or choose("place")
                          or choose("select_position") or
                          agents[obs.acting_player].select_action(obs, actions))
            obs = env.step(action)

        assert summoned and ring_set and pot_used and ring_chained and targeted and checked
        assert env.is_terminal()
        path = tmp_path / "peten_ring_chain.json"
        write_trajectory(path, env.trajectory())
        replay = read_trajectory(path)
        assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(
            replay.decisions)
        assert audit_trajectory_visibility(replay)["decisions"] == len(replay.decisions)
