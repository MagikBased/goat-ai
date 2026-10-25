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
MYSTICAL_SPACE_TYPHOON = 5318639
SOLEMN_JUDGMENT = 41420027
ROYAL_DECREE = 51452091
SCAPEGOAT = 504700123
BAZOO = 40133511
CHASER = 7359741
SHEEP_CODES = {73915052, 73915053, 73915054, 73915055}
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


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("response", [MYSTICAL_SPACE_TYPHOON,
                                      SOLEMN_JUDGMENT, ROYAL_DECREE])
def test_return_chain_distinguishes_removal_activation_negation_and_decree(
        tmp_path, response):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    negate = response == SOLEMN_JUDGMENT
    decree = response == ROYAL_DECREE
    for relative in (f"goat/c{BLS}.lua", f"official/c{GRACEFUL}.lua",
                     f"official/c{RETURN}.lua", f"official/c{response}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    lights = (LIGHT, 62651957)
    darks = (DARK, 7359741)
    filler = [code for code in VANILLA_DECK if code not in (*lights, *darks)]
    cards = (GRACEFUL, BLS,
             *(code for code in lights for _ in range(3)),
             *(code for code in darks for _ in range(3)),
             *(RETURN if code == 23771716 else code for code in filler[:26]))
    deck = tmp_path / "chaos_return.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    opposing = tmp_path / "response.ydk"
    opposing.write_text("#main\n" + "\n".join(map(str, (
        response, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(deck), str(opposing), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, BLS, RETURN, LIGHT, DARK}.issubset(c.code for c in obs.hand)
        assert response in {
            c.code for c in env.engine.probe.observation(1).hand}
        graceful = discarded = summoned = return_set = response_set = return_used = False
        response_chained = response_targeted = resolved = False
        costs = []
        for _ in range(105):
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
                                   in ({LIGHT, DARK} - set(costs))), action)
                    if action is not None and action.kind == "select_card":
                        costs.append(action.parameters["code"])
                if summoned and len(costs) == 2 and not return_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == RETURN), None)
                    return_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not response_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == response), None)
                response_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not return_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == RETURN), action)
                return_used |= action is not None and action.kind == "activate"
            if return_used and obs.acting_player == 1 and not response_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == response), action)
                response_chained |= action is not None and action.kind == "chain"
                if response_chained:
                    assert obs.life_points == (4000, 8000)
                    assert {LIGHT, DARK} == {c.code for c in obs.banished[0]}
            if response == MYSTICAL_SPACE_TYPHOON and response_chained \
                    and not response_targeted \
                    and actions[0].kind == "select_card":
                assert obs.acting_player == obs.viewer == 1
                action = next((a for a in actions if a.parameters.get("code") == RETURN
                               and a.parameters.get("controller") == 0), None)
                response_targeted |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_cards", "select_card", "place", "select_position",
                    "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if response_chained and not resolved \
                    and RETURN in {c.code for c in obs.graveyards[0]} \
                    and (response in {c.code for c in obs.graveyards[1]}
                         or (decree and any(c.code == ROYAL_DECREE
                                            and c.position == "faceup"
                                            for c in obs.field))) \
                    and not obs.chain:
                assert obs.life_points == (4000, 4000 if negate else 8000)
                revived_codes = {c.code for c in obs.field
                                 if c.controller == 0 and c.zone == "monster"
                                 and c.code != BLS}
                assert revived_codes == (set() if negate or decree else {LIGHT, DARK})
                assert {c.code for c in obs.banished[0]} == (
                    {LIGHT, DARK} if negate or decree else set())
                assert response_targeted == (response == MYSTICAL_SPACE_TYPHOON)
                resolved = True
            if resolved and obs.turn >= 4:
                assert {LIGHT, DARK} == {c.code for c in obs.banished[0]}
                assert BLS in {c.code for c in obs.field}
                assert f"official/c{RETURN}.lua" in env.engine.probe.loaded_script_sha256
                assert f"official/c{response}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Return chain did not resolve for the selected response")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("destroy_token", [False, True])
