"""Protocol regressions for the unaudited full-script deck probe."""

import os
import struct
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.decks import read_ydk
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.native_messages import decode_decision
from goat_ai.engine.ocgcore_probe import LOCATION_HAND, LOCATION_MZONE
from goat_ai.engine.protocol import SimulatorUnavailable
from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine
from goat_ai.environments.goat import GoatEnvironment

DECK = "examples/decks/control_probe.ydk"


def test_new_native_choice_formats():
    yes_no = decode_decision(b"\x0d\x00" + struct.pack("<Q", 123))
    assert [choice.kind for choice in yes_no.choices] == ["no", "yes"]
    assert [choice.prompt_id for choice in yes_no.choices] == [123, 123]
    options = decode_decision(b"\x0e\x01\x02" + struct.pack("<QQ", 17, 23))
    assert [(choice.response, choice.prompt_id) for choice in options.choices] == [
        (0, 17), (1, 23)]
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
        + "\n#extra\n504700102\n80071763\n!side\n",
        encoding="utf-8",
    )
    with GoatEnvironment(str(deck_path), DECK, 42,
                         ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert observation.deck_counts == (35, 35)
        assert observation.extra_deck_counts == (2, 0)
        assert observation.opponent_hand_count == 5
        assert len(observation.hand) == 6


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_hidden_opponent_effect_card_cannot_change_opening_view_or_actions(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / "scripts/official/c79571449.lua").is_file():
        pytest.skip("full card script checkout not installed")
    original = read_ydk(DECK)
    changed = list(original.main)
    changed[changed.index(2134346)] = 39507162  # Asura Priest -> Blade Knight
    alternate = tmp_path / "alternate.ydk"
    alternate.write_text("#main\n" + "\n".join(map(str, changed)) + "\n")

    def first_decision(opponent_deck):
        engine = ExperimentalOcgcoreEngine(root)
        try:
            decision = engine.reset(DECK, str(opponent_deck), 42)
            # Private query is test-only evidence that the hidden hand changed.
            hidden_hand = tuple(card.code for card in engine.probe._query_location(1, LOCATION_HAND)
                                if card is not None)
            return decision, hidden_hand
        finally:
            engine.close()

    baseline, first_hidden = first_decision(DECK)
    alternate_view, second_hidden = first_decision(alternate)
    assert first_hidden != second_hidden
    assert 2134346 in first_hidden and 39507162 in second_hidden
    assert baseline.observation == alternate_view.observation
    assert baseline.legal_actions == alternate_view.legal_actions


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_different_opponent_set_effect_cards_have_identical_visible_decisions(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / "scripts/official/c79571449.lua").is_file():
        pytest.skip("full card script checkout not installed")
    original = read_ydk(DECK)
    changed = list(original.main)
    changed[changed.index(2134346)] = 39507162
    alternate = tmp_path / "alternate.ydk"
    alternate.write_text("#main\n" + "\n".join(map(str, changed)) + "\n")

    def after_set(opponent_deck, target):
        with GoatEnvironment(DECK, str(opponent_deck), 42,
                             ExperimentalOcgcoreEngine(root)) as env:
            observation = env.reset()
            set_target = False
            for _ in range(40):
                if observation.viewer == 0 and observation.turn == 3:
                    assert set_target
                    private_code = env.engine.probe._query_location(1, LOCATION_MZONE)[0].code
                    return observation, env.legal_actions(), private_code
                actions = env.legal_actions()
                action = None
                if observation.acting_player == 1 and not set_target:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == target), None)
                    if action is not None:
                        set_target = True
                if action is None:
                    action = next((a for a in actions if a.kind == "end_phase"), None)
                if action is None:
                    action = next((a for a in actions if a.kind == "pass"), actions[0])
                observation = env.step(action)
            pytest.fail("did not reach the next player-zero draw phase")

    first_view, first_actions, first_private = after_set(DECK, 2134346)
    next_view, next_actions, next_private = after_set(alternate, 39507162)
    assert (first_private, next_private) == (2134346, 39507162)
    assert first_view.field[0].code is None
    assert first_view == next_view
    assert first_actions == next_actions
