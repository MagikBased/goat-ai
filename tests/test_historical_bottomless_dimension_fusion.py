"""Bottomless handles simultaneous Dimension Fusion Summons and Book protection."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

BLS = 504700118
GRACEFUL = 79571449
DIMENSION_FUSION = 23557835
BOTTOMLESS = 504700052
BOOK = 14087893
LIGHT = 62651957  # X-Head Cannon, 1800 ATK
DARK = 49881766  # Archfiend Soldier, 1900 ATK


def _decks(tmp_path):
    lights = (LIGHT, 15025844)
    darks = (DARK, 7359741)
    filler = [code for code in VANILLA_DECK if code not in (*lights, *darks)]
    own_cards = (GRACEFUL, BLS,
                 *(code for code in lights for _ in range(3)),
                 *(code for code in darks for _ in range(3)),
                 *(DIMENSION_FUSION if code == 23771716 else
                   BOOK if code == 69140098 else code for code in filler[:26]))
    assert len(own_cards) == 40
    own = tmp_path / "dimension_fusion_book.ydk"
    other = tmp_path / "bottomless.ydk"
    own.write_text("#main\n" + "\n".join(map(str, own_cards)) + "\n#extra\n!side\n")
    other.write_text("#main\n" + "\n".join(map(str, (
        BOTTOMLESS, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    return str(own), str(other)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
@pytest.mark.parametrize("book_response", [False, True])
def test_bottomless_simultaneous_summon_with_book_response(tmp_path, book_response):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    required = (f"goat/c{BLS}.lua", f"goat/c{BOTTOMLESS}.lua",
                *(f"official/c{code}.lua" for code in (GRACEFUL, DIMENSION_FUSION, BOOK)))
    if any(not (root / "scripts" / path).is_file() for path in required):
        pytest.skip("required card script not installed")
    own, other = _decks(tmp_path)
    with GoatEnvironment(own, other, seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, BLS, DIMENSION_FUSION, LIGHT, DARK} <= {
            card.code for card in obs.hand}
        assert BOTTOMLESS in {card.code for card in
                              env.engine.probe.observation(1).hand}
        graceful = discarded = summoned = book_set = bottomless_set = False
        fusion_used = bottomless_used = book_used = book_targeted = checked = False
        summon_costs = []
        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"dimension_bottomless_book_{book_response}.json"
                write_trajectory(path, env.trajectory())
                replay = read_trajectory(path)
                assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(
                    replay.decisions)
                audit_trajectory_visibility(replay)
                return
            actions = env.legal_actions()
            action = None
            if not checked and obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate" and
                                   a.parameters.get("code") == GRACEFUL), None)
                    graceful |= action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {card["code"] for card in
                                   a.parameters["cards"]} == {LIGHT, DARK}), None)
                    discarded = action is not None
                if discarded and not summoned and action is None:
                    action = next((a for a in actions if a.kind == "special_summon" and
                                   a.parameters.get("code") == BLS), None)
                    summoned = action is not None
                if summoned and len(summon_costs) < 2 and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   in ({LIGHT, DARK} - set(summon_costs))), action)
                    if action is not None and action.kind == "select_card":
                        summon_costs.append(action.parameters["code"])
                if len(summon_costs) == 2 and not book_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap" and
                                   a.parameters.get("code") == BOOK), None)
                    book_set = action is not None
            if not checked and obs.turn == 2 and obs.acting_player == 1 \
                    and not bottomless_set:
                action = next((a for a in actions if a.kind == "set_spell_trap" and
                               a.parameters.get("code") == BOTTOMLESS), None)
                bottomless_set = action is not None
            if not checked and obs.turn == 3 and obs.acting_player == 0 \
                    and not fusion_used:
                assert book_set and bottomless_set and set(summon_costs) == {LIGHT, DARK}
                action = next((a for a in actions if a.kind == "activate" and
                               a.parameters.get("code") == DIMENSION_FUSION), None)
                fusion_used = action is not None
            if fusion_used and obs.acting_player == 1 and not bottomless_used:
                action = next((a for a in actions if a.kind == "chain" and
                               a.parameters.get("code") == BOTTOMLESS), action)
                bottomless_used = action is not None and action.kind == "chain"
                if bottomless_used:
                    assert not obs.chain
                    assert {LIGHT, DARK} <= {c.code for c in obs.field
                                              if c.controller == 0 and c.zone == "monster"}
            if bottomless_used and book_response and obs.acting_player == 0 \
                    and not book_used:
                action = next((a for a in actions if a.kind == "chain" and
                               a.parameters.get("code") == BOOK), action)
                book_used = action is not None and action.kind == "chain"
            if book_used and not book_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card" and
                               a.parameters.get("code") == DARK and
                               a.parameters.get("controller") == 0), None)
                book_targeted = action is not None
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "select_cards", "select_card", "place", "select_position",
                    "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if bottomless_used and not checked and BOTTOMLESS in {
                    c.code for c in obs.graveyards[1]} and not obs.chain:
                assert obs.life_points == (6000, 8000)
                own_field = {c.code: c for c in obs.field
                             if c.controller == 0 and c.zone == "monster"}
                assert BLS in own_field
                assert LIGHT not in own_field
                assert LIGHT in {c.code for c in obs.banished[0]}
                assert DARK not in obs.graveyards[0]
                if book_response:
                    assert book_targeted and DARK in own_field
                    assert own_field[DARK].position == "facedown"
                    assert DARK not in {c.code for c in obs.banished[0]}
                    opponent = env.engine.probe.observation(1)
                    assert any(c.controller == 0 and c.code is None and
                               c.position == "facedown" for c in opponent.field)
                    assert any(c.controller == 0 and c.code == DARK for c in
                               opponent.known_opponent_field_cards)
                else:
                    assert DARK not in own_field
                    assert {LIGHT, DARK} <= {c.code for c in obs.banished[0]}
                assert {f"goat/c{BOTTOMLESS}.lua", f"official/c{DIMENSION_FUSION}.lua"} \
                    <= set(env.engine.probe.loaded_script_sha256)
                checked = True
    pytest.fail("Bottomless/Dimension Fusion branch did not finish")
