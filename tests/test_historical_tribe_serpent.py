"""Tribe-Infecting Virus uses Sinister Serpent as a recoverable discard cost."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

TRIBE = 33184167
SERPENT = 511000818  # Pre-errata Sinister Serpent
GAGAGIGO = 49003308
REPTILE = 524288
AQUA = 64


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_tribe_declares_present_type_after_discarding_serpent_as_cost(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for script in (f"official/c{TRIBE}.lua", f"pre-errata/c{SERPENT}.lua"):
        if not (root / "scripts" / script).is_file():
            pytest.skip(f"script {script} not installed")
    deck = tmp_path / "tribe_serpent.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        TRIBE, SERPENT, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        tribe_summoned = opponent_summoned = effect_used = discarded = announced = False
        serpent_returned = False
        for _ in range(60):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 \
                    and not tribe_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == TRIBE), None)
                tribe_summoned |= action is not None
            if observation.turn == 2 and observation.acting_player == 1 \
                    and not opponent_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == GAGAGIGO), None)
                opponent_summoned |= action is not None
            if observation.turn == 3 and observation.acting_player == 0:
                if not effect_used:
                    option = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == TRIBE), None)
                    if option is not None:
                        assert {c.code for c in observation.field} == {TRIBE, GAGAGIGO}
                        action = option
                        effect_used = True
                if effect_used and not discarded and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == SERPENT
                                   and a.parameters.get("controller") == 0
                                   and a.parameters.get("location") == 2), None)
                    discarded = action is not None
                if discarded and not announced and actions[0].kind == "announce_race":
                    assert {a.parameters["race"] for a in actions} == {AQUA, REPTILE}
                    assert SERPENT in {c.code for c in observation.graveyards[0]}
                    assert SERPENT not in {c.code for c in observation.hand}
                    other = env.engine.probe.observation(1)
                    assert SERPENT in {c.code for c in other.graveyards[0]}
                    assert all(c.controller == 1 for c in other.hand)
                    action = next(a for a in actions if a.parameters["race"] == REPTILE)
                    announced = True
            if announced and observation.turn == 3 and observation.phase == "main1" \
                    and observation.acting_player == 0 and GAGAGIGO \
                    in {c.code for c in observation.graveyards[1]}:
                assert {c.code for c in observation.field} == {TRIBE}
                assert SERPENT in {c.code for c in observation.graveyards[0]}
            if observation.turn == 5 and observation.phase == "standby" \
                    and observation.acting_player == 0 and not serpent_returned:
                action = next((a for a in actions if a.kind == "yes"
                               and a.parameters.get("code") == SERPENT), action)
                serpent_returned |= action is not None and action.kind == "yes"
            if serpent_returned and observation.turn == 5 and observation.phase == "main1" \
                    and observation.acting_player == 0:
                assert SERPENT in {c.code for c in observation.hand}
                assert SERPENT not in {c.code for c in observation.graveyards[0]}
                assert GAGAGIGO in {c.code for c in observation.graveyards[1]}
                loaded = env.engine.probe.loaded_script_sha256
                assert f"official/c{TRIBE}.lua" in loaded
                assert f"pre-errata/c{SERPENT}.lua" in loaded
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
    pytest.fail("Tribe-Infecting Virus and Sinister Serpent line did not complete")
