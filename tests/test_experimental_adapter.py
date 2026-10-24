"""Protocol regressions for the unaudited full-script deck probe."""

import os
import struct
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.decks import read_ydk
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.native_messages import decode_decision
from goat_ai.engine.protocol import SimulatorUnavailable
from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine
from goat_ai.environments.goat import GoatEnvironment

DECK = "examples/decks/control_probe.ydk"


def test_new_native_choice_formats():
    assert [choice.kind for choice in decode_decision(
        b"\x0d\x00" + struct.pack("<Q", 123)).choices] == ["no", "yes"]
    positions = decode_decision(b"\x13\x00" + struct.pack("<I", 123) + b"\x05")
    assert [choice.position for choice in positions.choices] == [1, 4]
    races = decode_decision(b"\x8c\x00\x01" + struct.pack("<Q", 0b101))
    assert [choice.race for choice in races.choices] == [1, 4]
    tribute = (b"\x14\x00\x01" + struct.pack("<III", 1, 2, 2)
               + struct.pack("<IBBIB", 111, 0, 4, 0, 1)
               + struct.pack("<IBBIB", 222, 0, 4, 1, 1))
    assert [choice.kind for choice in decode_decision(tribute).choices] == [
        "tribute", "tribute", "tribute_cards", "cancel"]


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_control_probe_complete_and_seeded():
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / "scripts/official/c79571449.lua").is_file():
        pytest.skip("full card script checkout not installed")
    with pytest.raises(SimulatorUnavailable, match="cannot simulate card"):
        RestrictedOcgcoreEngine(root)._load_deck(DECK)

    def run():
        with GoatEnvironment(DECK, DECK, 42, ExperimentalOcgcoreEngine(root)) as env:
            observation = env.reset()
            agent = RandomAgent(seed=42)
            trace = []
            for _ in range(3000):
                if env.is_terminal():
                    break
                action = agent.select_action(observation, env.legal_actions())
                trace.append((observation.acting_player, observation.phase,
                              action.kind, action.id))
                observation = env.step(action)
            assert env.is_terminal(), "probe exceeded 3000 decisions"
            return env.result(), tuple(trace)

    first = run()
    assert first[0] == 1
    assert len(first[1]) == 1251
    assert first == run()


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_experimental_duel_loads_fusion_and_41_card_main(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / "scripts/goat/c504700102.lua").is_file():
        pytest.skip("full card script checkout not installed")
    sample = read_ydk(DECK)
    deck_path = tmp_path / "expanded.ydk"
    deck_path.write_text(
        "#main\n" + "\n".join(map(str, (*sample.main, 87621407)))
        + "\n#extra\n504700102\n80071763\n!side\n70074904\n",
        encoding="utf-8",
    )
    with GoatEnvironment(str(deck_path), DECK, 42,
                         ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert observation.deck_counts == (35, 35)
        assert observation.extra_deck_counts == (2, 0)
        assert observation.opponent_hand_count == 5
        assert len(observation.hand) == 6
