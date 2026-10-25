"""Solemn can negate Dustshoot before any hand reveal or return choice."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

DUSTSHOOT = 64697231
SOLEMN = 41420027


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("negate", [False, True])
def test_solemn_response_to_dustshoot_controls_hand_reveal(tmp_path, negate):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"official/c{DUSTSHOOT}.lua", f"official/c{SOLEMN}.lua")
    for script in scripts:
        if not (root / "scripts" / script).is_file():
            pytest.skip(f"script {script} not installed")
    decks = []
    for name, code in (("dustshoot", DUSTSHOOT), ("solemn", SOLEMN)):
        deck = tmp_path / f"{name}.ydk"
        deck.write_text("#main\n" + "\n".join(map(str, (
            code, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
        decks.append(str(deck))

    with GoatEnvironment(*decks, seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert DUSTSHOOT in {c.code for c in obs.hand}
        assert SOLEMN in {c.code for c in env.engine.probe.observation(1).hand}
        dust_set = solemn_set = dust_used = response_made = chosen = False
        revealed = Counter()
        selected_code = None
        hand_before = deck_before = None
        for _ in range(65):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not dust_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                dust_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not solemn_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SOLEMN), None)
                solemn_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and solemn_set \
                    and not dust_used:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                if option is not None:
                    assert obs.opponent_hand_count >= 4
                    assert not obs.private_reveals
                    action = option
                    dust_used = True
                    hand_before = Counter(c.code for c in
                                          env.engine.probe.observation(1).hand)
                    deck_before = obs.deck_counts[1]
            if dust_used and obs.acting_player == 1 and not response_made:
                solemn = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SOLEMN), None)
                if solemn is not None:
                    assert [link.card_code for link in obs.chain] == [DUSTSHOOT]
                    action = solemn if negate else next(a for a in actions
                                                       if a.kind == "pass")
                    response_made = True
            if response_made and not negate and not chosen \
                    and actions[0].kind == "select_card":
                assert obs.acting_player == obs.viewer == 0
                revealed = Counter(c.code for event in obs.private_reveals
                                   if event.recipient == 0 for c in event.cards)
                assert revealed == hand_before
                assert Counter(a.parameters["code"] for a in actions) == revealed
                assert all("sequence" not in a.parameters for a in actions)
                action = actions[0]
                selected_code = action.parameters["code"]
                chosen = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if response_made and not obs.chain and DUSTSHOOT in {
                    c.code for c in obs.graveyards[0]} and (negate or chosen):
                owner = env.engine.probe.observation(0)
                opponent = env.engine.probe.observation(1)
                assert set(scripts).issubset(env.engine.probe.loaded_script_sha256)
                if negate:
                    assert not chosen
                    assert obs.life_points == (8000, 4000)
                    assert Counter(c.code for c in opponent.hand) == hand_before
                    assert owner.deck_counts[1] == deck_before
                    assert not owner.private_reveals
                    assert not owner.known_opponent_hand_cards
                    assert not opponent.private_reveals
                    assert SOLEMN in {c.code for c in obs.graveyards[1]}
                else:
                    assert obs.life_points == (8000, 8000)
                    assert owner.deck_counts[1] == deck_before + 1
                    assert Counter(owner.known_opponent_hand_cards) == (
                        revealed - Counter((selected_code,)))
                    assert Counter(c.code for c in opponent.hand) == (
                        hand_before - Counter((selected_code,)))
                    assert not opponent.private_reveals
                    assert SOLEMN not in {c.code for c in obs.graveyards[1]}
                return
    pytest.fail("Dustshoot/Solemn response did not resolve")
