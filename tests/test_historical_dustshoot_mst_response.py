"""Dustshoot can answer Typhoon targeting its Set field slot."""

import os
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

DUSTSHOOT = 64697231
MST = 5318639


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("respond", [False, True])
def test_dustshoot_response_to_mst_targeting_it_resolves_before_destruction(
        tmp_path, respond):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (DUSTSHOOT, MST)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("Dustshoot or Typhoon script not installed")
    dust_deck = tmp_path / "dustshoot.ydk"
    dust_deck.write_text("#main\n" + "\n".join(map(str, (
        *([DUSTSHOOT] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    mst_deck = tmp_path / "mst.ydk"
    mst_deck.write_text("#main\n" + "\n".join(map(str, (
        MST, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(dust_deck), str(mst_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert DUSTSHOOT in {c.code for c in obs.hand}
        assert MST in {c.code for c in env.engine.probe.observation(1).hand}
        trap_set = mst_used = target_chosen = response_seen = monster_chosen = False
        checked = False
        deck_before = hand_after_mst = selected_code = None
        revealed = Counter()
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"dustshoot_mst_response_{respond}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                                             env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not trap_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                trap_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and trap_set and not mst_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == MST), None)
                if action is not None:
                    assert any(c.controller == 0 and c.zone == "spell_trap"
                               and c.position == "facedown" and c.code is None
                               for c in obs.field)
                    deck_before = obs.deck_counts[1]
                    mst_used = True
            if mst_used and not target_chosen and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 0
                               and a.parameters.get("location") == 8
                               and "code" not in a.parameters), None)
                assert action is not None
                target_chosen = True
            if target_chosen and obs.acting_player == 0 and not response_seen:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                if option is not None:
                    assert [link.card_code for link in obs.chain] == [MST]
                    hand_after_mst = obs.opponent_hand_count
                    assert hand_after_mst >= 4
                    action = option if respond else next(
                        (a for a in actions if a.kind == "pass"), None)
                    assert action is not None
                    response_seen = True
            if respond and response_seen and not monster_chosen \
                    and actions[0].kind == "select_card":
                assert [(link.index, link.card_code) for link in obs.chain] == [
                    (1, MST), (2, DUSTSHOOT)]
                revealed = Counter(c.code for event in obs.private_reveals
                                   if event.recipient == 0 for c in event.cards
                                   if c.controller == 1 and c.location == 2)
                assert sum(revealed.values()) == hand_after_mst
                assert Counter(obs.known_opponent_hand_cards) == revealed
                assert not env.engine.probe.observation(1).private_reveals
                assert all("sequence" not in a.parameters for a in actions)
                action = next((a for a in actions if a.parameters.get("code")
                               in revealed), None)
                assert action is not None
                selected_code = action.parameters["code"]
                monster_chosen = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if response_seen and not checked and {DUSTSHOOT, MST}.issubset(
                    {c.code for pile in obs.graveyards for c in pile}):
                chooser = env.engine.probe.observation(0)
                spell_player = env.engine.probe.observation(1)
                assert not obs.chain
                assert DUSTSHOOT in {c.code for c in chooser.graveyards[0]}
                assert MST in {c.code for c in chooser.graveyards[1]}
                assert chooser.life_points == (8000, 8000)
                assert chooser.deck_counts[1] == deck_before + int(respond)
                assert chooser.opponent_hand_count == hand_after_mst - int(respond)
                if respond:
                    assert monster_chosen
                    assert Counter(chooser.known_opponent_hand_cards) == (
                        revealed - Counter((selected_code,)))
                else:
                    assert not chooser.private_reveals
                    assert not chooser.known_opponent_hand_cards
                assert not spell_player.private_reveals
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail("Dustshoot / Typhoon response duel did not finish")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_dustshoot_response_options_ignore_unrevealed_opponent_hand_card(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    dust_deck = tmp_path / "dustshoot.ydk"
    dust_deck.write_text("#main\n" + "\n".join(map(str, (
        *([DUSTSHOOT] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    def run(hidden_code):
        opponent_cards = [MST, *VANILLA_DECK[1:]]
        opponent_cards[6] = hidden_code
        opponent_deck = tmp_path / f"mst_hidden_{hidden_code}.ydk"
        opponent_deck.write_text("#main\n" + "\n".join(map(str, opponent_cards))
                                 + "\n#extra\n!side\n")
        with GoatEnvironment(str(dust_deck), str(opponent_deck), seed=52,
                             engine=ExperimentalOcgcoreEngine(root)) as env:
            obs = env.reset()
            assert hidden_code in {c.code for c in env.engine.probe.observation(1).hand}
            trap_set = mst_used = target_chosen = False
            before = after = None
            for _ in range(35):
                actions = env.legal_actions()
                action = None
                if obs.turn == 1 and obs.acting_player == 0 and not trap_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == DUSTSHOOT), None)
                    trap_set |= action is not None
                if obs.turn == 2 and obs.acting_player == 1 and trap_set and not mst_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == MST), None)
                    mst_used |= action is not None
                if mst_used and not target_chosen and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("controller") == 0
                                   and a.parameters.get("location") == 8
                                   and "code" not in a.parameters), None)
                    target_chosen |= action is not None
                if target_chosen and obs.acting_player == 0 and before is None:
                    assert obs.known_opponent_hand_cards == ()
                    assert not obs.private_reveals
                    assert any(a.kind == "chain" and a.parameters.get("code") == DUSTSHOOT
                               for a in actions)
                    before = (obs, actions)
                    action = next(a for a in actions if a.kind == "chain"
                                  and a.parameters.get("code") == DUSTSHOOT)
                if action is None:
                    action = next((a for a in actions if a.kind in (
                        "place", "pass", "end_phase")), actions[0])
                obs = env.step(action)
                if before is not None and obs.private_reveals:
                    after = obs
                    assert [link.card_code for link in obs.chain] == [MST, DUSTSHOOT]
                    assert not env.engine.probe.observation(1).private_reveals
                    break
            assert trap_set and mst_used and target_chosen
            assert before is not None and after is not None
            return before, after

    (before_a, after_a) = run(VANILLA_DECK[6])
    (before_b, after_b) = run(VANILLA_DECK[0])
    assert before_a == before_b
    assert after_a != after_b
    assert replace(after_a, private_reveals=(), known_opponent_hand_cards=()) == replace(
        after_b, private_reveals=(), known_opponent_hand_cards=())
    assert VANILLA_DECK[6] in after_a.known_opponent_hand_cards
    assert VANILLA_DECK[0] in after_b.known_opponent_hand_cards
