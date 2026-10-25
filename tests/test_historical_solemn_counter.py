"""A second Solemn Judgment negates the first, allowing Pot to draw."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

POT = 55144522
SOLEMN = 41420027


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_solemn_counters_solemn_and_pot_resolves(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (POT, SOLEMN)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required official card script not installed")
    decks = []
    for name, cards in (("pot_and_solemn", (POT, SOLEMN, *VANILLA_DECK[2:])),
                        ("solemn", (SOLEMN, *VANILLA_DECK[1:]))):
        deck = tmp_path / f"{name}.ydk"
        deck.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
        decks.append(deck)

    with GoatEnvironment(*(str(deck) for deck in decks), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {POT, SOLEMN} <= {card.code for card in obs.hand}
        assert SOLEMN in {card.code for card in env.engine.probe.observation(1).hand}
        own_set = opposing_set = pot_used = first_chained = second_chained = False
        hand_before = deck_before = None
        for _ in range(75):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not own_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SOLEMN), None)
                own_set = action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not opposing_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SOLEMN), action)
                opposing_set |= action is not None and action.kind == "set_spell_trap"
            if obs.turn == 3 and obs.acting_player == 0 and not pot_used:
                assert own_set and opposing_set
                hidden_backrow = [card for card in obs.field
                                  if card.controller == 1 and card.zone == "spell_trap"]
                assert len(hidden_backrow) == 1
                assert hidden_backrow[0].code is None
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == POT), None)
                if action is not None:
                    pot_used = True
                    hand_before = len(obs.hand)
                    deck_before = obs.deck_counts[0]
            if pot_used and obs.acting_player == 1 and not first_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SOLEMN), action)
                first_chained |= action is not None and action.kind == "chain"
                if first_chained:
                    assert [link.card_code for link in obs.chain] == [POT]
            if first_chained and obs.acting_player == 0 and not second_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SOLEMN), action)
                second_chained |= action is not None and action.kind == "chain"
                if second_chained:
                    assert [link.card_code for link in obs.chain] == [POT, SOLEMN]
                    assert obs.life_points == (8000, 4000)
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if second_chained and POT in {c.code for c in obs.graveyards[0]} \
                    and not obs.chain:
                own = env.engine.probe.observation(0)
                assert own.life_points == (4000, 4000)
                assert len(own.hand) == hand_before + 1
                assert own.deck_counts[0] == deck_before - 2
                assert SOLEMN in {c.code for c in own.graveyards[0]}
                assert SOLEMN in {c.code for c in own.graveyards[1]}
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                break
        else:
            pytest.fail("Solemn/Solemn/Pot chain did not resolve")

        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(3000):
            if env.is_terminal():
                break
            obs = env.step(agents[obs.acting_player].select_action(obs, env.legal_actions()))
        else:
            pytest.fail("Solemn/Solemn duel exceeded 3000 decisions")
        trajectory = env.trajectory()
        assert trajectory.winner in (0, 1, None)
        assert any([link.card_code for link in record.observation.chain] == [POT, SOLEMN]
                   and record.selected_action.kind == "chain"
                   and record.selected_action.parameters.get("code") == SOLEMN
                   for record in trajectory.decisions)
        assert any([(link.card_code, link.controller)
                    for link in record.observation.chain] == [
                        (POT, 0), (SOLEMN, 1), (SOLEMN, 0)]
                   for record in trajectory.decisions)
    path = tmp_path / "solemn_counter.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    assert verify_trajectory(loaded, ExperimentalOcgcoreEngine(root)) == len(
        trajectory.decisions)
