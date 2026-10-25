"""Solemn negates Duo's discards, but cannot refund its 1000 LP cost."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

DUO = 44763025
SOLEMN = 41420027


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("negate", [False, True])
def test_solemn_response_to_duo_preserves_paid_cost(tmp_path, negate):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"official/c{DUO}.lua", f"official/c{SOLEMN}.lua")
    for relative in scripts:
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    duo_deck = tmp_path / "duo.ydk"
    duo_deck.write_text("#main\n" + "\n".join(map(str, (
        DUO, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    solemn_deck = tmp_path / "solemn.ydk"
    solemn_deck.write_text("#main\n" + "\n".join(map(str, (
        SOLEMN, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(duo_deck), str(solemn_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert DUO in {c.code for c in obs.hand}
        assert SOLEMN in {c.code for c in env.engine.probe.observation(1).hand}
        solemn_set = duo_used = response_made = discard_chosen = False
        defender_hand_before = attacker_hand_before = None
        for _ in range(65):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1 and not solemn_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SOLEMN), None)
                solemn_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and solemn_set \
                    and not duo_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == DUO), None)
                if action is not None:
                    duo_used = True
                    attacker_hand_before = len(obs.hand)
                    defender_hand_before = obs.opponent_hand_count
                    assert any(c.controller == 1 and c.zone == "spell_trap"
                               and c.position == "facedown" and c.code is None
                               for c in obs.field)
            if duo_used and obs.acting_player == 1 and not response_made:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SOLEMN), None)
                if option is not None:
                    assert tuple(link.card_code for link in obs.chain) == (DUO,)
                    assert obs.life_points == (7000, 8000)
                    action = option if negate else next(a for a in actions
                                                        if a.kind == "pass")
                    response_made = True
            if response_made and not negate and not discard_chosen \
                    and actions[0].kind == "select_card" \
                    and all(a.parameters.get("location") == 2 for a in actions):
                assert obs.viewer == obs.acting_player == 1
                assert len(obs.hand) == defender_hand_before - 1
                attacker_view = env.engine.probe.observation(0)
                assert attacker_view.opponent_hand_count == len(obs.hand)
                assert not attacker_view.private_reveals
                action = actions[0]
                discard_chosen = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if response_made and DUO in {c.code for c in obs.graveyards[0]} \
                    and obs.chain == () and (negate or discard_chosen):
                if negate:
                    assert not discard_chosen
                assert obs.life_points == ((7000, 4000) if negate else (7000, 8000))
                assert len(env.engine.probe.observation(0).hand) \
                    == attacker_hand_before - 1
                assert env.engine.probe.observation(1).opponent_hand_count \
                    == attacker_hand_before - 1
                assert len(env.engine.probe.observation(1).hand) \
                    == defender_hand_before - (0 if negate else 2)
                assert (SOLEMN in {c.code for c in obs.graveyards[1]}) == negate
                assert not env.engine.probe.observation(0).private_reveals
                assert set(scripts) <= env.engine.probe.loaded_script_sha256.keys()
                return
    pytest.fail("Solemn / Duo response did not resolve")
