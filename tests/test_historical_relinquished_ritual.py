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
BOOK_OF_MOON = 14087893
RAIGEKI_BREAK = 4178474
DEKOICHI = 87621407


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


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("response", ("none", "book", "raigeki_break"))
def test_removal_chained_to_relinquished_equip_preserves_set_target(tmp_path, response):
    """GOAT Rule 13 keeps the target when the equipping monster is removed."""
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (root / f"scripts/official/c{BLACK_ILLUSION_RITUAL}.lua",
               root / f"scripts/goat/c{RELINQUISHED}.lua",
               root / f"scripts/official/c{BOOK_OF_MOON}.lua",
               root / f"scripts/official/c{RAIGEKI_BREAK}.lua",
               root / f"scripts/official/c{DEKOICHI}.lua")
    if any(not path.is_file() for path in scripts):
        pytest.skip("required historical scripts not installed")
    owner_cards = list(VANILLA_DECK)
    owner_cards[1:3] = [BLACK_ILLUSION_RITUAL, RELINQUISHED]
    defender_cards = list(VANILLA_DECK)
    defender_cards[0] = DEKOICHI
    response_card = BOOK_OF_MOON if response != "raigeki_break" else RAIGEKI_BREAK
    defender_cards[4] = response_card
    owner = _deck(tmp_path / "ritual.ydk", owner_cards)
    defender = _deck(tmp_path / "defender.ydk", defender_cards)

    with GoatEnvironment(owner, defender, seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {MATERIAL, BLACK_ILLUSION_RITUAL, RELINQUISHED} <= {
            card.code for card in obs.hand}
        assert {DEKOICHI, response_card} <= {
            card.code for card in env.engine.probe.observation(1).hand}
        ritual = material = set_monster = set_response = effect = target = responded = False
        target_slot = None
        for _ in range(120):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not ritual:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == BLACK_ILLUSION_RITUAL), None)
                    ritual |= action is not None
                elif actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == RELINQUISHED), None)
                    if action is None:
                        action = next((a for a in actions if a.parameters.get("code")
                                       == MATERIAL), None)
                        material |= action is not None
            elif obs.turn == 2 and obs.acting_player == 1:
                if not set_monster:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == DEKOICHI), None)
                    set_monster |= action is not None
                elif not set_response:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == response_card), None)
                    set_response |= action is not None
            elif obs.turn == 3:
                if obs.acting_player == 0 and not effect:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == RELINQUISHED), None)
                    effect |= action is not None
                elif obs.acting_player == 0 and effect and not target \
                        and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("controller") == 1
                                   and a.parameters.get("location") == 4), None)
                    assert action is not None and "code" not in action.parameters
                    target_slot = action.parameters["sequence"]
                    target = True
                elif obs.acting_player == 1 and target and not responded \
                        and response != "none":
                    action = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == response_card), None)
                    responded |= action is not None
                elif obs.acting_player == 1 and responded and actions[0].kind == "select_card":
                    action = next((a for a in actions if response == "raigeki_break"
                                   and a.parameters.get("controller") == 1
                                   and a.parameters.get("location") == 2), None)
                    if action is None:
                        action = next((a for a in actions
                                       if a.parameters.get("controller") == 0
                                       and a.parameters.get("location") == 4), None)
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "pass", "end_phase", "select_card", "place")), actions[0])
            obs = env.step(action)
            if (target and obs.turn == 3 and obs.phase == "main1"
                    and obs.acting_player == 0 and not obs.chain):
                break
        assert ritual and material and set_monster and set_response and effect and target
        assert responded == (response != "none")
        assert target_slot is not None
        own = env.engine.probe.observation(0)
        other = env.engine.probe.observation(1)
        if response != "none":
            assert any(card.controller == 1 and card.zone == "monster"
                       and card.sequence == target_slot and card.code is None
                       for card in own.field)
            assert not any(card.code == DEKOICHI and card.zone == "spell_trap"
                           for card in own.field)
            assert response_card in {card.code for card in own.graveyards[1]}
            if response == "book":
                assert any(card.code == RELINQUISHED and card.position == "facedown"
                           for card in own.field)
            else:
                assert RELINQUISHED in {card.code for card in own.graveyards[0]}
        else:
            assert not any(card.controller == 1 and card.zone == "monster"
                           and card.sequence == target_slot for card in own.field)
            assert any(card.code == DEKOICHI and card.zone == "spell_trap"
                       and card.controller == 0 for card in own.field)
            assert any(card.code is None and card.zone == "spell_trap"
                       and card.controller == 0 and card.position == "facedown"
                       for card in other.field)
            assert any(card.code == RELINQUISHED and card.attack == 0
                       for card in own.field)
        assert other.known_opponent_hand_cards == ()

        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(5000):
            if env.is_terminal():
                break
            obs = env.step(agents[obs.acting_player].select_action(obs, env.legal_actions()))
        assert env.is_terminal(), "Relinquished equip duel exceeded 5000 decisions"
        trajectory = env.trajectory()
        path = tmp_path / f"relinquished_equip_{response}.json"
        write_trajectory(path, trajectory)
        assert verify_trajectory(read_trajectory(path),
                                 ExperimentalOcgcoreEngine(root)) == len(
                                     trajectory.decisions)
        assert audit_trajectory_visibility(trajectory)["decisions"] == len(
            trajectory.decisions)
