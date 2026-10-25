"""Compulsory can remove Ring's target before pre-errata Ring resolves."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

RING = 511000824
COMPULSORY = 94192409
GEMINI_ELF = 69140098


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_compulsory", [False, True])
def test_compulsory_chained_to_ring_removes_target(tmp_path, chain_compulsory):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"pre-errata/c{RING}.lua", f"official/c{COMPULSORY}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    own_cards = (GEMINI_ELF, *([COMPULSORY] * 3),
                 *tuple(code for code in VANILLA_DECK if code != GEMINI_ELF)[:36])
    assert len(own_cards) == 40
    monster_deck = tmp_path / "monster.ydk"
    monster_deck.write_text("#main\n" + "\n".join(map(str, own_cards))
                            + "\n#extra\n!side\n")
    ring_deck = tmp_path / "ring.ydk"
    ring_deck.write_text("#main\n" + "\n".join(map(str, (
        RING, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(monster_deck), str(ring_deck), seed=316,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GEMINI_ELF, COMPULSORY} <= {c.code for c in obs.hand}
        assert RING in {c.code for c in env.engine.probe.observation(1).hand}
        summoned = compulsory_set = ring_set = ring_used = ring_targeted = False
        compulsory_chained = compulsory_targeted = False
        for _ in range(80):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == GEMINI_ELF), None)
                    summoned = action is not None
                if summoned and not compulsory_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == COMPULSORY), None)
                    compulsory_set = action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not ring_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == RING), None)
                ring_set = action is not None
            if obs.turn == 3 and obs.acting_player == 1 and ring_set \
                    and not ring_used:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == RING), None)
                ring_used = action is not None
            if ring_used and not ring_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == GEMINI_ELF), None)
                ring_targeted = action is not None
            if chain_compulsory and ring_targeted and obs.acting_player == 0 \
                    and not compulsory_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == COMPULSORY), None)
                if action is not None:
                    assert [link.card_code for link in obs.chain] == [RING]
                    compulsory_chained = True
            if compulsory_chained and not compulsory_targeted \
                    and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == GEMINI_ELF), None)
                compulsory_targeted = action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if ring_targeted and RING in {c.code for c in obs.graveyards[1]} \
                    and obs.chain == ():
                owner = env.engine.probe.observation(0)
                opponent = env.engine.probe.observation(1)
                assert not any(c.code == GEMINI_ELF for c in owner.field)
                if chain_compulsory:
                    assert compulsory_chained and compulsory_targeted
                    assert owner.life_points == (8000, 8000)
                    assert COMPULSORY in {c.code for c in owner.graveyards[0]}
                    assert GEMINI_ELF in {c.code for c in owner.hand}
                    assert opponent.known_opponent_hand_cards == (GEMINI_ELF,)
                    assert GEMINI_ELF not in {c.code for c in owner.graveyards[0]}
                else:
                    assert not compulsory_chained
                    assert owner.life_points == (6100, 6100)
                    assert GEMINI_ELF in {c.code for c in owner.graveyards[0]}
                    assert COMPULSORY not in {c.code for c in owner.graveyards[0]}
                    assert any(c.controller == 0 and c.zone == "spell_trap"
                               and c.code == COMPULSORY and c.position == "facedown"
                               for c in owner.field)
                    assert opponent.known_opponent_hand_cards == ()
                assert {f"pre-errata/c{RING}.lua",
                        f"official/c{COMPULSORY}.lua"} <= (
                            env.engine.probe.loaded_script_sha256.keys())
                return
    pytest.fail("Ring / Compulsory response did not resolve")