def test_return_monster_zone_capacity(tmp_path, destroy_token):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"official/c{GRACEFUL}.lua", f"official/c{BAZOO}.lua",
                     f"official/c{RETURN}.lua", f"goat/c{SCAPEGOAT}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    own_cards = (GRACEFUL, *([BAZOO] * 3), *([RETURN] * 3),
                 *(SCAPEGOAT if c == 51934376 else c for c in VANILLA_DECK[7:]))
    assert len(own_cards) == 40
    own = tmp_path / "return_one_space.ydk"
    own.write_text("#main\n" + "\n".join(map(str, own_cards)) + "\n#extra\n!side\n")
    with GoatEnvironment(str(own), "examples/decks/vanilla_probe.ydk", seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, BAZOO, RETURN, SCAPEGOAT, 62651957, 97590747}.issubset(
            c.code for c in obs.hand)
        first, second = 62651957, 97590747
        graceful = discarded = summoned = cost_paid = return_set = goat_set = False
        goat_used = chaser_summoned = attacked = target_chosen = False
        return_used = return_chosen = return_resolved = False
        for _ in range(120):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    graceful |= action is not None
                if graceful and not discarded:
                    action = next((a for a in actions if a.kind == "select_cards"
                                   and {c["code"] for c in a.parameters["cards"]}
                                   == {first, second}), action)
                    discarded |= action is not None and action.kind == "select_cards"
                if discarded and not summoned and action is None:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == BAZOO), None)
                    summoned |= action is not None
                if summoned and not cost_paid:
                    action = next((a for a in actions if a.kind in ("activate", "chain")
                                   and a.parameters.get("code") == BAZOO), action)
                    action = next((a for a in actions if a.kind == "select_cards"
                                   and {c["code"] for c in a.parameters["cards"]}
                                   == {first, second}), action)
                    cost_paid |= action is not None and action.kind == "select_cards"
                if cost_paid and not return_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == RETURN), None)
                    return_set |= action is not None
                if return_set and not goat_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == SCAPEGOAT), None)
                    goat_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 0 and goat_set and not goat_used:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SCAPEGOAT), action)
                goat_used |= action is not None and action.kind == "chain"
            if obs.turn == 2 and obs.acting_player == 1:
                if not chaser_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == CHASER), None)
                    chaser_summoned |= action is not None
                if destroy_token and chaser_summoned and obs.phase == "main1" \
                        and action is None:
                    action = next((a for a in actions if a.kind == "battle_phase"), None)
                if goat_used and obs.phase == "battle_start" and not attacked:
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == CHASER), None)
                    attacked |= action is not None
                if attacked and not target_chosen and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   in SHEEP_CODES and a.parameters.get("controller") == 0),
                                  None)
                    target_chosen |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and obs.phase == "main1":
                if not return_used:
                    assert sum(c.controller == 0 and c.zone == "monster"
                               for c in obs.field) == (4 if destroy_token else 5)
                    assert sum(c.code in SHEEP_CODES for c in obs.field) == (
                        3 if destroy_token else 4)
                    assert {first, second} == {c.code for c in obs.banished[0]}
                    if not destroy_token:
                        assert goat_used and chaser_summoned and return_set
                        assert not any(a.kind == "activate" and
                                       a.parameters.get("code") == RETURN for a in actions)
                        assert obs.life_points == (8000, 8000)
                        assert f"official/c{RETURN}.lua" in (
                            env.engine.probe.loaded_script_sha256)
                        return
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == RETURN), None)
                    return_used |= action is not None
                if return_used and not return_chosen:
                    action = next((a for a in actions if a.kind == "select_card"
                                   and a.parameters.get("code") == first), action)
                    return_chosen |= action is not None and action.kind == "select_card"
                    if return_chosen:
                        assert {a.parameters["code"] for a in actions
                                if a.kind == "select_card"} == {first, second}
                        assert not any(a.kind == "select_cards" for a in actions)
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_cards", "select_card", "place", "select_position",
                    "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if return_chosen and not return_resolved and not obs.chain \
                    and RETURN in {c.code for c in obs.graveyards[0]}:
                assert obs.life_points == (4000, 8000)
                assert sum(c.controller == 0 and c.zone == "monster"
                           for c in obs.field) == 5
                assert first in {c.code for c in obs.field}
                assert {c.code for c in obs.banished[0]} == {second}
                return_resolved = True
            if return_resolved and obs.turn >= 4:
                assert {c.code for c in obs.banished[0]} == {first, second}
                assert sum(c.code in SHEEP_CODES for c in obs.field) == 3
                assert BAZOO in {c.code for c in obs.field}
                assert f"official/c{RETURN}.lua" in env.engine.probe.loaded_script_sha256
                return
    pytest.fail("Return's Monster Zone capacity line did not finish")
