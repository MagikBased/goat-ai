"""Torrential Tribute summon response and Book of Moon chain."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import verify_trajectory

TORRENTIAL_TRIBUTE = 53582587
BOOK_OF_MOON = 14087893
DEKOICHI = 87621407
GRACEFUL_CHARITY = 79571449
POT_OF_GREED = 55144522
CALL_OF_THE_HAUNTED = 97077563
MYSTICAL_ELF = 15025844
SECOND_DISCARD = 79182538
MYSTIC_TOMATO = 504700142
SANGAN = 504700178
GEMINI_ELF = 69140098
SCAPEGOAT = 504700123
SHEEP_CODES = {73915052, 73915053, 73915054, 73915055}


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_torrential_after_summon_destroys_faceup_and_book_facedown_monsters(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (TORRENTIAL_TRIBUTE, BOOK_OF_MOON):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    paths = []
    for name, code in (("attacker", BOOK_OF_MOON),
                       ("defender", TORRENTIAL_TRIBUTE)):
        path = tmp_path / f"{name}.ydk"
        path.write_text("#main\n" + "\n".join(map(str, (
            code, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
        paths.append(path)

    with GoatEnvironment(*(str(path) for path in paths), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        summons = 0
        set_trap = chained_torrential = chained_book = False
        summoned_codes = []
        for _ in range(55):
            actions = env.legal_actions()
            action = None
            if (observation.acting_player == 0 and observation.turn in (1, 3)
                    and summons < (1 if observation.turn == 1 else 2)):
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    summons += 1
                    summoned_codes.append(action.parameters["code"])
            if observation.acting_player == 1 and observation.turn == 2 and not set_trap:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == TORRENTIAL_TRIBUTE), action)
                set_trap |= action is not None and action.kind == "set_spell_trap"
            if observation.acting_player == 1 and observation.turn == 3 and not chained_torrential:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == TORRENTIAL_TRIBUTE), action)
                if action is not None and action.kind == "chain":
                    assert summons == 2
                    assert observation.phase == "main1"
                    chained_torrential = True
            if observation.acting_player == 0 and chained_torrential and not chained_book:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK_OF_MOON), action)
                chained_book |= action is not None and action.kind == "chain"
            if action is None and summoned_codes:
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == summoned_codes[0]), None)
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if set_trap and not chained_torrential and observation.acting_player == 0:
                assert any(card.controller == 1 and card.zone == "spell_trap"
                           and card.position == "facedown" and card.code is None
                           for card in observation.field)
            if chained_book and any(card.code == TORRENTIAL_TRIBUTE
                                    for card in observation.graveyards[1]):
                assert set_trap and chained_torrential
                assert len(summoned_codes) == 2
                assert not any(card.zone == "monster" for card in observation.field)
                assert ({card.code for card in observation.graveyards[0]}
                        >= {*summoned_codes, BOOK_OF_MOON})
                assert observation.life_points == (8000, 8000)
                return
    pytest.fail("Torrential Tribute / Book of Moon chain did not resolve")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_torrential_after_scapegoat_resolution_destroys_all_tokens(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{SCAPEGOAT}.lua",
                     f"official/c{TORRENTIAL_TRIBUTE}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    goat_deck = tmp_path / "scapegoat.ydk"
    torrential_deck = tmp_path / "torrential.ydk"
    goat_deck.write_text("#main\n" + "\n".join(map(str, (
        *([SCAPEGOAT] * 2), *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    torrential_deck.write_text("#main\n" + "\n".join(map(str, (
        TORRENTIAL_TRIBUTE, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(goat_deck), str(torrential_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        goat_set = trap_set = goat_used = torrential_used = False
        for _ in range(85):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not goat_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                goat_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not trap_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == TORRENTIAL_TRIBUTE), None)
                trap_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and trap_set and not goat_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                goat_used |= action is not None
            if goat_used and obs.acting_player == 1 and not torrential_used:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == TORRENTIAL_TRIBUTE), None)
                if action is not None:
                    assert obs.chain == ()
                    assert SCAPEGOAT in {c.code for c in obs.graveyards[0]}
                    assert {c.code for c in obs.field if c.zone == "monster"
                            and c.controller == 0} == SHEEP_CODES
                    torrential_used = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_zones", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if torrential_used and TORRENTIAL_TRIBUTE in {
                    c.code for c in obs.graveyards[1]}:
                assert obs.chain == ()
                assert not any(c.zone == "monster" for c in obs.field)
                assert not any(c.code in SHEEP_CODES for pile in (
                    *obs.graveyards, *obs.banished) for c in pile)
                assert obs.life_points == (8000, 8000)
                assert {f"goat/c{SCAPEGOAT}.lua",
                        f"official/c{TORRENTIAL_TRIBUTE}.lua"}.issubset(
                            env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Torrential was not offered after Scapegoat summoned four tokens")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_torrential_chains_to_flip_effect_without_negating_dekoichi_draw(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (TORRENTIAL_TRIBUTE, DEKOICHI):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    own = tmp_path / "dekoichi.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        *([DEKOICHI] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    other = tmp_path / "torrential.ydk"
    other.write_text("#main\n" + "\n".join(map(str, (
        TORRENTIAL_TRIBUTE, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(other), seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        dekoichi_set = trap_set = opponent_summoned = flipped = chained = False
        opponent_code = None
        hand_before = deck_before = None
        for _ in range(75):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not dekoichi_set:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == DEKOICHI), None)
                dekoichi_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not trap_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == TORRENTIAL_TRIBUTE), None)
                    trap_set |= action is not None
                if trap_set and not opponent_summoned and action is None:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        opponent_code = action.parameters["code"]
                        opponent_summoned = True
            if obs.turn == 3 and obs.acting_player == 0 and trap_set \
                    and not flipped:
                action = next((a for a in actions if a.kind == "flip_summon"
                               and a.parameters.get("code") == DEKOICHI), None)
                if action is not None:
                    hand_before = len(obs.hand)
                    deck_before = obs.deck_counts[0]
                    flipped = True
            if flipped and obs.acting_player == 1 and not chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == TORRENTIAL_TRIBUTE), None)
                if action is not None:
                    assert len(obs.chain) == 1
                    assert obs.chain[0].card_code == DEKOICHI
                    chained = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if action.kind == "chain" and action.parameters.get("code") \
                    == TORRENTIAL_TRIBUTE:
                assert [link.card_code for link in obs.chain] == [
                    DEKOICHI, TORRENTIAL_TRIBUTE]
            if chained and TORRENTIAL_TRIBUTE in {
                    c.code for c in obs.graveyards[1]} and obs.chain == ():
                owner = env.engine.probe.observation(0)
                assert opponent_summoned and opponent_code is not None
                assert not any(c.zone == "monster" for c in owner.field)
                assert DEKOICHI in {c.code for c in owner.graveyards[0]}
                assert opponent_code in {c.code for c in owner.graveyards[1]}
                assert len(owner.hand) == hand_before + 1
                assert owner.deck_counts[0] == deck_before - 1
                assert owner.life_points == (8000, 8000)
                assert not env.engine.probe.observation(1).private_reveals
                assert {f"official/c{code}.lua" for code in (
                    TORRENTIAL_TRIBUTE, DEKOICHI)}.issubset(
                        env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Torrential did not chain to Dekoichi's Flip Effect")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_torrential_answers_completed_call_of_the_haunted_summon(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (GRACEFUL_CHARITY, CALL_OF_THE_HAUNTED, TORRENTIAL_TRIBUTE):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    own = tmp_path / "call.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL_CHARITY, CALL_OF_THE_HAUNTED, BOOK_OF_MOON,
        *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    other = tmp_path / "torrential.ydk"
    other.write_text("#main\n" + "\n".join(map(str, (
        TORRENTIAL_TRIBUTE, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(other), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        graceful = discarded = call_set = trap_set = opponent_summoned = False
        call_used = call_targeted = torrential_used = False
        opponent_code = None
        for _ in range(80):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL_CHARITY), None)
                    graceful |= action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"] for c in
                                   a.parameters["cards"]} == {
                                       MYSTICAL_ELF, SECOND_DISCARD}), None)
                    discarded |= action is not None
                if discarded and not call_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == CALL_OF_THE_HAUNTED), None)
                    call_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not trap_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == TORRENTIAL_TRIBUTE), None)
                    trap_set |= action is not None
                if trap_set and not opponent_summoned and action is None:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        opponent_code = action.parameters["code"]
                        opponent_summoned = True
            if obs.turn == 3 and obs.acting_player == 0 and trap_set \
                    and not call_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == CALL_OF_THE_HAUNTED), None)
                call_used |= action is not None
            if call_used and not call_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == MYSTICAL_ELF and a.parameters.get("controller") == 0), None)
                call_targeted |= action is not None
            if call_targeted and any(link.card_code == CALL_OF_THE_HAUNTED
                                     for link in obs.chain) and obs.acting_player == 1:
                assert not any(a.kind == "chain" and a.parameters.get("code")
                               == TORRENTIAL_TRIBUTE for a in actions)
            if call_targeted and obs.acting_player == 1 and not torrential_used:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == TORRENTIAL_TRIBUTE), None)
                if action is not None:
                    assert obs.chain == ()
                    assert any(c.code == MYSTICAL_ELF and c.zone == "monster"
                               for c in obs.field)
                    assert any(c.code == CALL_OF_THE_HAUNTED and c.zone == "spell_trap"
                               for c in obs.field)
                    torrential_used = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if torrential_used and TORRENTIAL_TRIBUTE in {
                    c.code for c in obs.graveyards[1]} and obs.chain == ():
                assert opponent_summoned and opponent_code is not None
                assert not any(c.zone == "monster" for c in obs.field)
                assert not any(c.code == CALL_OF_THE_HAUNTED for c in obs.field)
                assert {MYSTICAL_ELF, CALL_OF_THE_HAUNTED}.issubset(
                    {c.code for c in obs.graveyards[0]})
                assert opponent_code in {c.code for c in obs.graveyards[1]}
                assert obs.life_points == (8000, 8000)
                assert not obs.private_reveals
                assert {f"official/c{code}.lua" for code in (
                    GRACEFUL_CHARITY, CALL_OF_THE_HAUNTED,
                    TORRENTIAL_TRIBUTE)}.issubset(
                        env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Torrential was not offered after Call's effect Summon")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_card,expect_torrential", [
    (POT_OF_GREED, False), (SCAPEGOAT, True),
])
def test_call_at_chain_link_two_uses_last_summon_for_torrential_window(
        tmp_path, chain_card, expect_torrential):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (GRACEFUL_CHARITY, chain_card, CALL_OF_THE_HAUNTED,
                 TORRENTIAL_TRIBUTE):
        if not any((root / f"scripts/{folder}/c{code}.lua").is_file()
                   for folder in ("official", "goat")):
            pytest.skip(f"script for {code} not installed")
    own = tmp_path / "call_chain.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL_CHARITY, CALL_OF_THE_HAUNTED, BOOK_OF_MOON,
        *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    other = tmp_path / "chain_torrential.ydk"
    other_cards = [chain_card, TORRENTIAL_TRIBUTE, *VANILLA_DECK[2:]]
    other_cards[1], other_cards[4] = other_cards[4], other_cards[1]
    other.write_text("#main\n" + "\n".join(map(str, other_cards))
                     + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(other), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        graceful = discarded = call_set = trap_set = lead_used = call_used = False
        targeted = checked = torrential_fired = torrential_resolved = False
        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(3000):
            if env.is_terminal():
                assert checked, (graceful, discarded, call_set, trap_set,
                                 lead_used, call_used, targeted, obs.turn)
                assert torrential_resolved == expect_torrential
                assert {f"official/c{code}.lua" for code in (
                    GRACEFUL_CHARITY, CALL_OF_THE_HAUNTED,
                    TORRENTIAL_TRIBUTE)}.issubset(env.engine.probe.loaded_script_sha256)
                trajectory = env.trajectory()
                assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) == len(
                    trajectory.decisions)
                audit_trajectory_visibility(trajectory)
                return
            actions = env.legal_actions()
            action = None
            if torrential_fired and not torrential_resolved and obs.chain == () \
                    and TORRENTIAL_TRIBUTE in {card.code for card in obs.graveyards[1]}:
                assert not any(card.zone == "monster" for card in obs.field)
                torrential_resolved = True
            if not checked:
                if obs.turn == 1 and obs.acting_player == 0:
                    if not graceful:
                        action = next((a for a in actions if a.kind == "activate"
                                       and a.parameters.get("code") == GRACEFUL_CHARITY), None)
                        graceful |= action is not None
                    if graceful and not discarded and actions[0].kind == "select_cards":
                        action = next((a for a in actions if {card["code"] for card in
                                       a.parameters["cards"]} == {
                                           MYSTICAL_ELF, SECOND_DISCARD}), None)
                        discarded |= action is not None
                    if discarded and not call_set and action is None:
                        action = next((a for a in actions if a.kind == "set_spell_trap"
                                       and a.parameters.get("code") == CALL_OF_THE_HAUNTED), None)
                        call_set |= action is not None
                if obs.turn == 2 and obs.acting_player == 1 and not trap_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == TORRENTIAL_TRIBUTE), None)
                    trap_set |= action is not None
                if obs.turn == 4 and obs.acting_player == 1 and trap_set and not lead_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == chain_card), None)
                    lead_used |= action is not None
                if lead_used and obs.acting_player == 0 and not call_used \
                        and any(link.card_code == chain_card for link in obs.chain):
                    action = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == CALL_OF_THE_HAUNTED), None)
                    call_used |= action is not None
                if call_used and not targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == MYSTICAL_ELF and a.parameters.get("controller") == 0), None)
                    targeted |= action is not None
                if targeted and obs.chain == () and chain_card in {
                        card.code for card in obs.graveyards[1]} and any(
                        card.code == MYSTICAL_ELF for card in obs.field):
                    offered = any(a.kind == "chain" and a.parameters.get("code")
                                  == TORRENTIAL_TRIBUTE for a in actions)
                    assert offered == expect_torrential
                    assert any(card.code == TORRENTIAL_TRIBUTE and
                               card.position == "facedown" for card in obs.field)
                    if expect_torrential:
                        assert sum(card.code in SHEEP_CODES for card in obs.field) == 4
                        action = next(a for a in actions if a.kind == "chain" and
                                      a.parameters.get("code") == TORRENTIAL_TRIBUTE)
                        torrential_fired = True
                    checked = True
                if action is None:
                    action = next((a for a in actions if a.kind in (
                        "place", "select_position", "pass", "end_phase")), actions[0])
            else:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
    pytest.fail("Call/Pot chain timing duel did not complete")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_torrential_unavailable_for_mystic_tomato_damage_step_recruit(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"official/c{TORRENTIAL_TRIBUTE}.lua",
                     f"goat/c{MYSTIC_TOMATO}.lua", f"goat/c{SANGAN}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    attacker = tmp_path / "attacker.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        TORRENTIAL_TRIBUTE, *([GEMINI_ELF] * 3),
        *tuple(c for c in VANILLA_DECK if c != GEMINI_ELF)[:36])))
        + "\n#extra\n!side\n")
    defender = tmp_path / "defender.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        *([MYSTIC_TOMATO] * 3), SANGAN,
        *VANILLA_DECK[4:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        trap_set = gemini_summoned = tomato_set = battle = attacked = False
        attack_targeted = recruited = sangan_selected = False
        damage_step_choices = 0
        deck_before = None
        for _ in range(85):
            actions = env.legal_actions()
            action = None
            if trap_set and obs.phase == "damage_step" and obs.acting_player == 0:
                damage_step_choices += 1
                assert not any(a.parameters.get("code") == TORRENTIAL_TRIBUTE
                               and a.kind in ("activate", "chain") for a in actions)
            if obs.turn == 1 and obs.acting_player == 0:
                if not trap_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == TORRENTIAL_TRIBUTE), None)
                    trap_set |= action is not None
                if trap_set and not gemini_summoned and action is None:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == GEMINI_ELF), None)
                    gemini_summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not tomato_set:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == MYSTIC_TOMATO), None)
                tomato_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and tomato_set:
                if obs.phase == "main1" and not battle:
                    action = next((a for a in actions if a.kind == "battle_phase"), None)
                    battle |= action is not None
                if obs.phase == "battle_start" and not attacked:
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == GEMINI_ELF), None)
                    attacked |= action is not None
            if attacked and not attack_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and "code" not in a.parameters), None)
                attack_targeted |= action is not None
            if attack_targeted and not recruited and any(a.kind == "yes" for a in actions):
                assert obs.phase == "damage_step" and obs.acting_player == 1
                deck_before = obs.deck_counts[1]
                action = next(a for a in actions if a.kind == "yes")
                recruited = True
            if recruited and not sangan_selected and actions[0].kind == "select_card":
                assert obs.phase == "damage_step" and obs.acting_player == 1
                action = next((a for a in actions if a.parameters.get("code") == SANGAN),
                              None)
                sangan_selected |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if sangan_selected and obs.phase == "battle_step":
                attacker_view = env.engine.probe.observation(0)
                assert attacker_view.deck_counts[1] == deck_before - 1
                assert any(c.code == SANGAN and c.controller == 1
                           and c.zone == "monster" for c in attacker_view.field)
                assert any(c.code == TORRENTIAL_TRIBUTE and c.controller == 0
                           and c.zone == "spell_trap" for c in attacker_view.field)
                assert any(c.code == MYSTIC_TOMATO
                           for c in attacker_view.graveyards[1])
                assert damage_step_choices > 0
                assert f"goat/c{MYSTIC_TOMATO}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Mystic Tomato did not recruit during the Damage Step")
