"""A GOAT Relinquished Ritual Summon exercises native Level-sum choices."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

BLACK_ILLUSION_RITUAL = 41426869
RELINQUISHED = 504700106  # historical GOAT variant, alias of 64631466
MATERIAL = VANILLA_DECK[0]


def _deck(path: Path, cards) -> str:
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("material_on_field", (False, True))
def test_relinquished_ritual_uses_visible_hand_or_field_material(
    tmp_path, material_on_field,
):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (root / f"scripts/official/c{BLACK_ILLUSION_RITUAL}.lua",
               root / f"scripts/goat/c{RELINQUISHED}.lua",
               root / "scripts/proc_ritual.lua")
    if any(not path.is_file() for path in scripts):
        pytest.skip("required historical Ritual scripts not installed")
    own_cards = list(VANILLA_DECK)
    own_cards[1] = BLACK_ILLUSION_RITUAL
    own_cards[2] = RELINQUISHED
    own = _deck(tmp_path / "ritual.ydk", own_cards)
    other = _deck(tmp_path / "opponent.ydk", VANILLA_DECK)

    with GoatEnvironment(own, other, seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert {BLACK_ILLUSION_RITUAL, RELINQUISHED, MATERIAL} <= {
            card.code for card in observation.hand}
        normal_summoned = not material_on_field
        ritual_activated = sum_selected = False
        for _ in range(45):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0:
                if not normal_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == MATERIAL), None)
                    normal_summoned |= action is not None
                elif not ritual_activated:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == BLACK_ILLUSION_RITUAL),
                                  None)
                    ritual_activated |= action is not None
                elif actions[0].kind == "select_card":
                    ritual_monster = next((a for a in actions
                                           if a.parameters.get("code") == RELINQUISHED), None)
                    if ritual_monster is not None:
                        action = ritual_monster
                    else:
                        assert env.engine.probe._pending_message[0] == 23  # MSG_SELECT_SUM
                        assert env.engine.probe.decode_pending().sum_selection is None
                        assert env.engine.probe.observation(1).known_opponent_hand_cards == ()
                        action = next((a for a in actions if a.parameters.get("code") == MATERIAL
                                       and a.parameters.get("location") ==
                                       (4 if material_on_field else 2)), None)
                        assert action is not None
                        sum_selected = True
            if action is None:
                action = next((a for a in actions if a.kind == "pass"), actions[0])
            observation = env.step(action)
            if any(card.code == RELINQUISHED and card.zone == "monster"
                   for card in observation.field):
                break

        assert ritual_activated and sum_selected
        assert any(card.code == RELINQUISHED and card.position == "faceup"
                   for card in observation.field)
        assert MATERIAL in {card.code for card in observation.graveyards[0]}
        assert BLACK_ILLUSION_RITUAL in {card.code for card in observation.graveyards[0]}
        assert env.engine.probe.observation(1).field == observation.field
        assert f"goat/c{RELINQUISHED}.lua" in env.engine.probe.loaded_script_sha256

        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(5000):
            if env.is_terminal():
                break
            actions = env.legal_actions()
            observation = env.step(
                agents[observation.acting_player].select_action(observation, actions))
        assert env.is_terminal(), "Ritual duel exceeded 5000 decisions"
        trajectory = env.trajectory()
        saved = tmp_path / f"relinquished_{material_on_field}.json"
        write_trajectory(saved, trajectory)
        assert verify_trajectory(read_trajectory(saved),
                                 ExperimentalOcgcoreEngine(root)) == len(
                                     trajectory.decisions)
        assert audit_trajectory_visibility(trajectory)["decisions"] == len(
            trajectory.decisions)
