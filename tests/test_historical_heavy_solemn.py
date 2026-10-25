"""Solemn Judgment saves a second Set card by negating Heavy Storm."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

HEAVY_STORM = 19613556
SOLEMN_JUDGMENT = 41420027
BOOK_OF_MOON = 14087893


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("negate_heavy", [False, True])
def test_solemn_negates_heavy_and_preserves_other_backrow(tmp_path, negate_heavy):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (HEAVY_STORM, SOLEMN_JUDGMENT, BOOK_OF_MOON):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    storm_deck = tmp_path / "storm.ydk"
    storm_deck.write_text("#main\n" + "\n".join(map(str, (
        HEAVY_STORM, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    response_cards = list(VANILLA_DECK)
    response_cards[0] = SOLEMN_JUDGMENT
    response_cards[6] = BOOK_OF_MOON
    response_deck = tmp_path / "response.ydk"
    response_deck.write_text("#main\n" + "\n".join(map(str, response_cards))
                             + "\n#extra\n!side\n")

    with GoatEnvironment(str(storm_deck), str(response_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert HEAVY_STORM in {c.code for c in obs.hand}
        assert {SOLEMN_JUDGMENT, BOOK_OF_MOON} <= {
            c.code for c in env.engine.probe.observation(1).hand}
        solemn_set = book_set = heavy_used = response_seen = False
        for _ in range(65):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1:
                if not solemn_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == SOLEMN_JUDGMENT), None)
                    solemn_set = action is not None
                if solemn_set and not book_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOOK_OF_MOON), None)
                    book_set = action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not heavy_used:
                assert solemn_set and book_set
                assert len([c for c in obs.field if c.controller == 1
                            and c.zone == "spell_trap" and c.position == "facedown"
                            and c.code is None]) == 2
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == HEAVY_STORM), None)
                heavy_used = action is not None
            if heavy_used and obs.acting_player == 1 and not response_seen:
                assert [link.card_code for link in obs.chain] == [HEAVY_STORM]
                solemn = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SOLEMN_JUDGMENT), None)
                assert solemn is not None
                if negate_heavy:
                    action = solemn
                response_seen = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if response_seen and HEAVY_STORM in {c.code for c in obs.graveyards[0]} \
                    and obs.chain == ():
                assert obs.life_points == ((8000, 4000) if negate_heavy
                                           else (8000, 8000))
                if negate_heavy:
                    assert SOLEMN_JUDGMENT in {c.code for c in obs.graveyards[1]}
                    assert BOOK_OF_MOON not in {c.code for c in obs.graveyards[1]}
                    assert any(c.controller == 1 and c.zone == "spell_trap"
                               and c.code is None and c.position == "facedown"
                               for c in obs.field)
                else:
                    assert {SOLEMN_JUDGMENT, BOOK_OF_MOON} <= {
                        c.code for c in obs.graveyards[1]}
                    assert not any(c.zone == "spell_trap" for c in obs.field)
                assert {f"official/c{code}.lua" for code in (
                    HEAVY_STORM, SOLEMN_JUDGMENT, BOOK_OF_MOON)} <= (
                        env.engine.probe.loaded_script_sha256.keys())
                return
    pytest.fail("Heavy Storm / Solemn response did not resolve")
