"""Historical Necrovalley exception for pre-errata Sinister Serpent."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

GRACEFUL = 79571449
SERPENT = 511000818
NECROVALLEY = 511002998


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_necrovalley_does_not_stop_sinister_serpent_standby_return(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{GRACEFUL}.lua", f"pre-errata/c{SERPENT}.lua",
               f"pre-errata/c{NECROVALLEY}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required historical scripts not installed")
    cards = (GRACEFUL, SERPENT, NECROVALLEY, *VANILLA_DECK[3:])
    deck = tmp_path / "necro_serpent.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, SERPENT, NECROVALLEY} <= {c.code for c in obs.hand}
        graceful = discarded = necro = recovered = False
        before = None
        for _ in range(60):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    graceful |= action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if SERPENT in {
                        c["code"] for c in a.parameters["cards"]}
                        and NECROVALLEY not in {
                            c["code"] for c in a.parameters["cards"]}), None)
                    discarded |= action is not None
                if discarded and not necro and action is None:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == NECROVALLEY), None)
                    necro |= action is not None
            if (necro and obs.turn == 3 and obs.phase == "standby"
                    and obs.acting_player == 0 and not recovered):
                choices = {a.kind: a for a in actions
                           if a.parameters.get("code") == SERPENT}
                assert {"yes", "no"} <= choices.keys()
                assert SERPENT in {c.code for c in obs.graveyards[0]}
                assert any(c.code == NECROVALLEY and c.position == "faceup"
                           for c in obs.field)
                before = len(obs.hand)
                action = choices["yes"]
                recovered = True
            if recovered and obs.turn == 3 and obs.phase == "main1":
                assert SERPENT in {c.code for c in obs.hand}
                assert SERPENT not in {c.code for c in obs.graveyards[0]}
                assert len(obs.hand) == before + 1
                assert any(c.code == NECROVALLEY and c.position == "faceup"
                           for c in obs.field)
                other = env.engine.probe.observation(1)
                assert other.known_opponent_hand_cards == (SERPENT,)
                assert not other.private_reveals
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
    pytest.fail(f"Necrovalley/Serpent line stalled: graceful={graceful}, "
                f"discarded={discarded}, necro={necro}, recovered={recovered}")
