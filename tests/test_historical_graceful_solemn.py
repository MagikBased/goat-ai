"""Solemn can negate Graceful before its private draw and discard choices."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

GRACEFUL = 79571449
SOLEMN = 41420027


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("negate", [False, True])
def test_solemn_response_to_graceful_controls_draw_and_discard(tmp_path, negate):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"official/c{GRACEFUL}.lua", f"official/c{SOLEMN}.lua")
    for relative in scripts:
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    graceful_deck = tmp_path / "graceful.ydk"
    graceful_deck.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    solemn_deck = tmp_path / "solemn.ydk"
    solemn_deck.write_text("#main\n" + "\n".join(map(str, (
        SOLEMN, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(graceful_deck), str(solemn_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert GRACEFUL in {c.code for c in obs.hand}
        assert SOLEMN in {c.code for c in env.engine.probe.observation(1).hand}
        solemn_set = graceful_used = response_made = discarded = False
        hand_before = deck_before = None
        for _ in range(65):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1 and not solemn_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SOLEMN), None)
                solemn_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and solemn_set \
                    and not graceful_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == GRACEFUL), None)
                if action is not None:
                    graceful_used = True
                    hand_before = len(obs.hand)
                    deck_before = obs.deck_counts[0]
                    assert any(c.controller == 1 and c.zone == "spell_trap"
                               and c.position == "facedown" and c.code is None
                               for c in obs.field)
            if graceful_used and obs.acting_player == 1 and not response_made:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SOLEMN), None)
                if option is not None:
                    assert tuple(link.card_code for link in obs.chain) == (GRACEFUL,)
                    action = option if negate else next(a for a in actions
                                                        if a.kind == "pass")
                    response_made = True
            if response_made and not negate and not discarded \
                    and actions[0].kind == "select_cards":
                assert obs.viewer == obs.acting_player == 0
                assert obs.deck_counts[0] == deck_before - 3
                assert len(obs.hand) == hand_before + 2
                defender = env.engine.probe.observation(1)
                assert defender.opponent_hand_count == len(obs.hand)
                assert not defender.private_reveals
                action = actions[0]
                assert len(action.parameters["cards"]) == 2
                discarded = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if response_made and GRACEFUL in {c.code for c in obs.graveyards[0]} \
                    and obs.chain == () and (negate or discarded):
                if negate:
                    assert not discarded
                assert obs.life_points == ((8000, 4000) if negate else (8000, 8000))
                assert len(obs.hand) == hand_before - (1 if negate else 0)
                assert obs.deck_counts[0] == deck_before - (0 if negate else 3)
                assert (SOLEMN in {c.code for c in obs.graveyards[1]}) == negate
                assert len(obs.graveyards[0]) == (1 if negate else 3)
                assert not env.engine.probe.observation(1).private_reveals
                assert set(scripts) <= env.engine.probe.loaded_script_sha256.keys()
                return
    pytest.fail("Solemn / Graceful response did not resolve")
