"""Bazoo's Graveyard banish cost feeds Return in Chaos Return."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

BAZOO = 40133511
GRACEFUL = 79571449
RETURN = 27174286
FIRST = 62651957
SECOND = 97590747
THIRD = 51934376
MECHANICALCHASER = 7359741
SKILL_DRAIN = 82732705
CALL_OF_THE_HAUNTED = 97077563
KYCOO = 88240808


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_bazoo_banish_cost_boost_and_return_revival(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (BAZOO, GRACEFUL, RETURN):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    deck = tmp_path / "bazoo_return.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL, *([BAZOO] * 3), *([RETURN] * 3), *VANILLA_DECK[7:])))
                    + "\n#extra\n!side\n")
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, BAZOO, RETURN, FIRST, SECOND}.issubset(
            c.code for c in obs.hand)
        graceful = discarded = summoned = bazoo_used = cost_paid = False
        trap_set = boosted = expired = return_used = return_resolved = False
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
                                   a.parameters["cards"]} == {FIRST, SECOND}), None)
                    discarded |= action is not None
                if discarded and not summoned and action is None:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == BAZOO), None)
                    summoned |= action is not None
                if summoned and not bazoo_used and action is None:
                    action = next((a for a in actions if a.kind in ("activate", "chain")
                                   and a.parameters.get("code") == BAZOO), None)
                    bazoo_used |= action is not None
                if bazoo_used and not cost_paid:
                    action = next((a for a in actions if a.kind == "select_cards"
                                   and {c["code"] for c in
                                   a.parameters["cards"]} == {FIRST, SECOND}), action)
                    if action is not None and action.kind == "select_cards":
                        assert len(actions) == 3
                        assert {a.parameters["code"] for a in actions
                                if a.kind == "select_card"} == {FIRST, SECOND}
                    cost_paid |= action is not None and action.kind == "select_cards"
                if boosted and not trap_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == RETURN), None)
                    trap_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not return_used:
                if not expired:
                    assert any(c.code == BAZOO and c.attack == 1600 for c in obs.field)
                    expired = True
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == RETURN), action)
                return_used |= action is not None and action.kind == "activate"
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_cards", "select_card", "place", "select_position",
                    "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if cost_paid and not boosted and any(
                    c.code == BAZOO and c.attack == 2200 for c in obs.field):
                assert {c.code for c in obs.banished[0]} == {FIRST, SECOND}
                boosted = True
            if return_used and not return_resolved \
                    and RETURN in {c.code for c in obs.graveyards[0]}:
                assert obs.life_points == (4000, 8000)
                assert {FIRST, SECOND}.issubset({c.code for c in obs.field})
                assert any(c.code == BAZOO and c.attack == 1600 for c in obs.field)
                return_resolved = True
            if return_resolved and obs.turn >= 4:
                assert graceful and discarded and summoned and bazoo_used
                assert cost_paid and boosted and trap_set and expired
                assert {c.code for c in obs.banished[0]} == {FIRST, SECOND}
                assert any(c.code == BAZOO for c in obs.field)
                assert not any(c.code in (FIRST, SECOND) for c in obs.field)
                assert {f"official/c{code}.lua" for code in (BAZOO, RETURN)}.issubset(
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail(f"Bazoo/Return line did not resolve: turn={obs.turn} "
                f"phase={obs.phase} flags={graceful, discarded, summoned, bazoo_used, cost_paid, trap_set, boosted, expired, return_used, return_resolved} "
                f"field={[(c.code, c.attack) for c in obs.field]} "
                f"banished={[c.code for c in obs.banished[0]]}")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_bazoo_three_graveyard_cost_persists_through_opponent_turn(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (BAZOO, GRACEFUL):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    own = tmp_path / "bazoo_three.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL, *([BAZOO] * 3), *([RETURN] * 3), *VANILLA_DECK[7:])))
                   + "\n#extra\n!side\n")
    opposing = tmp_path / "chaser.ydk"
    opposing.write_text("#main\n" + "\n".join(map(str, (
        *([69140098] * 3), *(c for c in VANILLA_DECK if c != 69140098))))
                        + "\n#extra\n!side\n")
    with GoatEnvironment(str(own), str(opposing), seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, BAZOO, FIRST, SECOND, THIRD}.issubset(c.code for c in obs.hand)
        assert MECHANICALCHASER in {
            c.code for c in env.engine.probe.observation(1).hand}
        graceful = discarded = third_summoned = chaser_summoned = False
        battle = attacked = target = bazoo_summoned = bazoo_used = cost_paid = False
        boosted = opponent_turn_checked = False
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
                                   a.parameters["cards"]} == {FIRST, SECOND}), None)
                    discarded |= action is not None
                if discarded and not third_summoned and action is None:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == THIRD), None)
                    third_summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not chaser_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == MECHANICALCHASER), None)
                    chaser_summoned |= action is not None
                if chaser_summoned and obs.phase == "main1" and not battle \
                        and action is None:
                    action = next((a for a in actions if a.kind == "battle_phase"), None)
                    battle |= action is not None
                if battle and obs.phase == "battle_start" and not attacked:
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == MECHANICALCHASER), None)
                    attacked |= action is not None
                if attacked and not target and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == THIRD
                                   and a.parameters.get("controller") == 0), None)
                    target |= action is not None
            if obs.turn == 3 and obs.acting_player == 0:
                if not bazoo_summoned:
                    assert obs.life_points == (7850, 8000)
                    assert {FIRST, SECOND, THIRD}.issubset(
                        c.code for c in obs.graveyards[0])
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == BAZOO), None)
                    bazoo_summoned |= action is not None
                if bazoo_summoned and not bazoo_used and action is None:
                    action = next((a for a in actions if a.kind in ("activate", "chain")
                                   and a.parameters.get("code") == BAZOO), None)
                    bazoo_used |= action is not None
                if bazoo_used and not cost_paid:
                    action = next((a for a in actions if a.kind == "select_cards"
                                   and {c["code"] for c in a.parameters["cards"]}
                                   == {FIRST, SECOND, THIRD}), action)
                    cost_paid |= action is not None and action.kind == "select_cards"
            if obs.turn == 4 and obs.acting_player == 1 and obs.phase == "main1" \
                    and not opponent_turn_checked:
                assert any(c.code == BAZOO and c.attack == 2500 for c in obs.field)
                assert {c.code for c in obs.banished[0]} == {FIRST, SECOND, THIRD}
                opponent_turn_checked = True
            if obs.turn == 5 and obs.acting_player == 0 and obs.phase == "main1":
                assert boosted and opponent_turn_checked and cost_paid
                assert any(c.code == BAZOO and c.attack == 1600 for c in obs.field)
                assert {c.code for c in obs.banished[0]} == {FIRST, SECOND, THIRD}
                assert f"official/c{BAZOO}.lua" in env.engine.probe.loaded_script_sha256
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_cards", "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if cost_paid and not boosted and any(
                    c.code == BAZOO and c.attack == 2500 for c in obs.field):
                assert {c.code for c in obs.banished[0]} == {FIRST, SECOND, THIRD}
                boosted = True
    pytest.fail("Bazoo three-card cost and ATK duration did not finish")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_skill_drain_chained_after_bazoo_cost_prevents_attack_boost(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (BAZOO, GRACEFUL, SKILL_DRAIN):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    own = tmp_path / "bazoo.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL, *([BAZOO] * 3), *([RETURN] * 3), *VANILLA_DECK[7:])))
                   + "\n#extra\n!side\n")
    other = tmp_path / "drain.ydk"
    other.write_text("#main\n" + "\n".join(map(str, (
        SKILL_DRAIN if code == MECHANICALCHASER else code
        for code in VANILLA_DECK))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(own), str(other), seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, BAZOO, FIRST, SECOND}.issubset(c.code for c in obs.hand)
        assert SKILL_DRAIN in {c.code for c in env.engine.probe.observation(1).hand}
        graceful = discarded = trap_set = summoned = bazoo_used = cost_paid = False
        drain_chained = False
        for _ in range(70):
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
                                   == {FIRST, SECOND}), action)
                    discarded |= action is not None and action.kind == "select_cards"
            if obs.turn == 2 and obs.acting_player == 1 and not trap_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SKILL_DRAIN), None)
                trap_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0:
                if not summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == BAZOO), None)
                    summoned |= action is not None
                if summoned and not bazoo_used and action is None:
                    action = next((a for a in actions if a.kind in ("activate", "chain")
                                   and a.parameters.get("code") == BAZOO), None)
                    bazoo_used |= action is not None
                if bazoo_used and not cost_paid:
                    action = next((a for a in actions if a.kind == "select_cards"
                                   and {c["code"] for c in a.parameters["cards"]}
                                   == {FIRST, SECOND}), action)
                    cost_paid |= action is not None and action.kind == "select_cards"
            if cost_paid and obs.acting_player == 1 and not drain_chained:
                assert {c.code for c in obs.banished[0]} == {FIRST, SECOND}
                assert any(c.code == BAZOO and c.attack == 1600 for c in obs.field)
                assert [link.card_code for link in obs.chain] == [BAZOO]
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SKILL_DRAIN), None)
                drain_chained |= action is not None
                assert drain_chained
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_cards", "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if drain_chained and not obs.chain and obs.turn == 3 and obs.phase == "main1" \
                    and obs.acting_player == 0 \
                    and any(c.code == SKILL_DRAIN for c in obs.field):
                assert obs.life_points == (8000, 7000)
                assert {c.code for c in obs.banished[0]} == {FIRST, SECOND}
                assert any(c.code == BAZOO and c.attack == 1600 for c in obs.field)
                assert {f"official/c{code}.lua" for code in (BAZOO, SKILL_DRAIN)}.issubset(
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Skill Drain did not resolve after Bazoo's banish cost")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("kycoo_already_faceup", [False, True])
def test_kycoo_timing_controls_bazoo_banish_cost(tmp_path, kycoo_already_faceup):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (BAZOO, GRACEFUL, CALL_OF_THE_HAUNTED, KYCOO):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    own = tmp_path / "bazoo.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL, *([BAZOO] * 3), *([RETURN] * 3), *VANILLA_DECK[7:])))
                   + "\n#extra\n!side\n")
    opposing_cards = list(VANILLA_DECK)
    opposing_cards[9] = CALL_OF_THE_HAUNTED
    opposing_cards[20] = GRACEFUL
    opposing_cards[25] = KYCOO
    opposing = tmp_path / "kycoo_call.ydk"
    opposing.write_text("#main\n" + "\n".join(map(str, opposing_cards))
                        + "\n#extra\n!side\n")
    with GoatEnvironment(str(own), str(opposing), seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, BAZOO, FIRST, SECOND}.issubset(c.code for c in obs.hand)
        assert {GRACEFUL, CALL_OF_THE_HAUNTED, KYCOO, 23771716}.issubset(
            c.code for c in env.engine.probe.observation(1).hand)
        own_graceful = own_discarded = opposing_graceful = opposing_discarded = False
        call_set = kycoo_summoned = bazoo_summoned = bazoo_used = False
        cost_paid = call_chained = False
        kycoo_targeted = False
        for _ in range(95):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not own_graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    own_graceful |= action is not None
                if own_graceful and not own_discarded:
                    action = next((a for a in actions if a.kind == "select_cards"
                                   and {c["code"] for c in a.parameters["cards"]}
                                   == {FIRST, SECOND}), action)
                    own_discarded |= action is not None and action.kind == "select_cards"
            if obs.turn == 2 and obs.acting_player == 1:
                if kycoo_already_faceup and not kycoo_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == KYCOO), None)
                    kycoo_summoned |= action is not None
                if not kycoo_already_faceup and not opposing_graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    opposing_graceful |= action is not None
                if not kycoo_already_faceup and opposing_graceful \
                        and not opposing_discarded:
                    action = next((a for a in actions if a.kind == "select_cards"
                                   and {c["code"] for c in a.parameters["cards"]}
                                   == {KYCOO, 23771716}), action)
                    opposing_discarded |= action is not None and action.kind == "select_cards"
                if not kycoo_already_faceup and opposing_discarded \
                        and not call_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == CALL_OF_THE_HAUNTED), None)
                    call_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0:
                if not bazoo_summoned:
                    if not kycoo_already_faceup:
                        assert KYCOO in {c.code for c in obs.graveyards[1]}
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == BAZOO), None)
                    bazoo_summoned |= action is not None
                if kycoo_already_faceup and bazoo_summoned and action is None \
                        and any(a.kind == "end_phase" for a in actions):
                    assert kycoo_summoned
                    assert any(c.code == KYCOO and c.controller == 1 for c in obs.field)
                    assert any(c.code == BAZOO and c.attack == 1600 for c in obs.field)
                    assert {FIRST, SECOND}.issubset(c.code for c in obs.graveyards[0])
                    assert not any(a.kind in ("activate", "chain") and
                                   a.parameters.get("code") == BAZOO for a in actions)
                    assert not obs.banished[0]
                    return
                if bazoo_summoned and not bazoo_used and action is None:
                    action = next((a for a in actions if a.kind in ("activate", "chain")
                                   and a.parameters.get("code") == BAZOO), None)
                    bazoo_used |= action is not None
                if bazoo_used and not cost_paid:
                    action = next((a for a in actions if a.kind == "select_cards"
                                   and {c["code"] for c in a.parameters["cards"]}
                                   == {FIRST, SECOND}), action)
                    cost_paid |= action is not None and action.kind == "select_cards"
            if cost_paid and obs.acting_player == 1 and not call_chained:
                assert {c.code for c in obs.banished[0]} == {FIRST, SECOND}
                assert [link.card_code for link in obs.chain] == [BAZOO]
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == CALL_OF_THE_HAUNTED), None)
                call_chained |= action is not None
                assert call_chained
            if call_chained and not kycoo_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == KYCOO
                               and a.parameters.get("controller") == 1), None)
                kycoo_targeted |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_cards", "select_card", "place", "select_position",
                    "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if kycoo_targeted and not obs.chain and obs.turn == 3 \
                    and obs.phase == "main1" and obs.acting_player == 0:
                assert obs.life_points == (8000, 8000)
                assert {c.code for c in obs.banished[0]} == {FIRST, SECOND}
                assert any(c.code == BAZOO and c.attack == 2200 for c in obs.field)
                assert any(c.code == KYCOO and c.controller == 1 for c in obs.field)
                assert {f"official/c{code}.lua" for code in (
                    BAZOO, CALL_OF_THE_HAUNTED, KYCOO)}.issubset(
                        env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Kycoo/Call chain did not finish after Bazoo's cost")
