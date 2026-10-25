"""Nobleman removes a set Spy before its Flip Effect can recruit."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

NOBLEMAN = 504700116
SPY = 504700044
GUARD = 37101832


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_nobleman_banishes_set_spy_and_deck_copies_without_recruiting(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{NOBLEMAN}.lua", f"goat/c{SPY}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    attacker = tmp_path / "nobleman.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        NOBLEMAN, *([SPY] * 3), *VANILLA_DECK[4:]))) + "\n#extra\n!side\n")
    defender = tmp_path / "spy.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        *([SPY] * 3), GUARD, *VANILLA_DECK[4:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        set_spy = activated = targeted = False
        remaining_hand_spies = None
        for _ in range(60):
            actions = env.legal_actions()
            action = None
            if observation.turn == 2 and observation.acting_player == 1 and not set_spy:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == SPY), None)
                set_spy |= action is not None
            if observation.turn == 3 and observation.acting_player == 0 and not activated:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == NOBLEMAN), None)
                activated |= action is not None
            if activated and not targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("controller") == 1
                               and "code" not in a.parameters), None)
                targeted |= action is not None
                if targeted:
                    remaining_hand_spies = tuple(sum(card.code == SPY for card in
                                                     env.engine.probe.observation(seat).hand)
                                                 for seat in (0, 1))
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if targeted and any(card.code == SPY for card in observation.banished[1]):
                assert set_spy and activated
                assert not any(card.code == GUARD for card in observation.field)
                assert not any(card.code == SPY for card in observation.graveyards[1])
                assert sum(card.code == SPY for card in observation.banished[1]) \
                    == 3 - remaining_hand_spies[1]
                assert sum(card.code == SPY for card in observation.banished[0]) \
                    == 3 - remaining_hand_spies[0]
                assert sum(card.code == SPY for card in observation.hand) \
                    == remaining_hand_spies[0]
                assert sum(card.code == SPY for card in
                           env.engine.probe.observation(1).hand) \
                    == remaining_hand_spies[1]
                assert {f"goat/c{NOBLEMAN}.lua", f"goat/c{SPY}.lua"}.issubset(
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Nobleman did not remove the set Spy and matching Deck copies")
