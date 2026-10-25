"""Pre-errata Sinister Serpent's optional Standby Phase return."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

SINISTER_SERPENT = 511000818  # Pre-errata variant, not modern ID 8131171
GRACEFUL_CHARITY = 79571449


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("accept", [True, False])
def test_serpent_discard_then_optional_standby_return(tmp_path, accept):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for script in (f"pre-errata/c{SINISTER_SERPENT}.lua",
                   f"official/c{GRACEFUL_CHARITY}.lua"):
        if not (root / "scripts" / script).is_file():
            pytest.skip(f"script {script} not installed")
    deck = tmp_path / "serpent.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL_CHARITY, SINISTER_SERPENT, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        graceful = discarded = responded = False
        hand_before = None
        for _ in range(35):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not graceful:
                option = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == GRACEFUL_CHARITY), None)
                if option is not None:
                    action = option
                    graceful = True
            if graceful and not discarded and actions[0].kind == "select_cards":
                action = next((a for a in actions if SINISTER_SERPENT
                               in {c["code"] for c in a.parameters["cards"]}), None)
                discarded = action is not None
            if observation.turn == 3 and observation.phase == "standby" \
                    and observation.acting_player == 0 and not responded:
                choices = {a.kind: a for a in actions
                           if a.parameters.get("code") == SINISTER_SERPENT}
                assert {"yes", "no"}.issubset(choices)
                assert SINISTER_SERPENT in {c.code for c in observation.graveyards[0]}
                assert SINISTER_SERPENT not in {c.code for c in observation.hand}
                other = env.engine.probe.observation(1)
                assert SINISTER_SERPENT in {c.code for c in other.graveyards[0]}
                assert all(c.controller == 1 for c in other.hand)
                hand_before = len(observation.hand)
                action = choices["yes" if accept else "no"]
                responded = True
            if responded and observation.turn == 3 and observation.phase == "main1" \
                    and observation.acting_player == 0:
                in_hand = SINISTER_SERPENT in {c.code for c in observation.hand}
                in_graveyard = SINISTER_SERPENT in {c.code for c in observation.graveyards[0]}
                assert in_hand is accept
                assert in_graveyard is not accept
                assert len(observation.hand) == hand_before + int(accept)
                assert f"pre-errata/c{SINISTER_SERPENT}.lua" \
                    in env.engine.probe.loaded_script_sha256
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
    pytest.fail("Sinister Serpent did not reach its Standby Phase resolution")
