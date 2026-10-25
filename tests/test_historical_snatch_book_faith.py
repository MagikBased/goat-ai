"""A stolen Faith stays stolen after Book and uses its controller's Graveyard."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

SNATCH = 45986603
BOOK = 14087893
FAITH = 31560081


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_snatch_book_stolen_faith_recovers_controllers_book(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (SNATCH, BOOK, FAITH)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required official card script not installed")
    thief = tmp_path / "thief.ydk"
    thief.write_text("#main\n" + "\n".join(map(str, (
        SNATCH, BOOK, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    owner = tmp_path / "owner.ydk"
    owner.write_text("#main\n" + "\n".join(map(str, (
        FAITH, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(thief), str(owner), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {SNATCH, BOOK} <= {c.code for c in obs.hand}
        assert FAITH in {c.code for c in env.engine.probe.observation(1).hand}
        faith_summoned = snatch_used = snatch_targeted = booked = book_targeted = False
        flip_used = faith_targeted = False
        for _ in range(100):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1 and not faith_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == FAITH), None)
                faith_summoned = action is not None
            if obs.turn == 3 and obs.acting_player == 0:
                if not snatch_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == SNATCH), None)
                    snatch_used = action is not None
                if snatch_used and not snatch_targeted \
                        and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == FAITH
                                   and a.parameters.get("controller") == 1), None)
                    snatch_targeted = action is not None
                if snatch_targeted and not booked and any(
                        c.code == FAITH and c.controller == 0 and c.position == "faceup"
                        for c in obs.field):
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == BOOK), action)
                    booked = action is not None and action.kind == "activate"
                if booked and not book_targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == FAITH
                                   and a.parameters.get("controller") == 0), None)
                    book_targeted = action is not None
            if book_targeted and obs.turn == 3 \
                    and BOOK in {c.code for c in obs.graveyards[0]}:
                own = env.engine.probe.observation(0)
                own_faith = next(c for c in own.field if c.zone == "monster")
                assert own_faith.code == FAITH and own_faith.controller == 0
                assert own_faith.position == "facedown"
                assert SNATCH in {c.code for c in obs.graveyards[0]}
                other = env.engine.probe.observation(1)
                assert any(c.controller == 0 and c.code is None
                           and c.position == "facedown" for c in other.field)
                assert (0, "monster", own_faith.sequence, FAITH) in {
                    (c.controller, c.zone, c.sequence, c.code)
                    for c in other.known_opponent_field_cards}
            if obs.turn == 5 and obs.acting_player == 0:
                if not flip_used:
                    action = next((a for a in actions if a.kind == "flip_summon"
                                   and a.parameters.get("code") == FAITH), None)
                    flip_used = action is not None
                if flip_used and not faith_targeted \
                        and actions[0].kind == "select_card":
                    assert obs.chain and obs.chain[0].card_code == FAITH
                    action = next((a for a in actions if a.parameters.get("code") == BOOK
                                   and a.parameters.get("location") == 16), None)
                    faith_targeted = action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if faith_targeted and BOOK in {c.code for c in obs.hand} \
                    and obs.chain == ():
                assert obs.turn == 5 and obs.acting_player == 0
                assert any(c.code == FAITH and c.controller == 0
                           and c.position == "faceup" for c in obs.field)
                assert BOOK not in {c.code for c in obs.graveyards[0]}
                assert not any(c.code == BOOK for c in env.engine.probe.observation(1).hand)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                return
    pytest.fail("Snatch / Book / Faith line did not resolve")
