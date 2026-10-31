"""Spell Shield Type-8 can negate a targeted Snatch Steal activation."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import verify_trajectory

SNATCH = 45986603
SHIELD = 38275183
UPSTART = 70368879


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("use_shield", [False, True])
def test_spell_shield_free_mode_against_snatch_steal(tmp_path, use_shield):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (SNATCH, SHIELD, UPSTART):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"official script for {code} not installed")
    decks = []
    for name, cards in (
        ("snatch", (SNATCH, *VANILLA_DECK[1:])),
        ("shield", (SHIELD, *VANILLA_DECK[1:4], UPSTART, *VANILLA_DECK[5:])),
    ):
        path = tmp_path / f"{name}.ydk"
        path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
        decks.append(str(path))

    with GoatEnvironment(*decks, seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert SNATCH in {card.code for card in obs.hand}
        assert {SHIELD, UPSTART} <= {
            card.code for card in env.engine.probe.observation(1).hand}
        summoned = shield_set = snatch_used = target_chosen = response_seen = False
        shield_used = checked = False
        monster_code = None
        agents = (RandomAgent(4598), RandomAgent(3827))
        for _ in range(5000):
            if env.is_terminal():
                break
            actions = env.legal_actions()
            action = None
            if not checked and obs.turn == 2 and obs.acting_player == 1:
                if not summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        summoned = True
                        monster_code = action.parameters["code"]
                if action is None and summoned and not shield_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == SHIELD), None)
                    shield_set |= action is not None
            if not checked and shield_set and obs.turn == 3 \
                    and obs.acting_player == 0 and not snatch_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SNATCH), None)
                snatch_used |= action is not None
            if snatch_used and not target_chosen and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("code") == monster_code), None)
                target_chosen |= action is not None
            if target_chosen and not response_seen and obs.acting_player == 1:
                options = [a for a in actions if a.kind == "chain"
                           and a.parameters.get("code") == SHIELD]
                if options:
                    assert [a.parameters.get("effect_option") for a in options] == [0, 1]
                    assert not obs.known_opponent_hand_cards
                    action = options[0] if use_shield else next(
                        a for a in actions if a.kind == "pass")
                    response_seen = True
                    shield_used = use_shield
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if response_seen and not checked and obs.turn == 3 \
                    and obs.phase == "main1" and not obs.chain:
                own = env.engine.probe.observation(1)
                monster = next(card for card in own.field if card.code == monster_code)
                assert monster.controller == (1 if shield_used else 0)
                assert UPSTART in {card.code for card in own.hand}
                assert (SHIELD in {card.code for card in own.graveyards[1]}) == shield_used
                assert (SNATCH in {card.code for card in obs.field}) == (not shield_used)
                assert (SNATCH in {card.code for card in obs.graveyards[0]}) == shield_used
                checked = True
        assert checked and env.is_terminal(), (summoned, shield_set, snatch_used,
                                               target_chosen, response_seen, obs.turn)
        assert {f"official/c{code}.lua" for code in (SNATCH, SHIELD)} <= (
            env.engine.probe.loaded_script_sha256.keys())
        trajectory = env.trajectory()
        assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) == len(
            trajectory.decisions)
        assert audit_trajectory_visibility(trajectory)["decisions"] == len(
            trajectory.decisions)
