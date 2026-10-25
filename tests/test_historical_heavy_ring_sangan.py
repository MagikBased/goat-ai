"""Ring chained to Heavy Storm destroys Sangan before the Storm resolves."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

HEAVY_STORM = 19613556
RING = 511000824  # GOAT pre-errata variant
SANGAN = 504700178  # GOAT variant
MYSTICAL_ELF = 15025844


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_ring_chained_to_heavy_destroys_own_sangan_then_searches(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"official/c{HEAVY_STORM}.lua", f"pre-errata/c{RING}.lua",
                     f"goat/c{SANGAN}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    sangan_deck = tmp_path / "sangan_ring.ydk"
    sangan_deck.write_text("#main\n" + "\n".join(map(str, (
        SANGAN, RING, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    storm_deck = tmp_path / "storm.ydk"
    storm_deck.write_text("#main\n" + "\n".join(map(str, (
        HEAVY_STORM, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(sangan_deck), str(storm_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {SANGAN, RING}.issubset(c.code for c in obs.hand)
        assert HEAVY_STORM in {c.code for c in env.engine.probe.observation(1).hand}
        summoned = ring_set = heavy_used = ring_chained = targeted = searched = False
        deck_before = None
        for _ in range(90):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == SANGAN), None)
                    summoned |= action is not None
                if summoned and not ring_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == RING), None)
                    ring_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and ring_set \
                    and not heavy_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == HEAVY_STORM), action)
                if action is not None and action.kind == "activate":
                    heavy_used = True
                    deck_before = obs.deck_counts[0]
                    assert any(c.controller == 0 and c.zone == "spell_trap"
                               and c.position == "facedown" and c.code is None
                               for c in obs.field)
            if heavy_used and obs.acting_player == 0 and not ring_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == RING), action)
                ring_chained |= action is not None and action.kind == "chain"
                if ring_chained:
                    assert obs.chain[0].card_code == HEAVY_STORM
            if ring_chained and not targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == SANGAN), None)
                targeted |= action is not None
            if targeted and not searched and actions[0].kind == "select_card" \
                    and any(a.parameters.get("location") == 1 for a in actions):
                assert obs.chain and obs.chain[0].card_code == SANGAN
                assert obs.life_points == (7000, 7000)
                assert SANGAN in {c.code for c in obs.graveyards[0]}
                assert {HEAVY_STORM, RING} <= {
                    c.code for pile in obs.graveyards for c in pile}
                assert not any(c.zone == "spell_trap" for c in obs.field)
                assert env.engine.probe.observation(1).known_opponent_hand_cards == ()
                action = next(a for a in actions if a.parameters.get("code") == MYSTICAL_ELF)
                searched = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if searched and not obs.chain and MYSTICAL_ELF in {c.code for c in obs.hand}:
                assert obs.deck_counts[0] == deck_before - 1
                opponent = env.engine.probe.observation(1)
                assert opponent.known_opponent_hand_cards == (MYSTICAL_ELF,)
                assert [[c.code for c in reveal.cards]
                        for reveal in opponent.private_reveals] == [[MYSTICAL_ELF]]
                assert {f"official/c{HEAVY_STORM}.lua", f"pre-errata/c{RING}.lua",
                        f"goat/c{SANGAN}.lua"}.issubset(
                            env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Ring / Heavy Storm / Sangan line did not reach the search")
