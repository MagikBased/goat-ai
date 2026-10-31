"""Spell Shield Type-8's two historical Spell-negation modes."""

import os
from dataclasses import replace
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.agents.card_metadata import load_card_effect_texts
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

BOOK = 14087893
POT = 55144522
SHIELD = 38275183
UPSTART = 70368879


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("spell", [BOOK, POT])
def test_spell_shield_negation_modes_and_cost_visibility(tmp_path, spell):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (BOOK, POT, SHIELD, UPSTART)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required official card script not installed")
    texts = load_card_effect_texts(root, {SHIELD})
    assert "targets 1 monster" in texts[(SHIELD, 0)]
    assert "Spell Card from your hand" in texts[(SHIELD, 1)]
    own = tmp_path / "spells.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        BOOK, POT, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    other_cards = list(VANILLA_DECK)
    other_cards[0] = SHIELD
    other_cards[4] = UPSTART
    other = tmp_path / "shield.ydk"
    other.write_text("#main\n" + "\n".join(map(str, other_cards))
                     + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(other), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {BOOK, POT} <= {card.code for card in obs.hand}
        assert {SHIELD, UPSTART} <= {card.code for card in
                                    env.engine.probe.observation(1).hand}
        summoned = shield_set = spell_used = response_chosen = checked = False
        target_chosen = False
        monster_code = None
        deck_before = None
        agents = (RandomAgent(3827), RandomAgent(5183))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"spell_shield_{spell}.json"
                write_trajectory(path, env.trajectory())
                replay = read_trajectory(path)
                assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(
                    replay.decisions)
                audit_trajectory_visibility(replay)
                if spell == BOOK:
                    with pytest.raises(ValueError, match="schema v28"):
                        write_trajectory(tmp_path / "invalid_v27.json",
                                         replace(replay, schema_version=27))
                    def old_action(action):
                        return replace(action, parameters={
                            key: value for key, value in action.parameters.items()
                            if key != "effect_option"})

                    old_records = tuple(replace(record,
                        legal_actions=tuple(old_action(action)
                                            for action in record.legal_actions),
                        selected_action=old_action(record.selected_action))
                        for record in replay.decisions)
                    def old_view(view):
                        return replace(
                            view,
                            hand=tuple(replace(card, level=None)
                                       for card in view.hand),
                            field=tuple(replace(card, attribute=None, level=None)
                                        for card in view.field))

                    old = replace(replay, schema_version=27,
                                  decisions=tuple(replace(record,
                                      observation=old_view(record.observation))
                                      for record in old_records),
                                  terminal_observation=old_view(
                                      replay.terminal_observation))
                    old_path = tmp_path / "spell_shield_v27.json"
                    write_trajectory(old_path, old)
                    assert verify_trajectory(read_trajectory(old_path),
                                             ExperimentalOcgcoreEngine(root)) == len(old_records)
                return
            actions = env.legal_actions()
            action = None
            if not checked and spell == BOOK and obs.turn == 1 \
                    and obs.acting_player == 0 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    summoned = True
                    monster_code = action.parameters["code"]
            if not checked and obs.turn == 2 and obs.acting_player == 1 \
                    and not shield_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SHIELD), None)
                shield_set = action is not None
            if not checked and shield_set and obs.turn == 3 \
                    and obs.acting_player == 0 and not spell_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == spell), None)
                if action is not None:
                    spell_used = True
                    deck_before = obs.deck_counts[0]
            if not checked and spell == BOOK and spell_used and not target_chosen \
                    and obs.acting_player == 0 and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == monster_code
                               and a.parameters.get("controller") == 0), None)
                target_chosen = action is not None
            if not checked and spell_used and obs.acting_player == 1 \
                    and not response_chosen:
                shield_choices = [a for a in actions if a.kind == "chain"
                                  and a.parameters.get("code") == SHIELD]
                if shield_choices:
                    assert [link.card_code for link in obs.chain] == [spell]
                    assert len(shield_choices) == (2 if spell == BOOK else 1)
                    if spell == BOOK:
                        assert [candidate.parameters.get("effect_option")
                                for candidate in shield_choices] == [0, 1]
                    assert spell != BOOK or target_chosen
                    assert UPSTART in {card.code for card in obs.hand}
                    assert not obs.known_opponent_hand_cards
                    action = shield_choices[0]
                    response_chosen = True
            if not checked and spell == POT and response_chosen \
                    and obs.acting_player == 1 and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == UPSTART), None)
                assert action is not None
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            cost_choice = (spell == POT and response_chosen
                           and action.kind == "select_card"
                           and action.parameters.get("code") == UPSTART)
            obs = env.step(action)
            if cost_choice:
                assert [link.card_code for link in obs.chain] == [POT, SHIELD]
                assert UPSTART in {card.code for card in obs.graveyards[1]}
                assert obs.deck_counts[0] == deck_before
            if not checked and response_chosen and not obs.chain \
                    and spell in {card.code for card in obs.graveyards[0]}:
                assert obs.deck_counts[0] == deck_before
                assert SHIELD in {card.code for card in obs.graveyards[1]}
                other_view = env.engine.probe.observation(1)
                if spell == BOOK:
                    assert UPSTART in {card.code for card in other_view.hand}
                    monster = next(card for card in obs.field if card.code == monster_code)
                    assert monster.position == "faceup"
                else:
                    assert UPSTART in {card.code for card in obs.graveyards[1]}
                    assert UPSTART not in {card.code for card in other_view.hand}
                assert not obs.known_opponent_hand_cards
                assert {f"official/c{code}.lua" for code in (spell, SHIELD)} <= \
                    env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail("Spell Shield Type-8 fixture exceeded decision budget")
