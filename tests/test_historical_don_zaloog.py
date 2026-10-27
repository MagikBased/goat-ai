"""Don Zaloog offers optional random discard or two-card Deck mill."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

DON_ZALOOG = 76922029
MYSTICAL_ELF = 15025844
WABOKU = 12607053
SETTABLE_BACKROW = (12607053, 14087893, 4178474, 56120475, 60082869)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("choice", ["discard", "mill", "decline"])
def test_don_zaloog_battle_damage_choices_keep_hand_hidden(tmp_path, choice):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{DON_ZALOOG}.lua").is_file():
        pytest.skip("Don Zaloog script not installed")
    deck = tmp_path / "don.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        *([DON_ZALOOG] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        summoned = attacked = offered = mode_selected = False
        before_hand = before_deck = None
        for _ in range(55):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == DON_ZALOOG), None)
                summoned |= action is not None
            if observation.turn == 3 and observation.acting_player == 0 \
                    and observation.phase == "main1":
                action = next((a for a in actions if a.kind == "battle_phase"), action)
            if observation.turn == 3 and observation.phase == "battle_start" \
                    and observation.acting_player == 0 and not attacked:
                before_hand = observation.opponent_hand_count
                before_deck = observation.deck_counts[1]
                assert before_hand > 0 and before_deck > 2
                assert not observation.known_opponent_cards
                assert not observation.private_reveals
                action = next((a for a in actions if a.kind == "attack"
                               and a.parameters.get("code") == DON_ZALOOG), None)
                attacked |= action is not None
            if attacked and not offered and any(a.kind == "yes" for a in actions):
                assert observation.phase == "damage_step"
                assert observation.life_points == (8000, 6600)
                assert observation.opponent_hand_count == before_hand
                offered = True
                wanted = "no" if choice == "decline" else "yes"
                action = next(a for a in actions if a.kind == wanted
                              and a.parameters.get("code") == DON_ZALOOG)
                if choice == "decline":
                    mode_selected = True
            if offered and choice != "decline" and not mode_selected \
                    and actions[0].kind == "select_option":
                assert len(actions) == 2
                assert all(set(a.parameters) == {"prompt_id"} for a in actions)
                action = actions[0 if choice == "discard" else 1]
                mode_selected = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if mode_selected and observation.turn == 3 \
                    and observation.phase == "battle_step" \
                    and observation.acting_player == 0:
                assert summoned and attacked and offered
                assert observation.life_points == (8000, 6600)
                assert observation.chain == ()
                if choice == "discard":
                    assert observation.opponent_hand_count == before_hand - 1
                    assert observation.deck_counts[1] == before_deck
                    assert len(observation.graveyards[1]) == 1
                    assert observation.graveyards[1][0].code is not None
                elif choice == "mill":
                    assert observation.opponent_hand_count == before_hand
                    assert observation.deck_counts[1] == before_deck - 2
                    assert len(observation.graveyards[1]) == 2
                    assert all(c.code is not None for c in observation.graveyards[1])
                else:
                    assert observation.opponent_hand_count == before_hand
                    assert observation.deck_counts[1] == before_deck
                    assert not observation.graveyards[1]
                assert f"official/c{DON_ZALOOG}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail(f"Don Zaloog did not complete {choice} battle-damage line")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_don_triggers_when_weaker_monster_attacks_it(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{DON_ZALOOG}.lua").is_file():
        pytest.skip("Don Zaloog script not installed")
    deck = tmp_path / "don.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        *([DON_ZALOOG] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=10,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        don_summoned = elf_summoned = elf_attacked = offered = mode_selected = False
        before_hand = None
        for _ in range(65):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 \
                    and not don_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == DON_ZALOOG), None)
                don_summoned |= action is not None
            if observation.turn == 2 and observation.acting_player == 1 \
                    and observation.phase == "main1" and not elf_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == MYSTICAL_ELF), None)
                elf_summoned |= action is not None
            if observation.turn == 2 and observation.acting_player == 1 \
                    and observation.phase == "main1" and elf_summoned and action is None:
                action = next((a for a in actions if a.kind == "battle_phase"), None)
            if observation.turn == 2 and observation.acting_player == 1 \
                    and observation.phase == "battle_start" and not elf_attacked:
                before_hand = len(observation.hand)
                action = next((a for a in actions if a.kind == "attack"
                               and a.parameters.get("code") == MYSTICAL_ELF), None)
                elf_attacked |= action is not None
            if elf_attacked and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == DON_ZALOOG), None)
            if elf_attacked and not offered and any(a.kind == "yes"
                                                    and a.parameters.get("code") == DON_ZALOOG
                                                    for a in actions):
                assert observation.acting_player == 0
                assert observation.phase == "damage_step"
                assert observation.life_points == (8000, 7400)
                action = next(a for a in actions if a.kind == "yes"
                              and a.parameters.get("code") == DON_ZALOOG)
                offered = True
            if offered and not mode_selected and actions[0].kind == "select_option":
                assert observation.acting_player == 0
                assert len(actions) == 2
                action = actions[0]  # Random opponent-hand discard.
                mode_selected = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if mode_selected and observation.phase == "battle_step" \
                    and observation.acting_player == 1:
                assert observation.life_points == (8000, 7400)
                assert len(observation.hand) == before_hand - 1
                assert any(c.code == MYSTICAL_ELF for c in observation.graveyards[1])
                assert len(observation.graveyards[1]) == 2
                assert any(c.code == DON_ZALOOG for c in observation.field)
                assert f"official/c{DON_ZALOOG}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Don did not trigger after being attacked by Mystical Elf")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_don_with_empty_opponent_hand_only_mills_deck(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{DON_ZALOOG}.lua").is_file():
        pytest.skip("Don Zaloog script not installed")
    attacker = tmp_path / "don.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        *([DON_ZALOOG] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    defender = tmp_path / "empty_hand.ydk"
    filler = [code for code in VANILLA_DECK if code != MYSTICAL_ELF]
    defender.write_text("#main\n" + "\n".join(map(str, (
        *([MYSTICAL_ELF] * 3),
        *(code for code in SETTABLE_BACKROW for _ in range(3)),
        *filler[:22]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=3174,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert DON_ZALOOG in {c.code for c in observation.hand}
        don_summoned = elf_summoned = attacked = offered = False
        before_deck = None
        for _ in range(100):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 \
                    and not don_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == DON_ZALOOG), None)
                don_summoned |= action is not None
            if observation.turn == 2 and observation.acting_player == 1 \
                    and observation.phase == "main1":
                if not elf_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == MYSTICAL_ELF), None)
                    elf_summoned |= action is not None
                if elf_summoned and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"), None)
            if observation.turn == 3 and observation.acting_player == 0 \
                    and observation.phase == "main1":
                action = next((a for a in actions if a.kind == "battle_phase"), action)
            if observation.turn == 3 and observation.acting_player == 0 \
                    and observation.phase == "battle_start" and not attacked:
                assert observation.opponent_hand_count == 0
                assert sum(c.controller == 1 and c.zone == "spell_trap"
                           for c in observation.field) == 5
                before_deck = observation.deck_counts[1]
                action = next((a for a in actions if a.kind == "attack"
                               and a.parameters.get("code") == DON_ZALOOG), None)
                attacked |= action is not None
            if attacked and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == MYSTICAL_ELF), None)
            if attacked and not offered and any(a.kind == "yes"
                                                and a.parameters.get("code") == DON_ZALOOG
                                                for a in actions):
                assert observation.life_points == (8000, 7400)
                action = next(a for a in actions if a.kind == "yes"
                              and a.parameters.get("code") == DON_ZALOOG)
                offered = True
            if offered and actions[0].kind == "select_option":
                assert len(actions) == 1  # No random-discard mode is legal.
                action = actions[0]
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if offered and observation.phase == "battle_step" \
                    and observation.acting_player == 0:
                assert observation.opponent_hand_count == 0
                assert observation.deck_counts[1] == before_deck - 2
                assert observation.life_points == (8000, 7400)
                assert any(c.code == MYSTICAL_ELF for c in observation.graveyards[1])
                assert len(observation.graveyards[1]) == 3
                assert f"official/c{DON_ZALOOG}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Don did not mill when opponent had no hand cards")


def _reach_mode_choice(env):
    observation = env.reset()
    summoned = False
    for _ in range(40):
        actions = env.legal_actions()
        if actions[0].kind == "select_option":
            return observation, actions, tuple(
                c.code for c in env.engine.probe.observation(1).hand)
        action = None
        if observation.turn == 1 and observation.acting_player == 0 and not summoned:
            action = next((a for a in actions if a.kind == "normal_summon"
                           and a.parameters.get("code") == DON_ZALOOG), None)
            summoned |= action is not None
        if observation.turn == 3 and observation.phase == "main1" \
                and observation.acting_player == 0:
            action = next((a for a in actions if a.kind == "battle_phase"), action)
        if observation.turn == 3 and observation.phase == "battle_start" \
                and observation.acting_player == 0:
            action = next((a for a in actions if a.kind == "attack"
                           and a.parameters.get("code") == DON_ZALOOG), action)
        if action is None:
            action = next((a for a in actions if a.kind == "yes"
                           and a.parameters.get("code") == DON_ZALOOG), None)
        if action is None:
            action = next((a for a in actions if a.kind in (
                "place", "pass", "end_phase")), actions[0])
        observation = env.step(action)
    pytest.fail("Don Zaloog did not offer its two effect modes")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_don_choice_is_identical_when_opponent_private_hand_changes(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{DON_ZALOOG}.lua").is_file():
        pytest.skip("Don Zaloog script not installed")
    attacker = tmp_path / "don.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        *([DON_ZALOOG] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    changed = list(VANILLA_DECK)
    changed[3] = 97923414  # Replace a privately held La Jinn with a second Inpachi.
    defender = tmp_path / "changed_private_hand.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, changed)) + "\n#extra\n!side\n")
    with GoatEnvironment(str(attacker), "examples/decks/vanilla_probe.ydk", seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as original:
        observation, actions, hidden_hand = _reach_mode_choice(original)
    with GoatEnvironment(str(attacker), str(defender), seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as alternate:
        changed_observation, changed_actions, changed_hand = _reach_mode_choice(alternate)
    assert hidden_hand != changed_hand
    assert observation == changed_observation
    assert actions == changed_actions
    assert observation.opponent_hand_count == len(hidden_hand)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_don_does_not_trigger_when_waboku_prevents_direct_battle_damage(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (DON_ZALOOG, WABOKU):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    don_deck = tmp_path / "don.ydk"
    don_deck.write_text("#main\n" + "\n".join(map(str, (
        *([DON_ZALOOG] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    waboku_deck = tmp_path / "waboku.ydk"
    waboku_deck.write_text("#main\n" + "\n".join(map(str, (
        *([WABOKU] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(don_deck), str(waboku_deck), seed=11,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert DON_ZALOOG in {card.code for card in observation.hand}
        assert WABOKU in {card.code for card in env.engine.probe.observation(1).hand}
        don_summoned = waboku_set = don_attacked = waboku_used = checked = False
        damage_step_seen = False
        defender_hand = defender_deck = None
        agents = (RandomAgent(11), RandomAgent(12))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                assert {f"official/c{code}.lua" for code in (DON_ZALOOG, WABOKU)} <= (
                    env.engine.probe.loaded_script_sha256.keys())
                path = tmp_path / "don_waboku.json"
                write_trajectory(path, env.trajectory())
                replay = read_trajectory(path)
                assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(
                    replay.decisions)
                audit_trajectory_visibility(replay)
                return
            actions = env.legal_actions()
            if waboku_used and observation.turn == 3:
                damage_step_seen |= observation.phase == "damage_step"
                assert not any(a.kind == "yes"
                               and a.parameters.get("code") == DON_ZALOOG
                               for a in actions)
            action = None
            if observation.turn == 1 and observation.acting_player == 0 \
                    and not don_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == DON_ZALOOG), None)
                don_summoned |= action is not None
            if observation.turn == 2 and observation.acting_player == 1 \
                    and not waboku_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == WABOKU), None)
                waboku_set |= action is not None
            if observation.turn == 3 and observation.acting_player == 0 \
                    and observation.phase == "main1":
                action = next((a for a in actions if a.kind == "battle_phase"), action)
            if observation.turn == 3 and observation.acting_player == 0 \
                    and observation.phase == "battle_start" and not don_attacked:
                defender_hand = observation.opponent_hand_count
                defender_deck = observation.deck_counts[1]
                action = next((a for a in actions if a.kind == "attack"
                               and a.parameters.get("code") == DON_ZALOOG), None)
                don_attacked |= action is not None
            if don_attacked and observation.turn == 3 and observation.phase == "battle_step" \
                    and observation.acting_player == 1 and not waboku_used:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == WABOKU), None)
                waboku_used |= action is not None
            if waboku_used and damage_step_seen and not checked and observation.turn == 3 \
                    and observation.phase == "battle_step" \
                    and observation.acting_player == 0 \
                    and WABOKU in {c.code for c in observation.graveyards[1]}:
                assert observation.life_points == (8000, 8000)
                assert observation.opponent_hand_count == defender_hand
                assert observation.deck_counts[1] == defender_deck
                assert damage_step_seen
                checked = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase", "main2")), actions[0])
            if action is None:
                action = agents[observation.acting_player].select_action(observation, actions)
            observation = env.step(action)
    pytest.fail("Don Zaloog / Waboku duel did not terminate")
