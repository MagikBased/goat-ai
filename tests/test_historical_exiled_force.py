"""Exiled Force's self-Tribute and hidden target in GOAT mode."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

EXILED_FORCE = 74131780
DEKOICHI = 87621407


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_exiled_force_tributes_before_targeting_a_set_monster(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{EXILED_FORCE}.lua").is_file():
        pytest.skip("Exiled Force script not installed")
    deck = tmp_path / "exiled_force.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        EXILED_FORCE, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        opponent_set = summoned = activated = target_selected = False
        target_code = None
        for _ in range(35):
            actions = env.legal_actions()
            action = None
            if observation.turn == 2 and observation.acting_player == 1 \
                    and not opponent_set:
                action = next((a for a in actions if a.kind == "set_monster"), None)
                if action is not None:
                    opponent_set = True
                    target_code = action.parameters["code"]
            if observation.turn == 3 and observation.acting_player == 0:
                if not summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == EXILED_FORCE), None)
                    summoned = action is not None
                if summoned and not activated and action is None:
                    action = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == EXILED_FORCE), None)
                    if action is not None:
                        assert opponent_set
                        assert any(c.code is None and c.controller == 1
                                   and c.position == "facedown" for c in observation.field)
                        activated = True
            if activated and not target_selected and actions[0].kind == "select_card":
                assert [a.parameters for a in actions] == [
                    {"location": 4, "sequence": 0, "controller": 1}]
                assert EXILED_FORCE in {c.code for c in observation.graveyards[0]}
                assert all(c.code != EXILED_FORCE for c in observation.field)
                assert any(c.code is None and c.controller == 1
                           for c in observation.field)
                action = actions[0]
                target_selected = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if target_selected and target_code in {
                    c.code for c in observation.graveyards[1]}:
                assert not [c for c in observation.field if c.zone == "monster"]
                assert EXILED_FORCE in {c.code for c in observation.graveyards[0]}
                assert observation.life_points == (8000, 8000)
                assert "official/c74131780.lua" in env.engine.probe.loaded_script_sha256
                return
    pytest.fail("Exiled Force did not destroy the set monster")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_exiled_force_cannot_use_effect_without_another_monster(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{EXILED_FORCE}.lua").is_file():
        pytest.skip("Exiled Force script not installed")
    deck = tmp_path / "exiled_alone.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        EXILED_FORCE, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        summoned = False
        for _ in range(28):
            actions = env.legal_actions()
            if summoned and observation.acting_player == 0 \
                    and any(a.kind == "end_phase" for a in actions):
                assert [c.code for c in observation.field if c.zone == "monster"] \
                    == [EXILED_FORCE]
                assert not any(a.parameters.get("code") == EXILED_FORCE
                               and a.kind in ("chain", "activate") for a in actions)
                return
            action = None
            if observation.turn == 3 and observation.acting_player == 0 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == EXILED_FORCE), None)
                summoned = action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
    pytest.fail("did not reach an empty-board Exiled Force main phase")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_exiled_force_target_decision_does_not_reveal_set_monster(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"official/c{EXILED_FORCE}.lua", f"official/c{DEKOICHI}.lua")
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    attacker = tmp_path / "exiled.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        EXILED_FORCE, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    def run(hidden_code):
        defender = tmp_path / f"hidden_{hidden_code}.ydk"
        defender.write_text("#main\n" + "\n".join(map(str, (
            hidden_code, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
        with GoatEnvironment(str(attacker), str(defender), seed=52,
                             engine=ExperimentalOcgcoreEngine(root)) as env:
            obs = env.reset()
            assert EXILED_FORCE in {c.code for c in obs.hand}
            assert hidden_code in {c.code for c in env.engine.probe.observation(1).hand}
            set_done = summoned = activated = targeted = False
            decision = None
            for _ in range(55):
                actions = env.legal_actions()
                action = None
                if obs.turn == 2 and obs.acting_player == 1 and not set_done:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == hidden_code), None)
                    set_done |= action is not None
                if obs.turn == 3 and obs.acting_player == 0:
                    if not summoned:
                        action = next((a for a in actions if a.kind == "normal_summon"
                                       and a.parameters.get("code") == EXILED_FORCE), None)
                        summoned |= action is not None
                    if summoned and not activated and action is None:
                        action = next((a for a in actions if a.kind == "chain"
                                       and a.parameters.get("code") == EXILED_FORCE), None)
                        activated |= action is not None
                if activated and not targeted and actions[0].kind == "select_card":
                    assert obs.viewer == obs.acting_player == 0
                    assert EXILED_FORCE in {c.code for c in obs.graveyards[0]}
                    assert obs.known_opponent_field_cards == ()
                    assert not obs.private_reveals
                    assert [a.parameters for a in actions] == [
                        {"location": 4, "sequence": 0, "controller": 1}]
                    decision = (obs, actions)
                    action = actions[0]
                    targeted = True
                if action is None:
                    action = next((a for a in actions if a.kind in (
                        "place", "pass", "end_phase")), actions[0])
                obs = env.step(action)
                if targeted and hidden_code in {c.code for c in obs.graveyards[1]}:
                    assert all((set_done, summoned, activated, targeted))
                    assert f"official/c{EXILED_FORCE}.lua" in \
                        env.engine.probe.loaded_script_sha256
                    return decision
        pytest.fail(f"Exiled target line stalled for {hidden_code}")

    flip_decision = run(DEKOICHI)
    vanilla_decision = run(VANILLA_DECK[0])
    assert flip_decision is not None and flip_decision == vanilla_decision
