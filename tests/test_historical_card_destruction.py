"""Card Destruction hand reset precedes Night Assailant discard triggers."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

CARD_DESTRUCTION = 72892473
NIGHT_ASSAILANT = 16226796  # pre-errata GOAT variant
BANISHER_OF_THE_LIGHT = 61528025


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_card_destruction_draws_before_night_assailant_triggers(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for script in (f"official/c{CARD_DESTRUCTION}.lua",
                   f"pre-errata/c{NIGHT_ASSAILANT}.lua"):
        if not (root / "scripts" / script).is_file():
            pytest.skip(f"script {script} not installed")
    deck = tmp_path / "card_destruction.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        CARD_DESTRUCTION, NIGHT_ASSAILANT, NIGHT_ASSAILANT,
        *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        activated = checked_reset = False
        target_slots = []
        before_hands = before_decks = None
        for _ in range(18):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not activated:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == CARD_DESTRUCTION), None)
                if action is not None:
                    own = env.engine.probe.observation(0)
                    other = env.engine.probe.observation(1)
                    before_hands = (Counter(c.code for c in own.hand
                                            if c.code != CARD_DESTRUCTION),
                                    Counter(c.code for c in other.hand))
                    before_decks = own.deck_counts
                    assert len(own.hand) == 6 and len(other.hand) == 5
                    activated = True
            if activated and actions[0].kind == "chain":
                assert len(actions) == 2
                assert all(a.parameters.get("code") == NIGHT_ASSAILANT
                           for a in actions)
                action = actions[0]
            if activated and actions[0].kind == "select_card":
                assert len(actions) == 1
                assert actions[0].parameters["code"] == NIGHT_ASSAILANT
                assert actions[0].parameters["location"] == 16
                target_slots.append(actions[0].parameters["sequence"])
                action = actions[0]
            if action is None:
                action = next((a for a in actions if a.kind in ("pass", "place")),
                              actions[0])
            obs = env.step(action)
            own = env.engine.probe.observation(0)
            other = env.engine.probe.observation(1)
            if activated and not checked_reset and len(own.graveyards[1]) == 5:
                assert before_hands is not None and before_decks is not None
                assert own.deck_counts == other.deck_counts == (
                    before_decks[0] - 5, before_decks[1] - 5)
                assert Counter(c.code for c in own.graveyards[0]
                               if c.code != CARD_DESTRUCTION) == before_hands[0]
                assert Counter(c.code for c in own.graveyards[1]) == before_hands[1]
                assert len(own.hand) == len(other.hand) == 5
                assert own.opponent_hand_count == other.opponent_hand_count == 5
                assert not own.private_reveals and not other.private_reveals
                checked_reset = True
            if len(other.private_reveals) == 2:
                assert checked_reset and target_slots == [0, 2]
                assert sum(c.code == NIGHT_ASSAILANT for c in own.hand) == 2
                assert all(c.code != NIGHT_ASSAILANT for c in own.graveyards[0])
                assert len(own.hand) == 7 and other.opponent_hand_count == 7
                assert len(other.hand) == 5 and own.opponent_hand_count == 5
                assert [[c.code for c in reveal.cards]
                        for reveal in other.private_reveals] == [
                            [NIGHT_ASSAILANT], [NIGHT_ASSAILANT]]
                assert not own.private_reveals
                loaded = env.engine.probe.loaded_script_sha256
                assert f"official/c{CARD_DESTRUCTION}.lua" in loaded
                assert f"pre-errata/c{NIGHT_ASSAILANT}.lua" in loaded
                return
    pytest.fail("Card Destruction / Night Assailant line did not finish")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_card_destruction_draws_full_count_under_banisher(tmp_path):
    """GOAT Netrep: replacement of the discards does not reduce either draw."""
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (CARD_DESTRUCTION, BANISHER_OF_THE_LIGHT):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"official script for {code} not installed")
    deck = tmp_path / "card_destruction_banisher.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        CARD_DESTRUCTION, BANISHER_OF_THE_LIGHT, *VANILLA_DECK[2:])))
        + "\n#extra\n!side\n")
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {CARD_DESTRUCTION, BANISHER_OF_THE_LIGHT} <= {c.code for c in obs.hand}
        summoned = activated = checked = False
        before_hands = before_decks = None
        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / "card_destruction_banisher.json"
                write_trajectory(path, env.trajectory())
                restored = read_trajectory(path)
                assert verify_trajectory(restored, ExperimentalOcgcoreEngine(root)) == len(
                    restored.decisions)
                audit_trajectory_visibility(restored)
                return
            actions = env.legal_actions()
            action = None
            if not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == BANISHER_OF_THE_LIGHT), None)
                summoned = action is not None
            if summoned and not activated and action is None:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == CARD_DESTRUCTION), None)
                if action is not None:
                    own = env.engine.probe.observation(0)
                    other = env.engine.probe.observation(1)
                    before_hands = (
                        Counter(c.code for c in own.hand if c.code != CARD_DESTRUCTION),
                        Counter(c.code for c in other.hand))
                    before_decks = own.deck_counts
                    assert len(own.hand) == 5 and len(other.hand) == 5
                    activated = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if activated and not checked and CARD_DESTRUCTION in {
                    c.code for c in obs.banished[0]} and not obs.chain:
                assert before_hands is not None and before_decks is not None
                assert obs.deck_counts == (before_decks[0] - 4, before_decks[1] - 5)
                assert len(obs.hand) == 4 and obs.opponent_hand_count == 5
                assert obs.graveyards == ((), ())
                assert Counter(c.code for c in obs.banished[0]
                               if c.code != CARD_DESTRUCTION) == before_hands[0]
                assert Counter(c.code for c in obs.banished[1]) == before_hands[1]
                assert all(c.position == "faceup" for pile in obs.banished
                           for c in pile)
                assert not obs.private_reveals
                assert not env.engine.probe.observation(1).private_reveals
                loaded = env.engine.probe.loaded_script_sha256
                assert f"official/c{CARD_DESTRUCTION}.lua" in loaded
                assert f"official/c{BANISHER_OF_THE_LIGHT}.lua" in loaded
                checked = True
    pytest.fail("Card Destruction / Banisher line did not finish")
