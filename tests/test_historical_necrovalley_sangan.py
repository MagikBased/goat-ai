"""Necrovalley does not negate Sangan's sent-to-Graveyard Deck search."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

SANGAN = 504700178
NECROVALLEY = 511002998
MYSTICAL_ELF = 15025844


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_sangan_search_resolves_while_necrovalley_is_faceup(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"goat/c{SANGAN}.lua", f"pre-errata/c{NECROVALLEY}.lua")
    for script in scripts:
        if not (root / "scripts" / script).is_file():
            pytest.skip(f"script {script} not installed")
    defender = tmp_path / "sangan_necrovalley.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        SANGAN, NECROVALLEY, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(defender), "examples/decks/vanilla_probe.ydk", seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {SANGAN, NECROVALLEY} <= {c.code for c in obs.hand}
        assert MYSTICAL_ELF in {c.code for c in env.engine.probe._query_location(0, 1)}
        necro_active = sangan_set = attacker_summoned = attacked = searched = False
        deck_before = None
        for _ in range(85):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not necro_active:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == NECROVALLEY), None)
                    necro_active |= action is not None
                if necro_active and not sangan_set and action is None:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == SANGAN), None)
                    sangan_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not attacker_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") not in
                                   (MYSTICAL_ELF, 13039848)), None)
                    attacker_summoned |= action is not None
                if attacker_summoned and not attacked and action is None:
                    action = next((a for a in actions if a.kind in
                                   ("battle_phase", "attack")), None)
                    if action is not None and action.kind == "attack":
                        attacked = True
                        deck_before = obs.deck_counts[0]
            if attacked and not searched and actions[0].kind == "select_card":
                if obs.acting_player == 0 and obs.chain \
                        and obs.chain[0].card_code == SANGAN:
                    assert SANGAN in {c.code for c in obs.graveyards[0]}
                    assert any(c.code == NECROVALLEY and c.position == "faceup"
                               for c in obs.field)
                    action = next((a for a in actions if a.parameters.get("code")
                                   == MYSTICAL_ELF and a.parameters.get("location") == 1), None)
                    assert action is not None and "sequence" not in action.parameters
                    searched = True
                else:
                    action = next((a for a in actions if a.parameters.get("controller")
                                   == 0), None)
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if searched and MYSTICAL_ELF in {c.code for c in obs.hand}:
                opponent = env.engine.probe.observation(1)
                assert obs.deck_counts[0] == deck_before - 1
                assert SANGAN in {c.code for c in obs.graveyards[0]}
                assert any(c.code == NECROVALLEY and c.position == "faceup"
                           for c in obs.field)
                assert opponent.known_opponent_hand_cards == (MYSTICAL_ELF,)
                assert any(reveal.recipient == 1 and
                           [card.code for card in reveal.cards] == [MYSTICAL_ELF]
                           for reveal in opponent.private_reveals)
                assert set(scripts).issubset(env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Sangan did not search through active Necrovalley")
