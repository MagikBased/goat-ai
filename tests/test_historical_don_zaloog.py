"""Don Zaloog offers optional random discard or two-card Deck mill."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

DON_ZALOOG = 76922029


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
