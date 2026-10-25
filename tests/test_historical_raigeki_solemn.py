"""Solemn negates Raigeki Break after Sinister Serpent was discarded."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

RAIGEKI_BREAK = 4178474
SOLEMN = 41420027
SERPENT = 511000818


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("negate", [False, True])
def test_solemn_negates_break_but_not_its_serpent_discard(tmp_path, negate):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{RAIGEKI_BREAK}.lua", f"official/c{SOLEMN}.lua",
               f"pre-errata/c{SERPENT}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card scripts not installed")
    break_deck = tmp_path / "break.ydk"
    break_deck.write_text("#main\n" + "\n".join(map(str, (
        *([RAIGEKI_BREAK] * 3), SERPENT, *VANILLA_DECK[4:])))
        + "\n#extra\n!side\n")
    solemn_deck = tmp_path / "solemn.ydk"
    solemn_deck.write_text("#main\n" + "\n".join(map(str, (
        SOLEMN, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(break_deck), str(solemn_deck), seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {RAIGEKI_BREAK, SERPENT} <= {c.code for c in obs.hand}
        assert SOLEMN in {c.code for c in env.engine.probe.observation(1).hand}
        break_set = solemn_set = monster_set = break_used = serpent_discarded = False
        target_chosen = response_seen = resolved = returned = False
        monster_code = None
        for _ in range(110):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not break_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == RAIGEKI_BREAK), None)
                break_set = action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not solemn_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == SOLEMN), None)
                    solemn_set = action is not None
                if solemn_set and not monster_set and action is None:
                    action = next((a for a in actions if a.kind == "set_monster"), None)
                    if action is not None:
                        monster_code = action.parameters["code"]
                        monster_set = True
            if obs.turn == 3 and obs.acting_player == 0 and monster_set \
                    and not break_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == RAIGEKI_BREAK), None)
                break_used = action is not None
            if break_used and not serpent_discarded and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == SERPENT
                               and a.parameters.get("location") == 2), None)
                serpent_discarded = action is not None
            if serpent_discarded and not target_chosen and action is None \
                    and actions[0].kind == "select_card":
                assert SERPENT in {c.code for c in obs.graveyards[0]}
                hidden = next(c for c in obs.field if c.controller == 1
                              and c.zone == "monster")
                assert hidden.code is None and hidden.position == "facedown"
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 4
                               and a.parameters.get("sequence") == hidden.sequence), None)
                assert action is not None and "code" not in action.parameters
                target_chosen = True
            if target_chosen and obs.acting_player == 1 and not response_seen:
                solemn = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SOLEMN), None)
                assert solemn is not None
                assert [link.card_code for link in obs.chain] == [RAIGEKI_BREAK]
                if negate:
                    action = solemn
                response_seen = True
            if resolved and obs.turn == 5 and obs.phase == "standby" \
                    and obs.acting_player == 0 and not returned:
                action = next((a for a in actions if a.kind == "yes"
                               and a.parameters.get("code") == SERPENT), action)
                returned = action is not None and action.kind == "yes"
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if response_seen and not resolved and RAIGEKI_BREAK in {
                    c.code for c in obs.graveyards[0]} and not obs.chain:
                resolved = True
                owner = env.engine.probe.observation(1)
                assert SERPENT in {c.code for c in obs.graveyards[0]}
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                if negate:
                    assert obs.life_points == (8000, 4000)
                    assert SOLEMN in {c.code for c in obs.graveyards[1]}
                    assert monster_code not in {c.code for c in obs.graveyards[1]}
                    assert any(c.code == monster_code and c.position == "facedown"
                               for c in owner.field)
                    assert not env.engine.probe.observation(0).known_opponent_field_cards
                else:
                    assert obs.life_points == (8000, 8000)
                    assert SOLEMN not in {c.code for c in obs.graveyards[1]}
                    assert monster_code in {c.code for c in obs.graveyards[1]}
                    assert not any(c.controller == 1 and c.zone == "monster"
                                   for c in owner.field)
            if returned and obs.turn == 5 and obs.phase == "main1" \
                    and obs.acting_player == 0:
                assert resolved
                assert SERPENT in {c.code for c in obs.hand}
                assert SERPENT not in {c.code for c in obs.graveyards[0]}
                return
    pytest.fail("Raigeki Break / Solemn / Serpent line did not finish")
