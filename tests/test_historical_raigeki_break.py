"""Raigeki Break discards as a cost and targets a hidden field slot."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

RAIGEKI_BREAK = 4178474
SERPENT = 511000818  # pre-errata GOAT variant


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_raigeki_break_cost_hidden_target_and_serpent_return(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for script in (f"official/c{RAIGEKI_BREAK}.lua", f"pre-errata/c{SERPENT}.lua"):
        if not (root / "scripts" / script).is_file():
            pytest.skip(f"script {script} not installed")
    deck = tmp_path / "break_serpent.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        *([RAIGEKI_BREAK] * 3), SERPENT, *VANILLA_DECK[4:])))
                    + "\n#extra\n!side\n")
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        trap_set = monster_set = activated = discarded = targeted = returned = False
        target_code = None
        for _ in range(65):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not trap_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == RAIGEKI_BREAK), None)
                trap_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not monster_set:
                action = next((a for a in actions if a.kind == "set_monster"), None)
                if action is not None:
                    target_code = action.parameters["code"]
                    monster_set = True
            if obs.turn == 3 and obs.acting_player == 0 and monster_set and not activated:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == RAIGEKI_BREAK), None)
                activated |= action is not None
            if activated and not discarded and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == SERPENT
                               and a.parameters.get("location") == 2), None)
                discarded = action is not None
            if discarded and not targeted and action is None \
                    and actions[0].kind == "select_card":
                assert SERPENT in {c.code for c in obs.graveyards[0]}
                hidden = next(c for c in obs.field if c.controller == 1
                              and c.zone == "monster")
                assert hidden.code is None and hidden.position == "facedown"
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 4
                               and a.parameters.get("sequence") == hidden.sequence), None)
                assert action is not None and "code" not in action.parameters
                targeted = True
            if obs.turn == 5 and obs.phase == "standby" \
                    and obs.acting_player == 0 and not returned:
                action = next((a for a in actions if a.kind == "yes"
                               and a.parameters.get("code") == SERPENT), action)
                returned |= action is not None and action.kind == "yes"
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if targeted and obs.phase == "main1" and obs.turn == 3 \
                    and obs.acting_player == 0 and RAIGEKI_BREAK in {
                        c.code for c in obs.graveyards[0]}:
                assert target_code in {c.code for c in obs.graveyards[1]}
                assert SERPENT in {c.code for c in obs.graveyards[0]}
                assert not any(c.controller == 1 and c.zone == "monster"
                               for c in obs.field)
            if returned and obs.turn == 5 and obs.phase == "main1" \
                    and obs.acting_player == 0:
                assert SERPENT in {c.code for c in obs.hand}
                assert SERPENT not in {c.code for c in obs.graveyards[0]}
                assert target_code in {c.code for c in obs.graveyards[1]}
                loaded = env.engine.probe.loaded_script_sha256
                assert f"official/c{RAIGEKI_BREAK}.lua" in loaded
                assert f"pre-errata/c{SERPENT}.lua" in loaded
                return
    pytest.fail("Raigeki Break and Sinister Serpent line did not finish")
