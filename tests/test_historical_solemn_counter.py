"""Paired Solemn-on-Solemn branches around Pot of Greed in GOAT mode."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

POT = 55144522
SOLEMN = 41420027


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("counter_first_solemn", [False, True])
def test_solemn_counter_trap_chain_preserves_pot_when_countered(
        tmp_path, counter_first_solemn):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (POT, SOLEMN)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required official card scripts not installed")
    first_cards = list(VANILLA_DECK)
    first_cards[0], first_cards[1] = POT, SOLEMN
    second_cards = list(VANILLA_DECK)
    second_cards[0] = SOLEMN
    decks = []
    for seat, cards in enumerate((first_cards, second_cards)):
        path = tmp_path / f"solemn_{seat}.ydk"
        path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
        decks.append(str(path))

    with GoatEnvironment(*decks, seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert {POT, SOLEMN} <= {card.code for card in observation.hand}
        assert SOLEMN in {card.code for card in env.engine.probe.observation(1).hand}
        set_cards = set()
        pot_activated = first_counter = second_counter = False
        hand_before = deck_before = None
        three_links_seen = False
        for _ in range(100):
            actions = env.legal_actions()
            action = None
            if len(observation.chain) == 3:
                assert counter_first_solemn
                assert [(link.card_code, link.controller) for link in observation.chain] \
                    == [(POT, 0), (SOLEMN, 1), (SOLEMN, 0)]
                three_links_seen = True
            if observation.acting_player in (0, 1) and observation.turn <= 2 \
                    and observation.acting_player not in set_cards:
                action = next((candidate for candidate in actions
                               if candidate.kind == "set_spell_trap"
                               and candidate.parameters.get("code") == SOLEMN), None)
                if action is not None:
                    set_cards.add(observation.acting_player)
            if observation.turn == 3 and observation.acting_player == 0 \
                    and len(set_cards) == 2 and not pot_activated:
                action = next((candidate for candidate in actions
                               if candidate.kind == "activate"
                               and candidate.parameters.get("code") == POT), None)
                if action is not None:
                    opposing_backrow = [card for card in observation.field
                                        if card.controller == 1
                                        and card.zone == "spell_trap"]
                    assert len(opposing_backrow) == 1
                    assert opposing_backrow[0].code is None
                    hand_before = len(observation.hand)
                    deck_before = observation.deck_counts[0]
                    pot_activated = True
            if pot_activated and not first_counter and observation.acting_player == 1:
                action = next((candidate for candidate in actions
                               if candidate.kind == "chain"
                               and candidate.parameters.get("code") == SOLEMN), None)
                if action is not None:
                    assert tuple(link.card_code for link in observation.chain) == (POT,)
                    first_counter = True
            if first_counter and not second_counter and observation.acting_player == 0 \
                    and tuple(link.card_code for link in observation.chain) == (POT, SOLEMN):
                counter = next((candidate for candidate in actions
                                if candidate.kind == "chain"
                                and candidate.parameters.get("code") == SOLEMN), None)
                if counter_first_solemn:
                    assert counter is not None
                    action = counter
                    second_counter = True
                else:
                    assert counter is not None
                    action = next(candidate for candidate in actions
                                  if candidate.kind == "pass")
                    second_counter = True
            if action is None:
                action = next((candidate for candidate in actions if candidate.kind in
                               ("place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if pot_activated and second_counter and not observation.chain \
                    and POT in {card.code for card in observation.graveyards[0]}:
                break
        else:
            pytest.fail("Solemn counter chain did not resolve")

        assert observation.life_points == ((4000, 4000) if counter_first_solemn
                                           else (8000, 4000))
        assert three_links_seen == counter_first_solemn
        assert observation.deck_counts[0] == deck_before - (2 if counter_first_solemn else 0)
        assert len(observation.hand) == hand_before + (2 if counter_first_solemn else 0) - 1
        assert sum(card.code == SOLEMN for card in observation.graveyards[0]) \
            == int(counter_first_solemn)
        assert sum(card.code == SOLEMN for card in observation.graveyards[1]) == 1
        assert scripts <= env.engine.probe.loaded_script_sha256.keys()

        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(3000):
            if env.is_terminal():
                break
            observation = env.step(agents[observation.acting_player].select_action(
                observation, env.legal_actions()))
        assert env.is_terminal()
        path = tmp_path / f"solemn_counter_{counter_first_solemn}.json"
        write_trajectory(path, env.trajectory())
        trajectory = read_trajectory(path)
        audit_trajectory_visibility(trajectory)
        assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) \
            == len(trajectory.decisions)
