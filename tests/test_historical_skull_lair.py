"""Skull Lair pays a Graveyard cost and checks the target's visible Level."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

GRACEFUL = 79571449
SKULL_LAIR = 6733059
SKULL_SERVANT = 32274490


def _decks(tmp_path):
    own = tmp_path / "skull_lair.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL, *[SKULL_LAIR] * 3, *[SKULL_SERVANT] * 3,
        *VANILLA_DECK[7:]))) + "\n#extra\n!side\n")
    opponent = tmp_path / "skull_servant.ydk"
    opponent.write_text("#main\n" + "\n".join(map(str, (
        *[SKULL_SERVANT] * 3, *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    return own, opponent


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("faceup", [False, True])
def test_skull_lair_only_destroys_matching_faceup_level(tmp_path, faceup):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (GRACEFUL, SKULL_LAIR):
        assert (root / f"scripts/official/c{code}.lua").is_file()
    own, opponent = _decks(tmp_path)

    with GoatEnvironment(str(own), str(opponent), 18,
                         ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert {GRACEFUL, SKULL_LAIR, SKULL_SERVANT} <= {
            card.code for card in observation.hand}
        assert SKULL_SERVANT in {
            card.code for card in env.engine.probe.observation(1).hand}
        graceful_used = discarded = lair_set = monster_placed = False
        lair_activated = effect_used = cost_paid = checked = False
        agents = (RandomAgent(18), RandomAgent(19))
        for _ in range(3000):
            if env.is_terminal():
                break
            actions = env.legal_actions()
            action = None
            if not checked and observation.turn == 1 and observation.acting_player == 0:
                if not graceful_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    graceful_used |= action is not None
                if graceful_used and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if any(
                        card.get("code") == SKULL_SERVANT
                        for card in a.parameters["cards"])), None)
                    assert action is not None
                    discarded = True
                if discarded and not lair_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == SKULL_LAIR), None)
                    lair_set |= action is not None
            if not checked and observation.turn == 2 and observation.acting_player == 1 \
                    and not monster_placed:
                kind = "normal_summon" if faceup else "set_monster"
                action = next((a for a in actions if a.kind == kind
                               and a.parameters.get("code") == SKULL_SERVANT), None)
                monster_placed |= action is not None
            if monster_placed and not lair_activated and observation.acting_player == 0:
                action = next((a for a in actions if a.kind in ("chain", "activate")
                               and a.parameters.get("code") == SKULL_LAIR), None)
                lair_activated |= action is not None
            if lair_activated and not checked and observation.acting_player == 0 \
                    and observation.chain == () and any(
                        card.code == SKULL_LAIR and card.position == "faceup"
                        for card in observation.field):
                effect = next((a for a in actions if a.kind in ("activate", "chain")
                               and a.parameters.get("code") == SKULL_LAIR), None)
                if faceup and not effect_used:
                    assert effect is not None
                    action = effect
                    effect_used = True
                elif not faceup:
                    assert effect is None
                    assert any(card.controller == 1 and card.zone == "monster"
                               and card.position == "facedown" and card.code is None
                               for card in observation.field)
                    assert SKULL_SERVANT in {card.code for card in observation.graveyards[0]}
                    checked = True
            if effect_used and not cost_paid and actions[0].kind in (
                    "select_card", "select_cards", "select_unselect_card"):
                action = next((a for a in actions if a.parameters.get("code")
                               == SKULL_SERVANT or any(
                                   card.get("code") == SKULL_SERVANT
                                   for card in a.parameters.get("cards", ()))), None)
                if action is not None:
                    cost_paid = True
            if action is None:
                action = (next((a for a in actions if a.kind in (
                    "pass", "end_phase", "place")), actions[0])
                          if not checked else
                          agents[observation.acting_player].select_action(
                              observation, actions))
            observation = env.step(action)
            if faceup and cost_paid and not checked and observation.chain == ():
                checked = True
                assert SKULL_SERVANT in {card.code for card in observation.banished[0]}
                assert SKULL_LAIR in {card.code for card in observation.field}
                opposing = [card for card in observation.field
                            if card.controller == 1 and card.zone == "monster"]
                assert not opposing
        assert checked and env.is_terminal()
        path = tmp_path / f"skull_lair_{faceup}.json"
        write_trajectory(path, env.trajectory())
        replay = read_trajectory(path)
        assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(replay.decisions)
        assert audit_trajectory_visibility(replay)["decisions"] == len(replay.decisions)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_skull_lair_effect_unavailable_during_damage_step(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    own, opponent = _decks(tmp_path)

    with GoatEnvironment(str(own), str(opponent), 18,
                         ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        graceful = discarded = lair_set = summoned = lair_faceup = attacked = False
        battle_window = damage_window = False
        agents = (RandomAgent(18), RandomAgent(19))
        for _ in range(3000):
            if env.is_terminal():
                break
            actions = env.legal_actions()

            def choice(kind, code=None, choices=actions):
                return next((a for a in choices if a.kind == kind
                             and (code is None or a.parameters.get("code") == code)), None)

            action = None
            if not damage_window and obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = choice("activate", GRACEFUL)
                    graceful |= action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if any(
                        card.get("code") == SKULL_SERVANT
                        for card in a.parameters["cards"])), None)
                    assert action is not None
                    discarded = True
                if discarded and not lair_set and action is None:
                    action = choice("set_spell_trap", SKULL_LAIR)
                    lair_set |= action is not None
            if not damage_window and obs.turn == 2 and obs.acting_player == 1:
                if not summoned:
                    action = choice("normal_summon", SKULL_SERVANT)
                    summoned |= action is not None
                elif lair_faceup and not attacked:
                    action = choice("battle_phase") or choice("attack")
                    attacked |= action is not None and action.kind == "attack"
            if summoned and not lair_faceup and obs.acting_player == 0:
                action = choice("chain", SKULL_LAIR) or choice("activate", SKULL_LAIR)
                lair_faceup |= action is not None
            active = any(card.code == SKULL_LAIR and card.position == "faceup"
                         for card in obs.field)
            effect = (choice("chain", SKULL_LAIR) or choice("activate", SKULL_LAIR)
                      if active else None)
            if attacked and not damage_window and obs.acting_player == 0 \
                    and obs.phase == "battle_step":
                assert effect is not None
                battle_window = True
            if attacked and not damage_window and obs.acting_player == 0 \
                    and obs.phase == "damage_step":
                assert active and battle_window
                assert effect is None
                damage_window = True
            if action is None:
                action = (choice("pass") or choice("end_phase") or choice("place")
                          or actions[0] if not damage_window else
                          agents[obs.acting_player].select_action(obs, actions))
            obs = env.step(action)
        assert graceful and discarded and lair_set and summoned and attacked
        assert battle_window and damage_window and env.is_terminal()
        path = tmp_path / "skull_lair_damage_step.json"
        write_trajectory(path, env.trajectory())
        replay = read_trajectory(path)
        assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(replay.decisions)
        assert audit_trajectory_visibility(replay)["decisions"] == len(replay.decisions)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_skull_lair_can_use_effect_twice_in_one_turn(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    own, opponent = _decks(tmp_path)

    with GoatEnvironment(str(own), str(opponent), 18,
                         ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, SKULL_LAIR, SKULL_SERVANT} <= {c.code for c in obs.hand}
        assert SKULL_SERVANT in {c.code for c in env.engine.probe.observation(1).hand}
        graceful = discarded = lair_set = lair_faceup = False
        own_summoned = opponent_summoned = False
        activations = costs = targets = resolved = 0
        agents = (RandomAgent(18), RandomAgent(19))
        for _ in range(3000):
            if env.is_terminal():
                break
            actions = env.legal_actions()

            def choice(kind, code=None, choices=actions):
                return next((a for a in choices if a.kind == kind
                             and (code is None or a.parameters.get("code") == code)), None)

            action = None
            if resolved < 2 and obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = choice("activate", GRACEFUL)
                    graceful |= action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if len(a.parameters["cards"]) == 2
                                   and all(card.get("code") != SKULL_SERVANT
                                           for card in a.parameters["cards"])), None)
                    assert action is not None
                    discarded = True
                if discarded and not lair_set and action is None:
                    action = choice("set_spell_trap", SKULL_LAIR)
                    lair_set |= action is not None
                if discarded and lair_set and not own_summoned and action is None:
                    action = choice("normal_summon", SKULL_SERVANT)
                    own_summoned |= action is not None
            if resolved < 2 and obs.acting_player == 1 and obs.turn == 2 \
                    and not opponent_summoned:
                action = choice("normal_summon", SKULL_SERVANT)
                opponent_summoned |= action is not None
            if opponent_summoned and not lair_faceup and obs.acting_player == 0:
                action = choice("chain", SKULL_LAIR) or choice("activate", SKULL_LAIR)
                lair_faceup |= action is not None
            if lair_faceup and activations < 2 and obs.acting_player == 0 \
                    and obs.chain == () and any(
                        c.code == SKULL_LAIR and c.position == "faceup" for c in obs.field):
                action = choice("chain", SKULL_LAIR) or choice("activate", SKULL_LAIR)
                if action is not None:
                    activations += 1
            if activations > costs and actions[0].kind in (
                    "select_card", "select_cards", "select_unselect_card"):
                grave = {card.code for card in obs.graveyards[0]}
                action = next((a for a in actions if a.parameters.get("location") == 16
                               and a.parameters.get("code") in grave), None)
                if action is not None:
                    costs += 1
            if costs > targets and actions[0].kind == "select_card":
                controller = 0 if targets == 0 else 1
                action = next((a for a in actions if a.parameters.get("location") == 4
                               and a.parameters.get("controller") == controller
                               and a.parameters.get("code") == SKULL_SERVANT), None)
                if action is not None:
                    targets += 1
            if action is None:
                action = (choice("pass") or choice("end_phase") or choice("place")
                          or actions[0] if resolved < 2 else
                          agents[obs.acting_player].select_action(obs, actions))
            obs = env.step(action)
            if costs > resolved and obs.chain == ():
                resolved += 1
                assert obs.turn == 2
                assert len(obs.banished[0]) == resolved
                remaining = [card.controller for card in obs.field
                             if card.code == SKULL_SERVANT and card.zone == "monster"]
                assert remaining == ([1] if resolved == 1 else [])
                assert SKULL_LAIR in {card.code for card in obs.field}
        assert graceful and discarded and lair_set and lair_faceup
        assert own_summoned and opponent_summoned
        assert (activations, costs, targets, resolved) == (2, 2, 2, 2)
        assert env.is_terminal()
        path = tmp_path / "skull_lair_twice_same_turn.json"
        write_trajectory(path, env.trajectory())
        replay = read_trajectory(path)
        assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(replay.decisions)
        assert audit_trajectory_visibility(replay)["decisions"] == len(replay.decisions)
