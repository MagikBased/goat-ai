"""Magician of Faith recovers and reuses Graceful Charity without leaking draws."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import verify_trajectory

GRACEFUL = 79571449
FAITH = 31560081


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_faith_recovers_graceful_and_second_use_draws_then_discards(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (GRACEFUL, FAITH)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required official scripts not installed")
    deck = tmp_path / "faith_graceful.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL, FAITH, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, FAITH} <= {c.code for c in obs.hand}
        uses = discards = 0
        faith_set = faith_flipped = recovered = False
        second_hand_before = second_deck_before = None
        second_discard_codes = None
        grave_before_second = Counter()
        checked = False
        agents = (RandomAgent(18), RandomAgent(19))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                trajectory = env.trajectory()
                assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) == len(
                    trajectory.decisions)
                assert audit_trajectory_visibility(trajectory)["decisions"] == len(
                    trajectory.decisions)
                return
            actions = env.legal_actions()
            action = None
            if not checked and obs.turn == 1 and obs.acting_player == 0:
                if uses == 0:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    uses += action is not None
                if uses == 1 and discards == 0 and actions[0].kind == "select_cards":
                    action = next((a for a in actions if FAITH not in {
                        card["code"] for card in a.parameters["cards"]}), None)
                    discards += action is not None
                if discards == 1 and not faith_set and action is None:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == FAITH), None)
                    faith_set |= action is not None
            if not checked and obs.turn == 3 and obs.acting_player == 0:
                if faith_set and not faith_flipped:
                    action = next((a for a in actions if a.kind == "flip_summon"
                                   and a.parameters.get("code") == FAITH), None)
                    faith_flipped |= action is not None
                if faith_flipped and not recovered and actions[0].kind == "select_card":
                    assert [link.card_code for link in obs.chain] == [FAITH]
                    action = next((a for a in actions if a.parameters.get("code") == GRACEFUL
                                   and a.parameters.get("location") == 16), None)
                    recovered |= action is not None
                if recovered and uses == 1 and GRACEFUL in {c.code for c in obs.hand}:
                    opponent = env.engine.probe.observation(1)
                    assert opponent.known_opponent_hand_cards == (GRACEFUL,)
                    assert [[c.code for c in reveal.cards]
                            for reveal in opponent.private_reveals] == [[GRACEFUL]]
                    second_hand_before = len(obs.hand)
                    second_deck_before = obs.deck_counts[0]
                    grave_before_second = Counter(c.code for c in obs.graveyards[0])
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    uses += action is not None
                if uses == 2 and discards == 1 and actions[0].kind == "select_cards":
                    assert obs.deck_counts[0] == second_deck_before - 3
                    action = actions[0]
                    second_discard_codes = tuple(c["code"] for c in
                                                 action.parameters["cards"])
                    assert len(second_discard_codes) == 2
                    discards += 1
            if action is None:
                action = (agents[obs.acting_player].select_action(obs, actions) if checked
                          else next((a for a in actions if a.kind in (
                              "place", "select_position", "pass", "end_phase")), actions[0]))
            obs = env.step(action)
            if not checked and uses == discards == 2 and not obs.chain \
                    and GRACEFUL in {c.code for c in obs.graveyards[0]}:
                own = env.engine.probe.observation(0)
                opponent = env.engine.probe.observation(1)
                assert faith_set and faith_flipped and recovered
                assert own.deck_counts[0] == second_deck_before - 3
                assert len(own.hand) == second_hand_before
                assert Counter(c.code for c in own.graveyards[0]) - grave_before_second \
                    == Counter((GRACEFUL, *second_discard_codes))
                assert opponent.known_opponent_hand_cards == ()
                assert opponent.opponent_hand_count == len(own.hand)
                assert [[c.code for c in reveal.cards]
                        for reveal in opponent.private_reveals] == [[GRACEFUL]]
                assert not own.private_reveals
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail(f"Faith/Graceful line stalled: uses={uses} discards={discards} "
                f"Faith={faith_set}/{faith_flipped}/{recovered} turn={obs.turn}")
