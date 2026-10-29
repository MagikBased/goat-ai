"""Solemn Judgment cannot negate Thunder Dragon's activated monster effect."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

THUNDER_DRAGON = 504700054  # GOAT variant
SOLEMN_JUDGMENT = 41420027


def _deck(path: Path, code: int) -> str:
    path.write_text("#main\n" + "\n".join(map(str, (
        *([code] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
def test_set_solemn_cannot_chain_to_thunder_dragon_hand_effect(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for script in (f"goat/c{THUNDER_DRAGON}.lua",
                   f"official/c{SOLEMN_JUDGMENT}.lua"):
        if not (root / "scripts" / script).is_file():
            pytest.skip(f"script {script} not installed")
    thunder_deck = _deck(tmp_path / "thunder.ydk", THUNDER_DRAGON)
    solemn_deck = _deck(tmp_path / "solemn.ydk", SOLEMN_JUDGMENT)
    with GoatEnvironment(thunder_deck, solemn_deck, seed=11,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert THUNDER_DRAGON in {card.code for card in observation.hand}
        assert SOLEMN_JUDGMENT in {
            card.code for card in env.engine.probe.observation(1).hand}
        set_solemn = activated = checked_response = searched = resolved = False
        agents = (RandomAgent(11), RandomAgent(12))
        for _ in range(3000):
            if env.is_terminal():
                assert set_solemn and activated and checked_response
                assert searched and resolved
                trajectory = env.trajectory()
                path = tmp_path / "solemn_thunder_effect.json"
                write_trajectory(path, trajectory)
                saved = read_trajectory(path)
                assert verify_trajectory(saved, ExperimentalOcgcoreEngine(root)) == len(
                    trajectory.decisions)
                audit_trajectory_visibility(saved)
                return
            actions = env.legal_actions()
            action = None
            if observation.turn == 2 and observation.acting_player == 1 \
                    and not set_solemn:
                action = next((choice for choice in actions
                               if choice.kind == "set_spell_trap"
                               and choice.parameters.get("code") == SOLEMN_JUDGMENT), None)
                set_solemn |= action is not None
            if observation.turn == 3 and observation.acting_player == 0 \
                    and not activated:
                action = next((choice for choice in actions
                               if choice.kind == "activate"
                               and choice.parameters.get("code") == THUNDER_DRAGON), None)
                activated |= action is not None
            if (activated and observation.chain
                    and observation.chain[-1].card_code == THUNDER_DRAGON
                    and observation.acting_player == 1 and not checked_response):
                assert set_solemn
                assert [(choice.kind, choice.parameters.get("code"))
                        for choice in actions] == [("pass", None)]
                assert observation.life_points == (8000, 8000)
                assert any(card.controller == 1 and card.zone == "spell_trap"
                           and card.position == "facedown"
                           and card.code == SOLEMN_JUDGMENT
                           for card in observation.field)
                hidden_from_opponent = env.engine.probe.observation(0)
                assert any(card.controller == 1 and card.zone == "spell_trap"
                           and card.position == "facedown" and card.code is None
                           for card in hidden_from_opponent.field)
                checked_response = True
            if checked_response and not searched and actions[0].kind == "cancel":
                action = next((choice for choice in actions
                               if choice.kind == "select_cards"
                               and len(choice.parameters.get("cards", ())) == 2), None)
                assert action is not None
                searched = True
            if (searched and not observation.chain and not resolved
                    and THUNDER_DRAGON in {card.code for card in observation.graveyards[0]}):
                assert sum(card.code == THUNDER_DRAGON
                           for card in observation.hand) == 2
                assert observation.life_points == (8000, 8000)
                own_trap = env.engine.probe.observation(1)
                assert any(card.code == SOLEMN_JUDGMENT
                           and card.position == "facedown" for card in own_trap.field)
                resolved = True
            if action is None:
                action = (agents[observation.acting_player].select_action(
                    observation, actions) if resolved else
                    next((choice for choice in actions
                          if choice.kind in ("end_phase", "pass", "place")), actions[0]))
            observation = env.step(action)
    pytest.fail("Thunder Dragon / Solemn Judgment duel did not terminate")
