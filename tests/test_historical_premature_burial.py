"""Premature Burial leaves different outcomes when its equip link is broken."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

GRACEFUL_CHARITY = 79571449
PREMATURE_BURIAL = 70828912
BOOK_OF_MOON = 14087893
MYSTICAL_SPACE_TYPHOON = 5318639
MYSTICAL_ELF = 15025844
SECOND_DISCARD = 79182538
SOLEMN_JUDGMENT = 41420027


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("response", [BOOK_OF_MOON, MYSTICAL_SPACE_TYPHOON])
def test_premature_equip_break_by_flip_or_destruction(tmp_path, response):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (GRACEFUL_CHARITY, PREMATURE_BURIAL, response):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    deck = tmp_path / "premature.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL_CHARITY, PREMATURE_BURIAL, response, *VANILLA_DECK[3:])))
                    + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        graceful = discarded = premature = response_used = False
        for _ in range(45):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0:
                if not graceful:
                    option = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL_CHARITY), None)
                    if option is not None:
                        action = option
                        graceful = True
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"]
                                   for c in a.parameters["cards"]} == {
                                       MYSTICAL_ELF, SECOND_DISCARD}), None)
                    discarded = action is not None
                if discarded and not premature:
                    option = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == PREMATURE_BURIAL), None)
                    if option is not None:
                        assert MYSTICAL_ELF in {c.code for c in observation.graveyards[0]}
                        action = option
                        premature = True
                revived = any(c.code == MYSTICAL_ELF and c.zone == "monster"
                              and c.position == "faceup" for c in observation.field)
                if premature and revived and not response_used:
                    assert observation.life_points == (7200, 8000)
                    assert any(c.code == PREMATURE_BURIAL and c.zone == "spell_trap"
                               for c in observation.field)
                    option = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == response), None)
                    if option is not None:
                        action = option
                        response_used = True
                if actions[0].kind == "select_card" and premature:
                    target = (PREMATURE_BURIAL if response_used
                              and response == MYSTICAL_SPACE_TYPHOON else MYSTICAL_ELF)
                    action = next((a for a in actions if a.parameters.get("code") == target
                                   and a.parameters.get("controller") == 0), action)
            grave = {c.code for c in observation.graveyards[0]}
            if response_used and {PREMATURE_BURIAL, response}.issubset(grave) \
                    and any(a.kind == "normal_summon" for a in actions):
                assert observation.life_points == (7200, 8000)
                own_monsters = [c for c in observation.field if c.zone == "monster"]
                if response == BOOK_OF_MOON:
                    assert len(own_monsters) == 1
                    assert own_monsters[0].code == MYSTICAL_ELF
                    assert own_monsters[0].position == "facedown"
                    assert MYSTICAL_ELF not in grave
                    other = env.engine.probe.observation(1)
                    hidden = next(c for c in other.field if c.zone == "monster")
                    assert hidden.code is None and hidden.position == "facedown"
                    assert (0, "monster", hidden.sequence, MYSTICAL_ELF) in {
                        (c.controller, c.zone, c.sequence, c.code)
                        for c in other.known_opponent_field_cards}
                else:
                    assert not own_monsters
                    assert MYSTICAL_ELF in grave
                loaded = env.engine.probe.loaded_script_sha256
                assert f"official/c{PREMATURE_BURIAL}.lua" in loaded
                assert f"official/c{response}.lua" in loaded
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
    pytest.fail("Premature Burial response did not reach its final state")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_mst_chained_to_premature_activation_prevents_revive_but_cost_is_paid(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (GRACEFUL_CHARITY, PREMATURE_BURIAL, MYSTICAL_SPACE_TYPHOON):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    deck = tmp_path / "premature_chain.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL_CHARITY, PREMATURE_BURIAL, MYSTICAL_SPACE_TYPHOON,
        *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        graceful = discarded = premature = targeted = mst_chained = False
        for _ in range(35):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0:
                if not graceful:
                    option = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL_CHARITY), None)
                    if option is not None:
                        action = option
                        graceful = True
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"]
                                   for c in a.parameters["cards"]} == {
                                       MYSTICAL_ELF, SECOND_DISCARD}), None)
                    discarded = action is not None
                if discarded and not premature:
                    option = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == PREMATURE_BURIAL), None)
                    if option is not None:
                        action = option
                        premature = True
                if premature and not targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == MYSTICAL_ELF and a.parameters.get("location") == 16),
                                  action)
                    targeted = action is not None and action.kind == "select_card"
                if targeted and not mst_chained:
                    option = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == MYSTICAL_SPACE_TYPHOON),
                                  None)
                    if option is not None:
                        assert observation.life_points == (7200, 8000)
                        assert MYSTICAL_ELF in {c.code for c in observation.graveyards[0]}
                        assert not any(c.zone == "monster" for c in observation.field)
                        action = option
                        mst_chained = True
                if mst_chained and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == PREMATURE_BURIAL and a.parameters.get("controller") == 0),
                                  action)
            grave = {c.code for c in observation.graveyards[0]}
            if mst_chained and {PREMATURE_BURIAL, MYSTICAL_SPACE_TYPHOON}.issubset(grave) \
                    and any(a.kind == "normal_summon" for a in actions):
                assert observation.life_points == (7200, 8000)
                assert MYSTICAL_ELF in grave
                assert not any(c.zone == "monster" for c in observation.field)
                loaded = env.engine.probe.loaded_script_sha256
                assert f"official/c{PREMATURE_BURIAL}.lua" in loaded
                assert f"official/c{MYSTICAL_SPACE_TYPHOON}.lua" in loaded
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
    pytest.fail("chained MST did not resolve before Premature Burial")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("negate_activation", [False, True])
def test_solemn_can_negate_premature_activation_but_not_its_effect_summon(
    tmp_path, negate_activation,
):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (GRACEFUL_CHARITY, PREMATURE_BURIAL, SOLEMN_JUDGMENT):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    attacker = tmp_path / "premature.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL_CHARITY, PREMATURE_BURIAL, MYSTICAL_SPACE_TYPHOON,
        *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    defender = tmp_path / "solemn.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        *([SOLEMN_JUDGMENT] * 3), *VANILLA_DECK[3:])))
                        + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL_CHARITY, PREMATURE_BURIAL}.issubset(c.code for c in obs.hand)
        assert SOLEMN_JUDGMENT in {
            c.code for c in env.engine.probe.observation(1).hand}
        graceful = discarded = solemn_set = premature = targeted = responded = False
        for _ in range(65):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL_CHARITY), None)
                    graceful |= action is not None
                elif not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"] for c in
                                   a.parameters["cards"]} == {
                                       MYSTICAL_ELF, SECOND_DISCARD}), None)
                    discarded |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not solemn_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SOLEMN_JUDGMENT), None)
                solemn_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and discarded:
                if not premature:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == PREMATURE_BURIAL), None)
                    premature |= action is not None
                elif not targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == MYSTICAL_ELF and a.parameters.get("location") == 16),
                                  None)
                    targeted |= action is not None
            if targeted and obs.acting_player == 1 and not responded:
                solemn = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SOLEMN_JUDGMENT), None)
                if solemn is not None:
                    assert obs.life_points == (7200, 8000)
                    assert MYSTICAL_ELF in {c.code for c in obs.graveyards[0]}
                    action = solemn if negate_activation else next(
                        a for a in actions if a.kind == "pass")
                    responded = True
            if responded and obs.acting_player == 0 and obs.phase == "main1" \
                    and any(a.kind == "end_phase" for a in actions):
                own_monsters = {c.code for c in obs.field
                                if c.controller == 0 and c.zone == "monster"}
                if negate_activation:
                    assert obs.life_points == (7200, 4000)
                    assert MYSTICAL_ELF in {c.code for c in obs.graveyards[0]}
                    assert MYSTICAL_ELF not in own_monsters
                    assert PREMATURE_BURIAL in {c.code for c in obs.graveyards[0]}
                    assert SOLEMN_JUDGMENT in {c.code for c in obs.graveyards[1]}
                else:
                    assert obs.life_points == (7200, 8000)
                    assert MYSTICAL_ELF in own_monsters
                    assert PREMATURE_BURIAL in {c.code for c in obs.field}
                    assert not any(c.code == SOLEMN_JUDGMENT
                                   for c in obs.graveyards[1])
                    assert any(c.controller == 1 and c.zone == "spell_trap"
                               for c in obs.field)
                assert f"official/c{PREMATURE_BURIAL}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
    pytest.fail("Premature Burial and Solemn did not resolve within 65 decisions")
