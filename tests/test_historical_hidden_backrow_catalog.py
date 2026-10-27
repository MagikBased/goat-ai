"""A hidden backrow identity cannot affect the other player's decisions."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

# Common GOAT Spells, Quick-Play Spells, Normal/Counter Traps, and GOAT variants.
HIDDEN_BACKROW = (
    14087893,   # Book of Moon
    5318639,    # Mystical Space Typhoon
    19613556,   # Heavy Storm
    504700123,  # Scapegoat
    41420027,   # Solemn Judgment
    53582587,   # Torrential Tribute
    64697231,   # Trap Dustshoot
    44095762,   # Mirror Force
    4178474,    # Raigeki Break
    511000824,  # Ring of Destruction (GOAT pre-errata ID)
)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
def test_common_hidden_backrow_has_identical_opening_and_next_main_phase(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    snapshots = []
    for hidden_code in HIDDEN_BACKROW:
        opponent = tmp_path / f"hidden_{hidden_code}.ydk"
        opponent.write_text(
            "#main\n" + "\n".join(map(str, (hidden_code, *VANILLA_DECK[1:])))
            + "\n#extra\n!side\n")
        with GoatEnvironment("examples/decks/nobleman_probe.ydk", str(opponent),
                             seed=52, engine=ExperimentalOcgcoreEngine(root)) as env:
            observation = env.reset()
            assert hidden_code in {card.code for card in
                                   env.engine.probe.observation(1).hand}
            opening = (observation, env.legal_actions())
            set_done = False
            for _ in range(55):
                actions = env.legal_actions()
                action = None
                if observation.turn == 2 and observation.acting_player == 1 \
                        and not set_done:
                    action = next((option for option in actions
                                   if option.kind == "set_spell_trap"
                                   and option.parameters.get("code") == hidden_code), None)
                    set_done |= action is not None
                if observation.turn == 3 and observation.acting_player == 0 \
                        and observation.phase == "main1":
                    assert set_done
                    assert observation.viewer == 0
                    assert observation.known_opponent_field_cards == ()
                    assert observation.private_reveals == ()
                    assert len(actions) > 1
                    hidden = [card for card in observation.field
                              if card.controller == 1 and card.zone == "spell_trap"]
                    assert len(hidden) == 1
                    assert hidden[0].position == "facedown" and hidden[0].code is None
                    assert env.engine.probe._query_location(1, 8)[0].code == hidden_code
                    snapshots.append((opening, observation, actions))
                    break
                if action is None:
                    action = next((option for option in actions
                                   if option.kind in ("pass", "end_phase")), actions[0])
                observation = env.step(action)
            else:
                pytest.fail(f"next Main Phase was not reached for {hidden_code}")

    assert len(snapshots) == len(HIDDEN_BACKROW)
    assert all(snapshot == snapshots[0] for snapshot in snapshots[1:])
