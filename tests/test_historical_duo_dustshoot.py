"""Dustshoot resolves before a chained-to Delinquent Duo discards cards."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

DUO = 44763025
DUSTSHOOT = 64697231


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("respond", [False, True])
def test_dustshoot_response_to_duo_reveals_only_duo_players_hand(tmp_path, respond):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (DUO, DUSTSHOOT)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("Duo or Dustshoot script not installed")
    duo_deck = tmp_path / "duo.ydk"
    duo_deck.write_text("#main\n" + "\n".join(map(str, (
        DUO, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    dust_deck = tmp_path / "dustshoot.ydk"
    dust_deck.write_text("#main\n" + "\n".join(map(str, (
        *([DUSTSHOOT] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(duo_deck), str(dust_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert DUO in {card.code for card in obs.hand}
        assert DUSTSHOOT in {card.code for card in env.engine.probe.observation(1).hand}
        trap_set = duo_used = response_seen = monster_chosen = second_chosen = False
        checked = False
        duo_hand_before = dust_hand_before = duo_deck_before = selected_code = None
        revealed = Counter()
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"duo_dustshoot_{respond}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                                             env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1 and not trap_set:
                action = next((candidate for candidate in actions
                               if candidate.kind == "set_spell_trap"
                               and candidate.parameters.get("code") == DUSTSHOOT), None)
                trap_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and trap_set and not duo_used:
                action = next((candidate for candidate in actions
                               if candidate.kind == "activate"
                               and candidate.parameters.get("code") == DUO), None)
                if action is not None:
                    duo_used = True
                    duo_hand_before = len(obs.hand) - 1
                    dust_hand_before = obs.opponent_hand_count
                    duo_deck_before = obs.deck_counts[0]
            if duo_used and obs.acting_player == 1 and not response_seen:
                chain = next((candidate for candidate in actions
                              if candidate.kind == "chain"
                              and candidate.parameters.get("code") == DUSTSHOOT), None)
                if chain is not None:
                    assert [link.card_code for link in obs.chain] == [DUO]
                    assert obs.opponent_hand_count >= 4
                    assert not obs.private_reveals
                    action = chain if respond else next(
                        candidate for candidate in actions if candidate.kind == "pass")
                    response_seen = True
            if respond and response_seen and not monster_chosen \
                    and actions[0].kind == "select_card":
                assert [link.card_code for link in obs.chain] == [DUO, DUSTSHOOT]
                assert obs.acting_player == 1
                revealed = Counter(card.code for event in obs.private_reveals
                                   if event.recipient == 1 for card in event.cards
                                   if card.controller == 0 and card.location == 2)
                assert sum(revealed.values()) == duo_hand_before
                assert Counter(obs.known_opponent_hand_cards) == revealed
                assert not env.engine.probe.observation(0).private_reveals
                assert all("sequence" not in candidate.parameters for candidate in actions)
                action = next((candidate for candidate in actions
                               if candidate.parameters.get("code") in revealed), None)
                assert action is not None
                selected_code = action.parameters["code"]
                monster_chosen = True
            if action is None and response_seen and obs.acting_player == 1 \
                    and not second_chosen \
                    and (not respond or monster_chosen) \
                    and actions[0].kind == "select_card":
                assert len(obs.hand) == dust_hand_before - 1
                assert obs.life_points[0] == 7000
                action = actions[0]
                second_chosen = True
            if action is None and not checked:
                action = next((candidate for candidate in actions
                               if candidate.kind in ("place", "pass", "end_phase")),
                              actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if response_seen and not checked and DUO in {
                    card.code for card in obs.graveyards[0]} and not obs.chain:
                watcher = env.engine.probe.observation(1)
                duo_player = env.engine.probe.observation(0)
                assert second_chosen
                assert duo_player.life_points == (7000, 8000)
                assert watcher.deck_counts[0] == duo_deck_before + int(respond)
                assert watcher.opponent_hand_count == duo_hand_before - int(respond)
                assert len(watcher.hand) == dust_hand_before - 2
                if respond:
                    assert monster_chosen
                    assert Counter(watcher.known_opponent_hand_cards) == (
                        revealed - Counter((selected_code,)))
                    assert DUSTSHOOT in {card.code for card in watcher.graveyards[1]}
                else:
                    assert not watcher.private_reveals
                    assert not watcher.known_opponent_hand_cards
                    assert any(card.code == DUSTSHOOT for card in watcher.field)
                assert not duo_player.private_reveals
                assert not duo_player.known_opponent_hand_cards
                loaded = env.engine.probe.loaded_script_sha256
                if respond:
                    assert scripts <= loaded.keys()
                else:
                    assert f"official/c{DUO}.lua" in loaded
                checked = True
    pytest.fail("Duo / Dustshoot response duel did not finish")
