"""Book of Moon saves Sorcerer's target, but using the effect still locks attacks."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SORCERER = 9596126
GRACEFUL = 79571449
BOOK = 14087893
LIGHT = 15025844
DARK = 7359741


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("respond", [False, True])
def test_book_on_sorcerer_banish_target_saves_target_but_locks_sorcerer(
        tmp_path, respond):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{SORCERER}.lua", f"official/c{GRACEFUL}.lua",
               f"official/c{BOOK}.lua"}
    if any(not (root / "scripts" / relative).is_file() for relative in scripts):
        pytest.skip("required card script not installed")
    lights = (LIGHT, 62651957)
    darks = (49881766, DARK)
    filler = [code for code in VANILLA_DECK if code not in (*lights, *darks)]
    own = tmp_path / "sorcerer.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL, SORCERER, *(code for code in lights for _ in range(3)),
        *(code for code in darks for _ in range(3)), *filler[:26])))
        + "\n#extra\n!side\n")
    opponent = tmp_path / "book.ydk"
    opponent.write_text("#main\n" + "\n".join(map(str, (
        *([BOOK] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(opponent), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, SORCERER, LIGHT, DARK} <= {c.code for c in obs.hand}
        assert BOOK in {c.code for c in env.engine.probe.observation(1).hand}
        graceful = discarded = summoned = defender_summoned = book_set = False
        activated = targeted = response_made = book_targeted = checked = False
        battle_checked = False
        costs = set()
        defender_code = None
        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(5000):
            if env.is_terminal():
                assert checked and battle_checked
                path = tmp_path / f"sorcerer_book_{respond}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    graceful |= action is not None
                elif not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"] for c in
                                   a.parameters["cards"]} == {LIGHT, DARK}), None)
                    discarded |= action is not None
                elif discarded and not summoned:
                    action = next((a for a in actions if a.kind == "special_summon"
                                   and a.parameters.get("code") == SORCERER), None)
                    summoned |= action is not None
            if summoned and len(costs) < 2 and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               in ({LIGHT, DARK} - costs)), action)
                if action is not None and action.kind == "select_card":
                    costs.add(action.parameters["code"])
            if obs.turn == 2 and obs.acting_player == 1:
                if not defender_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        defender_code = action.parameters["code"]
                        defender_summoned = True
                elif not book_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOOK), None)
                    book_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and book_set:
                if not activated:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == SORCERER), None)
                    activated |= action is not None
                elif not targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == defender_code and a.parameters.get("controller") == 1), None)
                    targeted |= action is not None
            if targeted and obs.acting_player == 1 and not response_made:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK), None)
                if option is not None:
                    assert [link.card_code for link in obs.chain] == [SORCERER]
                    action = option if respond else next(a for a in actions
                                                        if a.kind == "pass")
                    response_made = True
            if response_made and respond and not book_targeted \
                    and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == defender_code and a.parameters.get("controller") == 1), None)
                book_targeted |= action is not None
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "select_position", "pass", "end_phase")),
                              actions[0])
            if checked and not battle_checked and obs.turn == 3 \
                    and obs.acting_player == 0:
                assert not any(a.kind == "activate"
                               and a.parameters.get("code") == SORCERER
                               for a in actions)
                if obs.phase == "main1":
                    action = next((a for a in actions if a.kind == "battle_phase"), action)
                if obs.phase == "battle_start":
                    assert not any(a.kind == "attack"
                                   and a.parameters.get("code") == SORCERER
                                   for a in actions)
                    battle_checked = True
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if response_made and not checked and not obs.chain \
                    and obs.turn == 3 and obs.phase == "main1" \
                    and obs.acting_player == 0:
                assert {LIGHT, DARK} <= {c.code for c in obs.banished[0]}
                assert any(c.code == SORCERER and c.controller == 0 for c in obs.field)
                if respond:
                    assert book_targeted
                    assert BOOK in {c.code for c in obs.graveyards[1]}
                    assert defender_code not in {c.code for c in obs.banished[1]}
                    hidden = next(c for c in obs.field if c.controller == 1
                                  and c.zone == "monster")
                    assert hidden.code is None and hidden.position == "facedown"
                    assert (1, "monster", hidden.sequence, defender_code) in {
                        (c.controller, c.zone, c.sequence, c.code)
                        for c in obs.known_opponent_field_cards}
                else:
                    assert defender_code in {c.code for c in obs.banished[1]}
                    assert BOOK not in {c.code for c in obs.graveyards[1]}
                assert obs.life_points == (8000, 8000)
                loaded = env.engine.probe.loaded_script_sha256
                assert {f"official/c{SORCERER}.lua",
                        f"official/c{GRACEFUL}.lua"} <= loaded.keys()
                if respond:
                    assert f"official/c{BOOK}.lua" in loaded
                checked = True
    pytest.fail("Sorcerer / Book duel did not finish")
