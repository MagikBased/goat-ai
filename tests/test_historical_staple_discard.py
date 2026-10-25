"""Common GOAT draw/discard staples and their information boundaries."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

GRACEFUL_CHARITY = 79571449
DELINQUENT_DUO = 44763025
DUSTSHOOT = 64697231
SINISTER_SERPENT = 511000818


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_graceful_and_duo_discard_choices_keep_hands_private(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (GRACEFUL_CHARITY, DELINQUENT_DUO):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    deck = tmp_path / "staples.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL_CHARITY, DELINQUENT_DUO, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        graceful_chosen = graceful_resolved = duo_chosen = False
        for _ in range(35):
            actions = env.legal_actions()
            action = None
            if actions[0].kind == "select_cards" and not graceful_chosen:
                assert observation.viewer == observation.acting_player == 0
                assert len(observation.hand) == 8
                assert observation.deck_counts[0] == 31
                assert len(actions) == 28
                hand = Counter(card.code for card in observation.hand)
                for choice in actions:
                    selected = choice.parameters["cards"]
                    assert len(selected) == 2
                    assert all(card["controller"] == 0 and card["location"] == 2
                               for card in selected)
                    assert not Counter(card["code"] for card in selected) - hand
                other = env.engine.probe.observation(1)
                assert other.opponent_hand_count == 8
                assert not other.private_reveals
                assert all(card.controller == 1 for card in other.hand)
                graceful_chosen = True
                action = actions[0]
            elif actions[0].kind == "select_card" and duo_chosen:
                assert observation.viewer == observation.acting_player == 1
                assert len(observation.hand) == 4
                assert len(observation.graveyards[1]) == 1
                assert observation.life_points == (7000, 8000)
                assert len(actions) == 4
                assert {choice.parameters["sequence"] for choice in actions} == set(range(4))
                assert all(choice.parameters["controller"] == 1
                           and choice.parameters["location"] == 2 for choice in actions)
                other = env.engine.probe.observation(0)
                assert other.opponent_hand_count == 4
                assert not other.private_reveals
                assert all(card.controller == 0 for card in other.hand)
                selected_code = actions[0].parameters["code"]
                observation = env.step(actions[0])
                assert len(observation.graveyards[1]) == 2
                assert selected_code in [card.code for card in observation.graveyards[1]]
                assert env.engine.probe.observation(1).opponent_hand_count == 5
                return

            if (graceful_chosen and not graceful_resolved
                    and len(observation.graveyards[0]) == 3):
                graceful_resolved = True
                assert len(env.engine.probe.observation(0).hand) == 6
                assert env.engine.probe.observation(0).deck_counts[0] == 31
                assert env.engine.probe.observation(1).opponent_hand_count == 6
                assert env.engine.probe.observation(0).opponent_hand_count == 5
            if graceful_resolved and not duo_chosen and observation.acting_player == 0:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == DELINQUENT_DUO), action)
                duo_chosen |= action is not None and action.kind == "activate"
            if not graceful_chosen and observation.acting_player == 0:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == GRACEFUL_CHARITY), action)
            if action is None:
                action = next((a for a in actions if a.kind in ("place", "pass")), None)
            if action is None:
                action = next((a for a in actions if a.kind == "end_phase"), actions[0])
            observation = env.step(action)
    pytest.fail("Graceful Charity and Delinquent Duo did not reach both discard choices")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_duo_discards_serpent_then_opponent_recovers_it_at_standby(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"official/c{DELINQUENT_DUO}.lua",
                     f"pre-errata/c{SINISTER_SERPENT}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    attacker = tmp_path / "duo.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        DELINQUENT_DUO, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    defender = tmp_path / "serpent.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        SINISTER_SERPENT, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(attacker), str(defender), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert DELINQUENT_DUO in {c.code for c in obs.hand}
        assert SINISTER_SERPENT in {
            c.code for c in env.engine.probe.observation(1).hand}
        duo_used = discarded = recovered = False
        defender_hand_before_return = None
        for _ in range(45):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not duo_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == DELINQUENT_DUO), None)
                duo_used |= action is not None
            if duo_used and not discarded and obs.acting_player == 1 \
                    and actions[0].kind == "select_card":
                assert obs.viewer == 1
                assert obs.life_points == (7000, 8000)
                assert not env.engine.probe.observation(0).private_reveals
                if SINISTER_SERPENT in {c.code for c in obs.hand}:
                    action = next((a for a in actions if a.parameters.get("code")
                                   == SINISTER_SERPENT), None)
                else:
                    action = actions[0]
                discarded = True
            if discarded and obs.turn == 2 and obs.phase == "standby" \
                    and obs.acting_player == 1 and not recovered:
                choices = {a.kind: a for a in actions
                           if a.parameters.get("code") == SINISTER_SERPENT}
                assert {"yes", "no"}.issubset(choices)
                assert SINISTER_SERPENT in {c.code for c in obs.graveyards[1]}
                assert SINISTER_SERPENT not in {c.code for c in obs.hand}
                defender_hand_before_return = len(obs.hand)
                action = choices["yes"]
                recovered = True
            if recovered and obs.turn == 2 and obs.phase == "main1" \
                    and obs.acting_player == 1:
                assert obs.life_points == (7000, 8000)
                assert SINISTER_SERPENT in {c.code for c in obs.hand}
                assert SINISTER_SERPENT not in {c.code for c in obs.graveyards[1]}
                assert len(obs.hand) == defender_hand_before_return + 1
                attacker_view = env.engine.probe.observation(0)
                assert attacker_view.opponent_hand_count == len(obs.hand)
                assert attacker_view.known_opponent_hand_cards == (SINISTER_SERPENT,)
                assert not attacker_view.private_reveals
                assert {f"official/c{DELINQUENT_DUO}.lua",
                        f"pre-errata/c{SINISTER_SERPENT}.lua"}.issubset(
                    env.engine.probe.loaded_script_sha256)
                agents = (RandomAgent(52), RandomAgent(53))
                for _ in range(5000):
                    action = agents[obs.acting_player].select_action(
                        obs, env.legal_actions())
                    obs = env.step(action)
                    if env.is_terminal():
                        trajectory = env.trajectory()
                        break
                else:
                    pytest.fail("Duo/Serpent replay did not reach a terminal state")
                assert any(SINISTER_SERPENT in record.observation.known_opponent_hand_cards
                           for record in trajectory.decisions)
                path = tmp_path / "duo_serpent.json"
                write_trajectory(path, trajectory)
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    trajectory.decisions)
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
    pytest.fail("Duo discard and Serpent's Standby Phase return did not resolve")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("empty_hand", [False, True])
def test_duo_one_card_hand_activation_boundary(tmp_path, empty_hand):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{DELINQUENT_DUO}.lua").is_file():
        pytest.skip("Delinquent Duo script not installed")
    backrow = (14087893, 60082869, 12607053, 56120475, 94192409,
               4178474, 35316708)
    attacker = tmp_path / "duo.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        DELINQUENT_DUO, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    defender = tmp_path / "set_five.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        *(code for code in backrow for _ in range(3)), *VANILLA_DECK[:19])))
                        + "\n#extra\n!side\n")
    with GoatEnvironment(str(attacker), str(defender), seed=260,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert DELINQUENT_DUO in {card.code for card in obs.hand}
        set_count = 0
        activated = False
        hand_before = None
        grave_before = None
        for _ in range(65):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1:
                if set_count < 5:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") in backrow), None)
                    if action is not None:
                        set_count += 1
                elif empty_hand and obs.hand:
                    action = next((a for a in actions if a.kind == "set_monster"), None)
            if obs.turn == 3 and obs.phase == "main1" and obs.acting_player == 0 \
                    and set_count == 5 \
                    and not activated:
                assert obs.opponent_hand_count == (0 if empty_hand else 1)
                assert len([c for c in obs.field if c.controller == 1
                            and c.zone == "spell_trap"]) == 5
                if empty_hand:
                    assert any(c.controller == 1 and c.zone == "monster"
                               and c.position == "facedown" and c.code is None
                               for c in obs.field)
                    assert DELINQUENT_DUO in {c.code for c in obs.hand}
                    assert not any(a.kind == "activate"
                                   and a.parameters.get("code") == DELINQUENT_DUO
                                   for a in actions)
                    assert obs.life_points == (8000, 8000)
                    assert not obs.graveyards[1]
                    return
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == DELINQUENT_DUO), None)
                assert action is not None
                hand_before = len(env.engine.probe.observation(1).hand)
                grave_before = len(obs.graveyards[1])
                activated = True
            if activated and obs.acting_player == 1:
                assert not any(a.kind == "select_card" for a in actions)
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if activated and DELINQUENT_DUO in {c.code for c in obs.graveyards[0]}:
                owner = env.engine.probe.observation(1)
                assert hand_before == 1
                assert len(owner.hand) == obs.opponent_hand_count == 0
                assert len(obs.graveyards[1]) == grave_before + 1
                assert obs.life_points == (7000, 8000)
                assert not obs.private_reveals
                assert not owner.private_reveals
                assert f"official/c{DELINQUENT_DUO}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("one-card Delinquent Duo branch did not resolve")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_duo_updates_dustshoot_known_hand_after_both_discards(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (DUSTSHOOT, DELINQUENT_DUO):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    deck = tmp_path / "dustshoot_duo.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        *([DUSTSHOOT] * 3), DELINQUENT_DUO, *VANILLA_DECK[4:])))
                    + "\n#extra\n!side\n")
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {DUSTSHOOT, DELINQUENT_DUO}.issubset(c.code for c in obs.hand)
        trap_set = dustshoot_used = returned = duo_used = second_discard = False
        revealed = Counter()
        before_duo = Counter()
        for _ in range(65):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not trap_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                trap_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 0 and trap_set \
                    and not dustshoot_used:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                dustshoot_used |= action is not None
            if dustshoot_used and not returned and actions[0].kind == "select_card":
                assert obs.acting_player == 0
                revealed = Counter(obs.known_opponent_hand_cards)
                assert revealed == Counter(c.code for c in
                                           env.engine.probe.observation(1).hand)
                action = actions[0]
                returned = True
            if obs.turn == 3 and obs.phase == "main1" and obs.acting_player == 0 \
                    and returned and not duo_used:
                before_duo = Counter(obs.known_opponent_hand_cards)
                assert before_duo == Counter(c.code for c in
                                             env.engine.probe.observation(1).hand)
                assert sum(before_duo.values()) == 5
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == DELINQUENT_DUO), None)
                duo_used |= action is not None
            if duo_used and obs.acting_player == 1 \
                    and actions[0].kind == "select_card" and not second_discard:
                remaining = Counter(c.code for c in obs.hand)
                assert sum(remaining.values()) == 4
                assert Counter(env.engine.probe.observation(0)
                               .known_opponent_hand_cards) == remaining
                assert sum(before_duo.values()) == sum(remaining.values()) + 1
                action = actions[0]
                second_discard = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if second_discard and DELINQUENT_DUO in {c.code for c in obs.graveyards[0]}:
                other = env.engine.probe.observation(1)
                assert Counter(env.engine.probe.observation(0)
                               .known_opponent_hand_cards) == Counter(
                                   c.code for c in other.hand)
                assert len(other.hand) == 3
                assert obs.life_points == (7000, 8000)
                assert {f"official/c{DUSTSHOOT}.lua",
                        f"official/c{DELINQUENT_DUO}.lua"}.issubset(
                            env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Dustshoot/Duo known-hand sequence did not resolve")
