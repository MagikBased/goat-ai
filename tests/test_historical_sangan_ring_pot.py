"""Sangan destroyed mid-chain searches after Pot of Greed finishes drawing."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

SANGAN = 504700178  # GOAT variant
RING = 511000824  # pre-errata variant
POT = 55144522
MYSTICAL_ELF = 15025844


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("draw_sole_target", [False, True])
def test_ring_destroys_sangan_mid_pot_chain_then_searches(tmp_path, draw_sole_target):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{SANGAN}.lua", f"pre-errata/c{RING}.lua",
                     f"official/c{POT}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    player_deck = tmp_path / "sangan_pot.ydk"
    if draw_sole_target:
        high_attack = [code for code in VANILLA_DECK
                       if code not in (MYSTICAL_ELF, 13039848)]
        cards = [SANGAN, POT, *high_attack, *([14087893] * 3), MYSTICAL_ELF]
        assert len(cards) == 40
        cards[10], cards[-1] = cards[-1], cards[10]
    else:
        cards = [SANGAN, POT, *VANILLA_DECK[2:]]
    player_deck.write_text("#main\n" + "\n".join(map(str, cards))
                           + "\n#extra\n!side\n")
    opponent_deck = tmp_path / "ring.ydk"
    opponent_deck.write_text("#main\n" + "\n".join(map(str, (
        RING, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(player_deck), str(opponent_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {SANGAN, POT}.issubset(c.code for c in obs.hand)
        assert RING in {c.code for c in env.engine.probe.observation(1).hand}
        sangan_summoned = ring_set = pot_used = ring_chained = ring_targeted = False
        searched = False
        hand_before = deck_before = None
        for _ in range(70):
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
            if obs.turn == 3 and obs.acting_player == 0 and ring_set and not pot_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == POT), None)
                if action is not None:
                    hand_before = len(obs.hand)
                    deck_before = obs.deck_counts[0]
                    if draw_sole_target:
                        assert MYSTICAL_ELF not in {c.code for c in obs.hand}
                        assert sum(c.code == MYSTICAL_ELF for c in
                                   env.engine.probe._query_location(0, 1)) == 1
                    pot_used = True
            if pot_used and obs.acting_player == 1 and not ring_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == RING), None)
                ring_chained |= action is not None
            if ring_chained and not ring_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == SANGAN), None)
                ring_targeted |= action is not None
            if ring_targeted and not draw_sole_target and not searched \
                    and actions[0].kind == "select_card" \
                    and any(a.parameters.get("location") == 1 for a in actions):
                assert obs.chain and obs.chain[0].card_code == SANGAN
                assert obs.deck_counts[0] == deck_before - 2
                assert len(obs.hand) == hand_before + 1
                assert obs.life_points == (7000, 7000)
                assert SANGAN in {c.code for c in obs.graveyards[0]}
                assert all(a.parameters.get("location") == 1
                           and "sequence" not in a.parameters for a in actions)
                opponent = env.engine.probe.observation(1)
                assert not opponent.private_reveals
                assert opponent.known_opponent_hand_cards == ()
                action = next(a for a in actions if a.parameters.get("code") == MYSTICAL_ELF)
                searched = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if draw_sole_target and ring_targeted:
                owner = env.engine.probe.observation(0)
                opponent = env.engine.probe.observation(1)
                if opponent.private_reveals:
                    assert obs.chain == ()
                    assert MYSTICAL_ELF in {c.code for c in owner.hand}
                    assert not any(c.code == MYSTICAL_ELF for c in
                                   env.engine.probe._query_location(0, 1))
                    assert len(owner.hand) == hand_before + 1
                    assert owner.deck_counts[0] == deck_before - 2 == 31
                    assert owner.life_points == (7000, 7000)
                    assert SANGAN in {c.code for c in owner.graveyards[0]}
                    assert not owner.private_reveals
                    assert len(opponent.private_reveals) == 1
                    reveal = opponent.private_reveals[0]
                    assert reveal.recipient == 1 and len(reveal.cards) == 31
                    assert Counter(c.code for c in reveal.cards) == Counter(
                        c.code for c in env.engine.probe._query_location(0, 1))
                    assert opponent.known_opponent_hand_cards == ()
                    assert {f"goat/c{SANGAN}.lua", f"pre-errata/c{RING}.lua",
                            f"official/c{POT}.lua"}.issubset(
                                env.engine.probe.loaded_script_sha256)
                    return
            if searched and obs.chain == () and MYSTICAL_ELF in {c.code for c in obs.hand}:
                assert obs.deck_counts[0] == deck_before - 3
                assert len(obs.hand) == hand_before + 2
                opponent = env.engine.probe.observation(1)
                assert opponent.known_opponent_hand_cards == (MYSTICAL_ELF,)
                assert [[c.code for c in reveal.cards]
                        for reveal in opponent.private_reveals] == [[MYSTICAL_ELF]]
                assert {f"goat/c{SANGAN}.lua", f"pre-errata/c{RING}.lua",
                        f"official/c{POT}.lua"}.issubset(
                            env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Ring/Sangan/Pot chain did not reach the search")
