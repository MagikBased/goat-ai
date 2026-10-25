"""Ring removes Mirror Force's attacker, but Mirror still destroys another monster."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

MIRROR = 44095762
RING = 511000824


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_ring_chained_to_mirror_removes_attacker_but_not_other_monster(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"official/c{MIRROR}.lua", f"pre-errata/c{RING}.lua")
    for relative in scripts:
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    attacker_deck = tmp_path / "attacker.ydk"
    attacker_deck.write_text("#main\n" + "\n".join(map(str, VANILLA_DECK))
                             + "\n#extra\n!side\n")
    defender_deck = tmp_path / "defender.ydk"
    defender_cards = [MIRROR, *VANILLA_DECK[1:]]
    defender_cards[6] = RING
    defender_deck.write_text("#main\n" + "\n".join(map(str, defender_cards))
                             + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker_deck), str(defender_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        defender_hand = {c.code for c in env.engine.probe.observation(1).hand}
        assert {MIRROR, RING} <= defender_hand
        summons = 0
        mirror_set = ring_set = attacked = mirror_chained = ring_chained = False
        target_selected = False
        attacker_code = other_code = attacker_attack = None
        for _ in range(90):
            actions = env.legal_actions()
            action = None
            if obs.acting_player == 0 and obs.turn in (1, 3) \
                    and summons < (1 if obs.turn == 1 else 2):
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    summons += 1
                    if summons == 2:
                        other_code = action.parameters["code"]
            if obs.turn == 2 and obs.acting_player == 1:
                if not mirror_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == MIRROR), action)
                    mirror_set |= action is not None and action.kind == "set_spell_trap"
                elif not ring_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == RING), action)
                    ring_set |= action is not None and action.kind == "set_spell_trap"
            if obs.turn == 3 and obs.acting_player == 0 and summons == 2 \
                    and not attacked and action is None:
                action = next((a for a in actions if a.kind in (
                    "battle_phase", "attack")), None)
                if action is not None and action.kind == "attack":
                    attacked = True
                    attacker_code = action.parameters["code"]
                    attacker_attack = next(c.attack for c in obs.field
                                           if c.controller == 0 and c.code == attacker_code)
            if attacked and obs.acting_player == 1 and not mirror_chained:
                assert sum(c.controller == 1 and c.zone == "spell_trap"
                           and c.position == "facedown" and c.code is None
                           for c in env.engine.probe.observation(0).field) == 2
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == MIRROR), action)
                mirror_chained |= action is not None and action.kind == "chain"
                if mirror_chained:
                    assert obs.phase == "battle_step"
            if mirror_chained and obs.chain and obs.acting_player == 1 \
                    and not ring_chained:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == RING), None)
                if option is not None:
                    assert tuple(link.card_code for link in obs.chain) == (MIRROR,)
                    action = option
                    ring_chained = True
            if ring_chained and not target_selected and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == attacker_code and a.parameters.get("controller") == 0), None)
                target_selected |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if target_selected and {MIRROR, RING} <= {
                    c.code for pile in obs.graveyards for c in pile} \
                    and obs.chain == ():
                assert attacker_code != other_code
                assert attacker_code in {c.code for c in obs.graveyards[0]}
                assert other_code in {c.code for c in obs.graveyards[0]}
                assert not any(c.controller == 0 and c.zone == "monster"
                               for c in obs.field)
                assert obs.life_points == (8000 - attacker_attack,
                                           8000 - attacker_attack)
                assert set(scripts) <= env.engine.probe.loaded_script_sha256.keys()
                return
    pytest.fail("Ring / Mirror Force chain did not resolve")
