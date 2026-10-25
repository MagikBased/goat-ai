"""Dimension Fusion revives banished Chaos costs without an End Phase return."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

BLS = 504700118
GRACEFUL_CHARITY = 79571449
DIMENSION_FUSION = 23557835
LIGHT = 15025844
DARK = 49881766
DD_WARRIOR_LADY = 7572887
GEMINI_ELF = 69140098


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_dimension_fusion_revives_both_chaos_costs_persistently(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{BLS}.lua", f"official/c{GRACEFUL_CHARITY}.lua",
                     f"official/c{DIMENSION_FUSION}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    lights = (LIGHT, 62651957)
    darks = (DARK, 7359741)
    filler = [code for code in VANILLA_DECK if code not in (*lights, *darks)]
    cards = (GRACEFUL_CHARITY, BLS,
             *(code for code in lights for _ in range(3)),
             *(code for code in darks for _ in range(3)),
             *(DIMENSION_FUSION if code == 23771716 else code
               for code in filler[:26]))
    assert len(cards) == 40 and cards.count(DIMENSION_FUSION) == 3
    deck = tmp_path / "dimension_fusion.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL_CHARITY, BLS, DIMENSION_FUSION,
                LIGHT, DARK}.issubset(c.code for c in obs.hand)
        graceful = discarded = summoned = fusion_used = fusion_resolved = False
        summon_costs = []
        for _ in range(85):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not summoned and obs.phase == "main1":
                    assert not any(a.kind == "activate" and a.parameters.get("code")
                                   == DIMENSION_FUSION for a in actions)
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL_CHARITY), None)
                    graceful |= action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"] for c in
                                   a.parameters["cards"]} == {LIGHT, DARK}), None)
                    discarded = action is not None
                if discarded and not summoned and action is None:
                    action = next((a for a in actions if a.kind == "special_summon"
                                   and a.parameters.get("code") == BLS), None)
                    summoned = action is not None
                if summoned and len(summon_costs) < 2 \
                        and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   in ({LIGHT, DARK} - set(summon_costs))), action)
                    if action is not None and action.kind == "select_card":
                        summon_costs.append(action.parameters["code"])
                if len(summon_costs) == 2 and not fusion_used and action is None:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == DIMENSION_FUSION), None)
                    fusion_used = action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_cards", "select_card", "place", "select_position",
                    "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if fusion_used and not fusion_resolved and DIMENSION_FUSION in {
                    c.code for c in obs.graveyards[0]}:
                assert obs.life_points == (6000, 8000)
                assert {BLS, LIGHT, DARK} <= {
                    c.code for c in obs.field if c.controller == 0
                    and c.zone == "monster"}
                assert not obs.banished[0]
                assert not obs.chain
                fusion_resolved = True
            if fusion_resolved and obs.turn >= 3:
                assert obs.life_points == (6000, 8000)
                assert {BLS, LIGHT, DARK} <= {
                    c.code for c in obs.field if c.controller == 0
                    and c.zone == "monster"}
                assert not obs.banished[0]
                assert {f"goat/c{BLS}.lua",
                        f"official/c{GRACEFUL_CHARITY}.lua",
                        f"official/c{DIMENSION_FUSION}.lua"}.issubset(
                            env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Dimension Fusion did not leave both Chaos costs on the field")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_dimension_fusion_revives_one_banished_monster_for_each_player(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (DD_WARRIOR_LADY, DIMENSION_FUSION):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    deck = tmp_path / "warrior_dimension_fusion.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        DD_WARRIOR_LADY, DIMENSION_FUSION, DIMENSION_FUSION,
        DIMENSION_FUSION, *VANILLA_DECK[4:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=5,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {DD_WARRIOR_LADY, DIMENSION_FUSION}.issubset(
            c.code for c in obs.hand)
        assert GEMINI_ELF in {
            c.code for c in env.engine.probe.observation(1).hand}
        warrior_set = elf_summoned = attacked = banish_chosen = fusion_used = False
        for _ in range(95):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not warrior_set:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == DD_WARRIOR_LADY), None)
                warrior_set = action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not elf_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == GEMINI_ELF), None)
                    elf_summoned = action is not None
                if elf_summoned and not attacked and action is None:
                    action = next((a for a in actions if a.kind in (
                        "battle_phase", "attack") and (a.kind != "attack" or
                        a.parameters.get("code") == GEMINI_ELF)), None)
                    if action is not None and action.kind == "attack":
                        target = next(c for c in obs.field if c.controller == 0
                                      and c.zone == "monster")
                        assert target.code is None and target.position == "facedown"
                    attacked |= action is not None and action.kind == "attack"
            if attacked and obs.acting_player == 0 and not banish_chosen:
                action = next((a for a in actions if a.parameters.get("code")
                               == DD_WARRIOR_LADY and a.kind in (
                                   "chain", "yes", "activate")), None)
                banish_chosen = action is not None
            if obs.turn == 3 and obs.acting_player == 0 and banish_chosen \
                    and not fusion_used:
                assert {DD_WARRIOR_LADY} == {c.code for c in obs.banished[0]}
                assert {GEMINI_ELF} == {c.code for c in obs.banished[1]}
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == DIMENSION_FUSION), None)
                fusion_used = action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "select_position", "pass",
                    "main2", "end_phase")), actions[0])
            obs = env.step(action)
            if fusion_used and DIMENSION_FUSION in {c.code for c in obs.graveyards[0]} \
                    and not obs.chain:
                assert obs.life_points == (6000, 8000)
                assert {DD_WARRIOR_LADY} == {c.code for c in obs.field
                                             if c.controller == 0
                                             and c.zone == "monster"}
                assert {GEMINI_ELF} == {c.code for c in obs.field
                                        if c.controller == 1
                                        and c.zone == "monster"}
                assert not obs.banished[0] and not obs.banished[1]
                assert {f"official/c{code}.lua" for code in (
                    DD_WARRIOR_LADY, DIMENSION_FUSION)}.issubset(
                        env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Dimension Fusion did not revive both players' banished monsters")
