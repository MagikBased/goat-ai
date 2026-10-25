"""A public Sangan search stays known through Graceful's private draw, then discard."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

SANGAN = 504700178
GRACEFUL = 79571449
SERPENT = 511000818
RING = 511000824


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_public_serpent_search_then_private_graceful_draw_and_discard(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"goat/c{SANGAN}.lua", f"official/c{GRACEFUL}.lua",
               f"pre-errata/c{SERPENT}.lua", f"pre-errata/c{RING}.lua")
    for relative in scripts:
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    owner_cards = [SANGAN, GRACEFUL, *VANILLA_DECK[2:]]
    owner_cards[-1] = SERPENT
    owner_deck = tmp_path / "sangan_graceful_serpent.ydk"
    owner_deck.write_text("#main\n" + "\n".join(map(str, owner_cards))
                          + "\n#extra\n!side\n")
    ring_deck = tmp_path / "ring.ydk"
    ring_deck.write_text("#main\n" + "\n".join(map(str, (
        RING, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(owner_deck), str(ring_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {SANGAN, GRACEFUL} <= {c.code for c in obs.hand}
        assert SERPENT not in {c.code for c in obs.hand}
        assert RING in {c.code for c in env.engine.probe.observation(1).hand}
        sangan_summoned = ring_set = ring_used = ring_targeted = searched = False
        graceful_used = discarded = False
        deck_before_graceful = None
        for _ in range(90):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not sangan_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == SANGAN), None)
                sangan_summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not ring_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == RING), None)
                ring_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 1 and ring_set and not ring_used:
                action = next((a for a in actions if a.kind in ("chain", "activate")
                               and a.parameters.get("code") == RING), None)
                ring_used |= action is not None
            if ring_used and not ring_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == SANGAN
                               and a.parameters.get("controller") == 0), None)
                ring_targeted |= action is not None
            if ring_targeted and not searched and actions[0].kind == "select_card" \
                    and any(a.parameters.get("location") == 1 for a in actions):
                assert obs.acting_player == 0
                assert env.engine.probe.observation(1).known_opponent_hand_cards == ()
                action = next((a for a in actions if a.parameters.get("code") == SERPENT
                               and a.parameters.get("location") == 1), None)
                searched |= action is not None
            if searched and obs.turn == 3 and obs.phase == "main1" \
                    and obs.acting_player == 0 and not graceful_used:
                assert env.engine.probe.observation(1).known_opponent_hand_cards \
                    == (SERPENT,)
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == GRACEFUL), None)
                if action is not None:
                    graceful_used = True
                    deck_before_graceful = obs.deck_counts[0]
            if graceful_used and not discarded and actions[0].kind == "select_cards":
                assert env.engine.probe.observation(1).known_opponent_hand_cards \
                    == (SERPENT,)
                assert obs.deck_counts[0] == deck_before_graceful - 3
                action = next((a for a in actions if SERPENT in {
                    card["code"] for card in a.parameters["cards"]}), None)
                discarded |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if discarded and SERPENT in {c.code for c in obs.graveyards[0]} \
                    and obs.chain == ():
                opponent = env.engine.probe.observation(1)
                assert SERPENT not in {c.code for c in obs.hand}
                assert opponent.known_opponent_hand_cards == ()
                assert [[c.code for c in event.cards]
                        for event in opponent.private_reveals] == [[SERPENT]]
                assert obs.deck_counts[0] == deck_before_graceful - 3
                assert obs.life_points == (7000, 7000)
                assert set(scripts) <= env.engine.probe.loaded_script_sha256.keys()
                return
    pytest.fail("Sangan search / Graceful discard line did not complete")
