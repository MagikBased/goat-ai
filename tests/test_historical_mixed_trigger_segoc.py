"""Mandatory Sangan precedes optional Peten in both controller assignments."""

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
PETEN = 504700084  # GOAT variant
TORRENTIAL = 53582587
MYSTICAL_ELF = 15025844


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("turn_card,other_card,seed", [
    (SANGAN, PETEN, 316),
    (PETEN, SANGAN, 100),
])
def test_torrential_orders_mandatory_before_optional_across_controllers(
        tmp_path, turn_card, other_card, seed):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    required = {f"goat/c{SANGAN}.lua", f"goat/c{PETEN}.lua",
                f"official/c{TORRENTIAL}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in required):
        pytest.skip("required GOAT card script not installed")

    filler = [code for code in VANILLA_DECK if code != MYSTICAL_ELF]
    decks = []
    for player, card in enumerate((turn_card, other_card)):
        cards = ([SANGAN, *([MYSTICAL_ELF] * 3)] if card == SANGAN
                 else [PETEN] * 3)
        if player == 1:
            cards.append(TORRENTIAL)
        deck = tmp_path / f"player_{player}.ydk"
        deck.write_text("#main\n" + "\n".join(map(str, (cards + filler)[:40]))
                        + "\n#extra\n!side\n")
        decks.append(str(deck))

    with GoatEnvironment(*decks, seed=seed,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert turn_card in {card.code for card in obs.hand}
        assert {other_card, TORRENTIAL} <= {
            card.code for card in env.engine.probe.observation(1).hand}
        sangan_player = 0 if turn_card == SANGAN else 1
        peten_player = 1 - sangan_player
        flags = set()
        selections = []
        chain_seen = completed = False
        agents = (RandomAgent(seed), RandomAgent(seed + 1))
        for _ in range(5000):
            if env.is_terminal():
                break
            actions = env.legal_actions()

            def choose(kind, code=None):
                return next((item for item in actions if item.kind == kind
                             and (code is None or item.parameters.get("code") == code)), None)

            if len(obs.chain) == 2 and [link.card_code for link in obs.chain] == [
                    SANGAN, PETEN]:
                assert [link.controller for link in obs.chain] == [
                    sangan_player, peten_player]
                chain_seen = True
            action = None
            if chain_seen and len(selections) < 2 and actions[0].kind == "select_card":
                expected = (peten_player, PETEN) if not selections else (
                    sangan_player, MYSTICAL_ELF)
                assert obs.acting_player == expected[0]
                action = next((item for item in actions if item.parameters.get("code")
                               == expected[1] and (expected[1] == PETEN or
                                                   item.parameters.get("location") == 1)), None)
                assert action is not None, (expected, [item.parameters for item in actions])
                if action.parameters.get("location") == 1:
                    assert "sequence" not in action.parameters
                selections.append(obs.acting_player)
            if action is None and obs.turn == 1 and obs.acting_player == 0 \
                    and "first" not in flags:
                action = choose("normal_summon", turn_card)
                if action:
                    flags.add("first")
            if action is None and obs.turn == 2 and obs.acting_player == 1:
                if "second" not in flags:
                    action = choose("normal_summon", other_card)
                    if action:
                        flags.add("second")
                if action is None and "trap_set" not in flags:
                    action = choose("set_spell_trap", TORRENTIAL)
                    if action:
                        flags.add("trap_set")
            if action is None and obs.turn == 3 and obs.acting_player == 0 \
                    and "third" not in flags:
                action = next((item for item in actions if item.kind == "normal_summon"
                               and item.parameters.get("code") != turn_card), None)
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
            if not completed and selections == [peten_player, sangan_player] \
                    and not obs.chain:
                assert any(card.code == PETEN and card.controller == peten_player
                           for card in obs.field)
                assert PETEN in {card.code for card in obs.banished[peten_player]}
                views = [env.engine.probe.observation(player) for player in (0, 1)]
                assert MYSTICAL_ELF in {card.code for card in views[sangan_player].hand}
                assert MYSTICAL_ELF in views[peten_player].known_opponent_hand_cards
                assert required <= env.engine.probe.loaded_script_sha256.keys()
                completed = True
        assert env.is_terminal() and chain_seen and completed
        path = tmp_path / "mixed_trigger_segoc.json"
        write_trajectory(path, env.trajectory())
        trajectory = read_trajectory(path)
        audit_trajectory_visibility(trajectory)
        assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) == len(
            trajectory.decisions)
