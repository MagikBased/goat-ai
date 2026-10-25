"""Two pre-errata Night Assailants discarded together recover each other."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

NIGHT_ASSAILANT = 16226796  # Pre-errata GOAT variant
GRACEFUL_CHARITY = 79571449


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_two_night_assailants_discarded_together_recover_each_other(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for script in (f"pre-errata/c{NIGHT_ASSAILANT}.lua",
                   f"official/c{GRACEFUL_CHARITY}.lua"):
        if not (root / "scripts" / script).is_file():
            pytest.skip(f"script {script} not installed")
    deck = tmp_path / "night_assailants.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        NIGHT_ASSAILANT, NIGHT_ASSAILANT, GRACEFUL_CHARITY,
        *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        activated = discarded = False
        first_trigger = second_trigger = 0
        targets = []
        for _ in range(20):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not activated:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == GRACEFUL_CHARITY), None)
                activated |= action is not None
            if activated and not discarded and actions[0].kind == "select_cards":
                action = next((a for a in actions if [
                    c["code"] for c in a.parameters["cards"]].count(NIGHT_ASSAILANT) == 2),
                              None)
                assert action is not None
                discarded = True
            if discarded and actions[0].kind == "chain":
                assert len(actions) == 2
                assert all(a.parameters.get("code") == NIGHT_ASSAILANT for a in actions)
                assert sum(c.code == NIGHT_ASSAILANT for c in obs.graveyards[0]) == 2
                action = actions[0]
                first_trigger += 1
            if discarded and actions[0].kind == "select_card":
                assert len(actions) == 1
                assert actions[0].parameters["code"] == NIGHT_ASSAILANT
                assert actions[0].parameters["location"] == 16
                targets.append(actions[0].parameters["sequence"])
                action = actions[0]
                second_trigger += 1
            if action is None:
                action = next((a for a in actions if a.kind in ("pass", "place")),
                              actions[0])
            obs = env.step(action)
            own = env.engine.probe.observation(0)
            other = env.engine.probe.observation(1)
            if len(other.private_reveals) == 2:
                assert activated and discarded
                assert first_trigger == 1 and second_trigger == 2
                assert targets == [1, 0]
                assert sum(c.code == NIGHT_ASSAILANT for c in own.hand) == 2
                assert all(c.code != NIGHT_ASSAILANT for c in own.graveyards[0])
                assert other.opponent_hand_count == len(own.hand) == 8
                assert [reveal.recipient for reveal in other.private_reveals] == [1, 1]
                assert [[card.code for card in reveal.cards]
                        for reveal in other.private_reveals] == [
                            [NIGHT_ASSAILANT], [NIGHT_ASSAILANT]]
                assert not own.private_reveals
                loaded = env.engine.probe.loaded_script_sha256
                assert f"pre-errata/c{NIGHT_ASSAILANT}.lua" in loaded
                assert f"official/c{GRACEFUL_CHARITY}.lua" in loaded
                return
    pytest.fail("two Night Assailants did not recover each other")
