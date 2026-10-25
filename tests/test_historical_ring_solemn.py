"""Solemn negates pre-errata Ring before it destroys its own-monster target."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

RING = 511000824
SOLEMN = 41420027
ARCHFIEND_SOLDIER = 49881766


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("negate", [False, True])
def test_solemn_negates_ring_before_own_monster_damage(tmp_path, negate):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"pre-errata/c{RING}.lua", f"official/c{SOLEMN}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card scripts not installed")
    ring_cards = list(VANILLA_DECK)
    ring_cards[0] = RING
    ring_cards[1], ring_cards[8] = ring_cards[8], ring_cards[1]
    ring_deck = tmp_path / "ring.ydk"
    ring_deck.write_text("#main\n" + "\n".join(map(str, ring_cards))
                         + "\n#extra\n!side\n")
    solemn_deck = tmp_path / "solemn.ydk"
    solemn_deck.write_text("#main\n" + "\n".join(map(str, (
        SOLEMN, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(ring_deck), str(solemn_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {RING, ARCHFIEND_SOLDIER} <= {card.code for card in obs.hand}
        assert SOLEMN in {card.code for card in env.engine.probe.observation(1).hand}
        summoned = ring_set = solemn_set = ring_used = targeted = response_seen = False
        for _ in range(80):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == ARCHFIEND_SOLDIER), None)
                    summoned = action is not None
                if summoned and not ring_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == RING), None)
                    ring_set = action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not solemn_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SOLEMN), action)
                solemn_set |= action is not None and action.kind == "set_spell_trap"
            if obs.turn == 3 and obs.acting_player == 0 and not ring_used:
                action = next((a for a in actions if a.kind in ("activate", "chain")
                               and a.parameters.get("code") == RING), action)
                ring_used |= action is not None and action.parameters.get("code") == RING
            if ring_used and not targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == ARCHFIEND_SOLDIER
                               and a.parameters.get("controller") == 0), action)
                targeted |= action is not None and action.kind == "select_card"
            if targeted and obs.acting_player == 1 and not response_seen:
                solemn = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SOLEMN), None)
                assert solemn is not None
                assert [link.card_code for link in obs.chain] == [RING]
                if negate:
                    action = solemn
                response_seen = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if response_seen and RING in {c.code for c in obs.graveyards[0]} \
                    and obs.chain == ():
                owner = env.engine.probe.observation(0)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                if negate:
                    assert owner.life_points == (8000, 4000)
                    assert SOLEMN in {c.code for c in owner.graveyards[1]}
                    assert any(c.code == ARCHFIEND_SOLDIER and c.position == "faceup"
                               for c in owner.field)
                    assert ARCHFIEND_SOLDIER not in {c.code for c in owner.graveyards[0]}
                else:
                    assert owner.life_points == (6100, 6100)
                    assert SOLEMN not in {c.code for c in owner.graveyards[1]}
                    assert ARCHFIEND_SOLDIER in {c.code for c in owner.graveyards[0]}
                    assert not any(c.controller == 0 and c.zone == "monster"
                                   for c in owner.field)
                return
    pytest.fail("Ring/Solemn response did not resolve")
