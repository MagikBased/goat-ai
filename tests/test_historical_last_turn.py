"""Last Turn can replace an already announced attack with its forced battle."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import verify_trajectory

WALL = 17078030
LAST_TURN = 28566710
MYSTICAL_SPACE_TYPHOON = 5318639
SEVEN_COLORED_FISH = 23771716
ARCHFIEND_SOLDIER = 49881766


def _find(actions, kind, code=None):
    return next((action for action in actions if action.kind == kind
                 and (code is None or action.parameters.get("code") == code)), None)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_last_turn_forced_battle_replaces_attack_and_awards_winner(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (WALL, LAST_TURN, MYSTICAL_SPACE_TYPHOON):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    deck = tmp_path / "last_turn.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        WALL, LAST_TURN, MYSTICAL_SPACE_TYPHOON, VANILLA_DECK[2],
        *VANILLA_DECK[4:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {WALL, LAST_TURN, MYSTICAL_SPACE_TYPHOON, SEVEN_COLORED_FISH} <= {
            card.code for card in obs.hand}
        done = set()
        for _ in range(150):
            if env.is_terminal():
                assert {"summoned", "wall_set", "last_set", "mst_set", "wall",
                        "paid", "mst", "enemy_summoned", "enemy_attack", "last"} <= done
                assert env.result() == 1
                assert obs.life_points == (1000, 8000)
                assert [(card.code, card.controller, card.zone) for card in obs.field] \
                    == [(ARCHFIEND_SOLDIER, 1, "monster")]
                trajectory = env.trajectory()
                assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) == len(
                    trajectory.decisions)
                assert audit_trajectory_visibility(trajectory)["decisions"] == len(
                    trajectory.decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                for kind, code, tag in (
                    ("normal_summon", SEVEN_COLORED_FISH, "summoned"),
                    ("set_spell_trap", WALL, "wall_set"),
                    ("set_spell_trap", LAST_TURN, "last_set"),
                    ("set_spell_trap", MYSTICAL_SPACE_TYPHOON, "mst_set"),
                ):
                    if tag not in done:
                        action = _find(actions, kind, code)
                        if action is not None:
                            done.add(tag)
                            break
            if obs.turn == 2 and obs.acting_player == 0:
                if "wall" not in done:
                    action = _find(actions, "chain", WALL)
                    if action is not None:
                        done.add("wall")
                elif "paid" in done and "mst" not in done:
                    action = _find(actions, "chain", MYSTICAL_SPACE_TYPHOON)
                    if action is not None:
                        done.add("mst")
                if "mst" in done and obs.phase == "battle_step" and "last" not in done:
                    option = _find(actions, "chain", LAST_TURN)
                    if option is not None:
                        assert "enemy_attack" in done
                        action = option
                        done.add("last")
            if obs.turn == 2 and obs.acting_player == 1:
                if "enemy_summoned" not in done:
                    action = _find(actions, "normal_summon")
                    if action is not None:
                        done.add("enemy_summoned")
                if "enemy_summoned" in done and "enemy_attack" not in done \
                        and action is None:
                    action = _find(actions, "attack")
                    if action is not None:
                        done.add("enemy_attack")
                    else:
                        action = _find(actions, "battle_phase")
            if actions[0].kind == "announce_number" and "paid" not in done:
                action = next((candidate for candidate in actions
                               if candidate.parameters.get("number") == 7000), None)
                if action is not None:
                    done.add("paid")
            if actions[0].kind == "select_card":
                codes = {candidate.parameters.get("code") for candidate in actions}
                target = (WALL if WALL in codes and "mst" in done and "last" not in done
                          else ARCHFIEND_SOLDIER if "last" in done and obs.acting_player == 1
                          else SEVEN_COLORED_FISH)
                action = _find(actions, "select_card", target)
                assert action is not None
            if action is None:
                action = next((candidate for candidate in actions if candidate.kind
                               in ("pass", "place", "end_phase", "cancel")), actions[0])
            obs = env.step(action)
    pytest.fail("Last Turn did not reach its End Phase outcome")
