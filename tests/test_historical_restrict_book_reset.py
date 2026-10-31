"""Book of Moon resets a previously Summoned Restrict's equip effect."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SCAPEGOAT = 504700123
METAMORPHOSIS = 46411259
RESTRICT = 504700102
BOOK = 14087893
SHEEP_CODES = {73915052, 73915053, 73915054, 73915055}


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("prior_action", ["none", "manual_change", "attack",
                                         "summoned_this_turn"])
def test_book_reset_respects_prior_actions(tmp_path, prior_action):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{SCAPEGOAT}.lua", f"official/c{METAMORPHOSIS}.lua",
               f"goat/c{RESTRICT}.lua", f"official/c{BOOK}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    attacker = tmp_path / "restrict_book.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        *([SCAPEGOAT] * 3), *([METAMORPHOSIS] * 3), *([BOOK] * 3),
        *VANILLA_DECK[9:]))) + f"\n#extra\n{RESTRICT}\n!side\n")
    defender = tmp_path / "sheep.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        *([SCAPEGOAT] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=70,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        target_turn = 3 if prior_action == "summoned_this_turn" else 5
        obs = env.reset()
        assert {SCAPEGOAT, METAMORPHOSIS, BOOK} <= {card.code for card in obs.hand}
        own_goat = other_goat = meta = own_token = fusion = False
        first_effect = first_target = first_equipped = book = book_target = False
        manually_changed = battle_entered = attack_declared = attack_targeted = False
        locked = flipped = second_effect = second_target = False
        first_slot = second_slot = None

        def finish_and_verify(observation):
            agents = (RandomAgent(70), RandomAgent(71))
            for _ in range(3000):
                if env.is_terminal():
                    break
                observation = env.step(agents[observation.acting_player].select_action(
                    observation, env.legal_actions()))
            else:
                pytest.fail("Restrict / Book continuation exceeded 3000 decisions")
            trajectory = env.trajectory()
            assert trajectory.schema_version == 29
            path = tmp_path / f"restrict_book_reset_{prior_action}.json"
            write_trajectory(path, trajectory)
            assert verify_trajectory(read_trajectory(path),
                                     ExperimentalOcgcoreEngine(root)) == len(
                                         trajectory.decisions)

        for _ in range(160):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not own_goat:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                own_goat |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not other_goat:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                other_goat |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not meta:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == METAMORPHOSIS), action)
                meta |= action is not None and action.kind == "activate"
            if meta and not own_token and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               in SHEEP_CODES and a.parameters.get("controller") == 0), None)
                own_token |= action is not None
            if own_token and not fusion and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == RESTRICT),
                              None)
                fusion |= action is not None
            if obs.turn == target_turn and obs.acting_player == 0 and fusion:
                if not first_effect:
                    action = next((a for a in actions if a.kind in ("activate", "chain")
                                   and a.parameters.get("code") == RESTRICT), None)
                    first_effect |= action is not None
                if first_effect and not first_target and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("controller") == 1
                                   and a.parameters.get("code") in SHEEP_CODES), None)
                    if action is not None:
                        first_slot = action.parameters["sequence"]
                        first_target = True
                if first_target and not obs.chain and not first_equipped:
                    restrict = next(c for c in obs.field if c.code == RESTRICT)
                    equipped = [c for c in obs.field if c.zone == "spell_trap"
                                and c.controller == 0 and c.equipped_to == (
                                    0, restrict.sequence)]
                    if equipped:
                        first_equipped = True
                        assert len(equipped) == 1
                        assert not any(a.kind in ("activate", "chain")
                                       and a.parameters.get("code") == RESTRICT
                                       for a in actions)
                if first_equipped and prior_action == "manual_change" \
                        and not manually_changed and action is None:
                    action = next((a for a in actions if a.kind == "change_position"
                                   and a.parameters.get("code") == RESTRICT), None)
                    manually_changed |= action is not None
                if first_equipped and prior_action == "attack" and not book \
                        and action is None:
                    if obs.phase == "main1" and not battle_entered:
                        action = next((a for a in actions if a.kind == "battle_phase"), None)
                        battle_entered |= action is not None
                    elif obs.phase == "battle_start" and not attack_declared:
                        action = next((a for a in actions if a.kind == "attack"
                                       and a.parameters.get("code") == RESTRICT), None)
                        attack_declared |= action is not None
                    elif attack_declared and not attack_targeted \
                            and actions[0].kind == "select_card":
                        action = next((a for a in actions if a.parameters.get("controller")
                                       == 1 and a.parameters.get("code") in SHEEP_CODES
                                       and a.parameters.get("sequence") != first_slot), None)
                        attack_targeted |= action is not None
                    elif attack_targeted and obs.phase in ("battle_start", "battle_step"):
                        action = next((a for a in actions if a.kind == "main2"), None)
                ready_for_book = (prior_action in ("none", "summoned_this_turn")
                                  or prior_action == "manual_change" and manually_changed
                                  or prior_action == "attack" and attack_targeted
                                  and obs.phase == "main2")
                if first_equipped and ready_for_book \
                        and not book and action is None:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == BOOK), None)
                    book |= action is not None
                if book and not book_target and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == RESTRICT
                                   and a.parameters.get("controller") == 0), None)
                    book_target |= action is not None
                if book_target and not obs.chain and not flipped and not locked:
                    restrict = next(c for c in obs.field if c.code == RESTRICT)
                    assert restrict.position == "facedown"
                    assert BOOK in {c.code for c in obs.graveyards[0]}
                    assert not any(c.zone == "spell_trap" and c.equipped_to == (
                        0, restrict.sequence) for c in obs.field)
                    assert sum(c.code in SHEEP_CODES for c in obs.field
                               if c.controller == 1 and c.zone == "monster") == 3
                    flip_option = next((a for a in actions if a.kind == "flip_summon"
                                        and a.parameters.get("code") == RESTRICT), None)
                    if prior_action != "none":
                        if prior_action == "manual_change":
                            assert manually_changed
                        elif prior_action == "attack":
                            assert attack_declared and attack_targeted
                        else:
                            assert prior_action == "summoned_this_turn" and meta and fusion
                        assert flip_option is None
                        locked = True
                    else:
                        action = flip_option
                        flipped |= action is not None
                if flipped and not second_effect and action is None:
                    action = next((a for a in actions if a.kind in ("activate", "chain")
                                   and a.parameters.get("code") == RESTRICT), None)
                    second_effect |= action is not None
                if second_effect and not second_target and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("controller") == 1
                                   and a.parameters.get("code") in SHEEP_CODES
                                   and a.parameters.get("sequence") != first_slot), None)
                    if action is not None:
                        second_slot = action.parameters["sequence"]
                        second_target = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if locked and obs.turn == target_turn and not obs.chain:
                own = env.engine.probe.observation(0)
                restrict = next(c for c in own.field if c.code == RESTRICT)
                assert restrict.position == "facedown"
                assert sum(c.code in SHEEP_CODES for c in own.field
                           if c.controller == 1 and c.zone == "monster") == 3
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                finish_and_verify(obs)
                return
            if second_target and not obs.chain and obs.turn == target_turn:
                assert first_equipped and book and book_target and flipped
                assert first_slot != second_slot
                restrict = next(c for c in obs.field if c.code == RESTRICT)
                assert restrict.position == "faceup"
                assert restrict.faceup_turns == 0  # Book reset, then Flip Summon this turn.
                assert any(c.zone == "spell_trap" and c.controller == 0
                           and c.equipped_to == (0, restrict.sequence) for c in obs.field)
                assert sum(c.code in SHEEP_CODES for c in obs.field
                           if c.controller == 1 and c.zone == "monster") == 2
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                finish_and_verify(obs)
                return
    pytest.fail(f"Restrict reset stalled: turn={obs.turn} phase={obs.phase} "
                f"goats={own_goat}/{other_goat} meta={meta}/{own_token}/{fusion} "
                f"first={first_effect}/{first_target}/{first_equipped} "
                f"book={book}/{book_target} change={manually_changed} "
                f"attack={battle_entered}/{attack_declared}/{attack_targeted} "
                f"lock={locked} flip={flipped} "
                f"second={second_effect}/{second_target}")
