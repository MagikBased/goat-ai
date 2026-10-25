"""Solemn can negate Compulsory during an attack, preserving the attacker."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

COMPULSORY = 94192409
SOLEMN = 41420027
GEMINI_ELF = 69140098


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("negate", [False, True])
def test_solemn_response_to_compulsory_attack_bounce(tmp_path, negate):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (COMPULSORY, SOLEMN)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required official card script not installed")
    attacker_cards = list(VANILLA_DECK)
    attacker_cards[0], attacker_cards[6] = attacker_cards[6], attacker_cards[0]
    attacker_cards[1] = SOLEMN
    attacker = tmp_path / "attacker.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, attacker_cards))
                        + "\n#extra\n!side\n")
    defender = tmp_path / "defender.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        COMPULSORY, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GEMINI_ELF, SOLEMN} <= {c.code for c in obs.hand}
        assert COMPULSORY in {c.code for c in env.engine.probe.observation(1).hand}
        summoned = solemn_set = compulsory_set = attacked = False
        compulsory_chained = targeted = solemn_chained = False
        for _ in range(95):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == GEMINI_ELF), None)
                    summoned = action is not None
                if summoned and not solemn_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == SOLEMN), None)
                    solemn_set = action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not compulsory_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == COMPULSORY), action)
                compulsory_set |= action is not None and action.kind == "set_spell_trap"
            if (obs.turn == 3 and obs.acting_player == 0 and compulsory_set
                    and not attacked):
                action = next((a for a in actions if a.kind in ("battle_phase", "attack")
                               and (a.kind != "attack"
                                    or a.parameters.get("code") == GEMINI_ELF)), action)
                attacked |= action is not None and action.kind == "attack"
            if attacked and obs.acting_player == 1 and not compulsory_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == COMPULSORY), action)
                compulsory_chained |= action is not None and action.kind == "chain"
                if compulsory_chained:
                    assert obs.phase == "battle_step"
            if compulsory_chained and not targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == GEMINI_ELF
                               and a.parameters.get("controller") == 0), action)
                targeted |= action is not None and action.kind == "select_card"
            if negate and targeted and obs.acting_player == 0 and not solemn_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SOLEMN), action)
                solemn_chained |= action is not None and action.kind == "chain"
                if solemn_chained:
                    assert [link.card_code for link in obs.chain] == [COMPULSORY]
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "select_position", "pass", "end_phase",
                    "main2")), actions[0])
            obs = env.step(action)
            if targeted and COMPULSORY in {c.code for c in obs.graveyards[1]} \
                    and obs.chain == ():
                owner = env.engine.probe.observation(0)
                opponent = env.engine.probe.observation(1)
                if negate:
                    assert solemn_chained and owner.life_points[0] == 4000
                    assert SOLEMN in {c.code for c in owner.graveyards[0]}
                    assert any(c.code == GEMINI_ELF and c.controller == 0
                               for c in owner.field)
                    assert GEMINI_ELF not in {c.code for c in owner.hand}
                    assert opponent.known_opponent_hand_cards == ()
                else:
                    assert not solemn_chained and owner.life_points == (8000, 8000)
                    assert SOLEMN not in {c.code for c in owner.graveyards[0]}
                    assert GEMINI_ELF in {c.code for c in owner.hand}
                    assert not any(c.code == GEMINI_ELF for c in owner.field)
                    assert GEMINI_ELF in opponent.known_opponent_hand_cards
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                return
    pytest.fail("Compulsory/Solemn attack response did not resolve")
