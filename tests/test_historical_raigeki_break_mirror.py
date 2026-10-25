"""Destroying an activated Raigeki Break does not negate its pending effect."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

BREAK = 4178474


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("respond", [False, True])
def test_break_answering_break_destroys_source_but_not_pending_effect(tmp_path, respond):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    script = f"official/c{BREAK}.lua"
    if not (root / "scripts" / script).is_file():
        pytest.skip("Raigeki Break script not installed")
    decks = []
    for name in ("first", "second"):
        path = tmp_path / f"{name}.ydk"
        path.write_text("#main\n" + "\n".join(map(str, (
            *([BREAK] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
        decks.append(str(path))

    with GoatEnvironment(*decks, seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert BREAK in {card.code for card in obs.hand}
        assert BREAK in {card.code for card in env.engine.probe.observation(1).hand}
        first_set = second_set = summoned = first_used = first_discarded = False
        first_targeted = response_seen = second_discarded = second_targeted = False
        checked = False
        monster_code = None
        hands_before = None
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"break_mirror_{respond}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                                             env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not first_set:
                action = next((candidate for candidate in actions
                               if candidate.kind == "set_spell_trap"
                               and candidate.parameters.get("code") == BREAK), None)
                first_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not summoned:
                    action = next((candidate for candidate in actions
                                   if candidate.kind == "normal_summon"), None)
                    if action is not None:
                        monster_code = action.parameters["code"]
                        summoned = True
                if summoned and not second_set and action is None:
                    action = next((candidate for candidate in actions
                                   if candidate.kind == "set_spell_trap"
                                   and candidate.parameters.get("code") == BREAK), None)
                    second_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and second_set \
                    and not first_used:
                action = next((candidate for candidate in actions
                               if candidate.kind == "chain"
                               and candidate.parameters.get("code") == BREAK), None)
                if action is None:
                    action = next((candidate for candidate in actions
                                   if candidate.kind == "activate"
                                   and candidate.parameters.get("code") == BREAK), None)
                if action is not None:
                    first_used = True
                    hands_before = (len(obs.hand), obs.opponent_hand_count)
            if first_used and not first_discarded and action is None \
                    and obs.acting_player == 0 and actions[0].kind == "select_card":
                action = next((candidate for candidate in actions
                               if candidate.parameters.get("location") == 2), None)
                first_discarded = action is not None
            if first_discarded and not first_targeted and action is None \
                    and obs.acting_player == 0 and actions[0].kind == "select_card":
                action = next((candidate for candidate in actions
                               if candidate.parameters.get("controller") == 1
                               and candidate.parameters.get("location") == 4
                               and candidate.parameters.get("code") == monster_code), None)
                first_targeted = action is not None
            if first_targeted and obs.acting_player == 1 and not response_seen:
                option = next((candidate for candidate in actions
                               if candidate.kind == "chain"
                               and candidate.parameters.get("code") == BREAK), None)
                if option is not None:
                    assert [link.card_code for link in obs.chain] == [BREAK]
                    action = option if respond else next(
                        candidate for candidate in actions if candidate.kind == "pass")
                    response_seen = True
            if respond and response_seen and not second_discarded and action is None \
                    and obs.acting_player == 1 and actions[0].kind == "select_card":
                action = next((candidate for candidate in actions
                               if candidate.parameters.get("location") == 2), None)
                second_discarded = action is not None
            if respond and second_discarded and not second_targeted and action is None \
                    and obs.acting_player == 1 and actions[0].kind == "select_card":
                assert [link.card_code for link in obs.chain] == [BREAK, BREAK]
                action = next((candidate for candidate in actions
                               if candidate.parameters.get("controller") == 0
                               and candidate.parameters.get("location") == 8
                               and candidate.parameters.get("code") == BREAK), None)
                second_targeted = action is not None
            if action is None and not checked:
                action = next((candidate for candidate in actions
                               if candidate.kind in ("place", "pass", "end_phase")),
                              actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if response_seen and not checked and not obs.chain \
                    and BREAK in {card.code for card in obs.graveyards[0]}:
                first = env.engine.probe.observation(0)
                second = env.engine.probe.observation(1)
                assert monster_code in {card.code for card in second.graveyards[1]}
                assert not any(card.controller == 1 and card.zone == "monster"
                               for card in first.field)
                assert len(first.hand) == hands_before[0] - 1
                assert second.opponent_hand_count == hands_before[0] - 1
                assert first.opponent_hand_count == hands_before[1] - int(respond)
                assert sum(card.code == BREAK for card in first.graveyards[0]) == 1
                assert sum(card.code == BREAK for card in second.graveyards[1]) \
                    == int(respond)
                assert second_targeted == respond
                assert script in env.engine.probe.loaded_script_sha256
                checked = True
    pytest.fail("Raigeki Break mirror duel did not finish")
