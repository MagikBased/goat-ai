"""Book of Moon resets BLS's once-per-turn banish effect after a Flip Summon."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

BLS = 504700118
GRACEFUL = 79571449
BOOK = 14087893
SCAPEGOAT = 504700123
LIGHT = 62651957
DARK = 7359741


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_bls_book_flip_summon_allows_second_banish_same_turn(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{BLS}.lua", f"goat/c{SCAPEGOAT}.lua",
               f"official/c{GRACEFUL}.lua", f"official/c{BOOK}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    lights = (15025844, LIGHT)
    darks = (49881766, DARK)
    filler = [code for code in VANILLA_DECK if code not in (*lights, *darks)]
    cards = [GRACEFUL, BLS, *(c for c in lights for _ in range(3)),
             *(c for c in darks for _ in range(3)), *filler[:26]]
    cards[-1] = BOOK
    own_deck = tmp_path / "bls_book.ydk"
    own_deck.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    opposing_cards = [SCAPEGOAT if code == 51934376 else code
                      for code in VANILLA_DECK]
    opposing_deck = tmp_path / "scapegoat.ydk"
    opposing_deck.write_text("#main\n" + "\n".join(map(str, opposing_cards))
                             + "\n#extra\n!side\n")

    with GoatEnvironment(str(own_deck), str(opposing_deck), seed=182,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, BLS, BOOK} <= {c.code for c in obs.hand}
        assert SCAPEGOAT in {c.code for c in env.engine.probe.observation(1).hand}
        graceful = discarded = summoned = set_monster = set_goat = False
        first_effect = first_target = goat_chained = first_resolved = False
        book_used = book_targeted = flipped = second_effect = second_target = False
        costs = set()
        original_target = None
        for _ in range(130):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    graceful |= action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"] for c in
                                   a.parameters["cards"]} == {LIGHT, DARK}), None)
                    discarded |= action is not None
                if discarded and not summoned and action is None:
                    action = next((a for a in actions if a.kind == "special_summon"
                                   and a.parameters.get("code") == BLS), None)
                    summoned |= action is not None
            if summoned and len(costs) < 2 and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               in ({LIGHT, DARK} - costs)), action)
                if action is not None and action.kind == "select_card":
                    costs.add(action.parameters["code"])
            if obs.turn == 2 and obs.acting_player == 1:
                if not set_monster:
                    action = next((a for a in actions if a.kind == "set_monster"), None)
                    set_monster |= action is not None
                    if set_monster:
                        original_target = action.parameters["code"]
                if set_monster and not set_goat and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == SCAPEGOAT), None)
                    set_goat |= action is not None
            if obs.turn == 3 and obs.acting_player == 0:
                if set_monster and set_goat and not first_effect:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == BLS), None)
                    first_effect |= action is not None
                if first_effect and not first_target and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("controller") == 1
                                   and a.parameters.get("location") == 4), None)
                    first_target |= action is not None
                    if first_target:
                        assert "code" not in action.parameters
                if first_resolved and not book_used:
                    assert not any(a.kind == "activate" and a.parameters.get("code") == BLS
                                   for a in actions)
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == BOOK), None)
                    book_used |= action is not None
                if book_used and not book_targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == BLS
                                   and a.parameters.get("controller") == 0), None)
                    book_targeted |= action is not None
                if book_targeted and not flipped:
                    action = next((a for a in actions if a.kind == "flip_summon"
                                   and a.parameters.get("code") == BLS), action)
                    flipped |= action is not None and action.kind == "flip_summon"
                if flipped and not second_effect:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == BLS), action)
                    second_effect |= action is not None and action.kind == "activate"
                if second_effect and not second_target and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("controller") == 1
                                   and a.parameters.get("location") == 4), None)
                    second_target |= action is not None
            if first_target and obs.acting_player == 1 and not goat_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SCAPEGOAT), action)
                goat_chained |= action is not None and action.kind == "chain"
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "select_position", "pass", "end_phase")),
                              actions[0])
            obs = env.step(action)
            if goat_chained and not first_resolved and not obs.chain \
                    and original_target in {c.code for c in obs.banished[1]}:
                first_resolved = True
                assert len([c for c in obs.field if c.controller == 1
                            and c.zone == "monster"]) == 4
            if second_target and not obs.chain and obs.turn == 3:
                assert first_resolved and book_used and flipped and second_effect
                assert original_target in {c.code for c in obs.banished[1]}
                assert len([c for c in obs.field if c.controller == 1
                            and c.zone == "monster"]) == 3
                assert any(c.code == BLS and c.position == "faceup" for c in obs.field)
                assert obs.life_points == (8000, 8000)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                return
    pytest.fail(f"BLS reset stalled: summon={summoned} set={set_monster}/{set_goat} "
                f"effect={first_effect}/{first_resolved}/{second_effect}/{second_target} "
                f"book={book_used}/{book_targeted}/{flipped} turn={obs.turn}")
