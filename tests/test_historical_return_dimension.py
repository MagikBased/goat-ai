"""Return from the Different Dimension revives banished Chaos costs temporarily."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

BLS = 504700118
GRACEFUL = 79571449
RETURN = 27174286
BOOK_OF_MOON = 14087893
LIGHT = 15025844
DARK = 49881766


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("set_revived_monster", [False, True])
def test_return_revives_chaos_costs_with_book_end_phase_exception(
    tmp_path, set_revived_monster,
):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{BLS}.lua", f"official/c{GRACEFUL}.lua",
                     f"official/c{RETURN}.lua", f"official/c{BOOK_OF_MOON}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    lights = (LIGHT, 62651957)
    darks = (DARK, 7359741)
    filler = [code for code in VANILLA_DECK if code not in (*lights, *darks)]
    cards = (GRACEFUL, BLS,
             *(code for code in lights for _ in range(3)),
             *(code for code in darks for _ in range(3)),
             *(RETURN if code == 23771716 else code for code in filler[:26]))
    assert len(cards) == 40
    assert cards.count(RETURN) == 3
    deck = tmp_path / "chaos_return.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    opponent = tmp_path / "book.ydk"
    opponent.write_text("#main\n" + "\n".join(map(str, (
        BOOK_OF_MOON, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(deck), str(opponent), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, BLS, RETURN, LIGHT, DARK}.issubset(c.code for c in obs.hand)
        assert BOOK_OF_MOON in {c.code for c in env.engine.probe.observation(1).hand}
        graceful = discarded = summoned = trap_set = return_used = False
        return_resolved = book_set = book_used = book_targeted = False
        summon_costs = []
        for _ in range(100):
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
                if summoned and len(summon_costs) < 2 and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   in ({LIGHT, DARK} - set(summon_costs))), action)
                    if action is not None and action.kind == "select_card":
                        summon_costs.append(action.parameters["code"])
                if summoned and len(summon_costs) == 2 and not trap_set \
                        and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == RETURN), None)
                    trap_set |= action is not None
            if set_revived_monster and obs.turn == 2 and obs.acting_player == 1 \
                    and not book_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == BOOK_OF_MOON), None)
                book_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not return_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == RETURN), action)
                return_used |= action is not None and action.kind == "activate"
            if (set_revived_monster and return_resolved and obs.turn == 3
                    and obs.acting_player == 1 and not book_used):
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK_OF_MOON), None)
                book_used |= action is not None
            if book_used and not book_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == LIGHT
                               and a.parameters.get("controller") == 0), action)
                book_targeted |= action is not None and action.kind == "select_card"
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_cards", "select_card", "place", "select_position",
                    "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if return_used and not return_resolved \
                    and RETURN in {c.code for c in obs.graveyards[0]}:
                assert obs.life_points == (4000, 8000)
                assert {LIGHT, DARK} == {c.code for c in obs.field
                                         if c.controller == 0 and c.zone == "monster"
                                         and c.code != BLS}
                assert {c.code for c in obs.banished[0]} == set()
                return_resolved = True
            if return_resolved and obs.turn >= 4:
                assert obs.life_points == (4000, 8000)
                assert BLS in {c.code for c in obs.field}
                if set_revived_monster:
                    assert book_set and book_used and book_targeted
                    assert {c.code for c in obs.banished[0]} == {DARK}
                    own = env.engine.probe.observation(0)
                    assert any(c.code == LIGHT and c.position == "facedown"
                               for c in own.field)
                    assert BOOK_OF_MOON in {c.code for c in obs.graveyards[1]}
                else:
                    assert {LIGHT, DARK} == {c.code for c in obs.banished[0]}
                    assert not any(c.code in {LIGHT, DARK} for c in obs.field)
                assert f"official/c{RETURN}.lua" in env.engine.probe.loaded_script_sha256
                return
    pytest.fail("Return did not revive and rebanish both Chaos cost monsters")
