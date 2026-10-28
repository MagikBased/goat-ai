"""Spirit Reaper still inflicts direct damage when the opponent cannot discard."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

REAPER = 504700038
DROP_OFF = 55773067
IDOL = 27125110
MIRROR_FORCE = 44095762
TRAPS = (
    12607053, 60082869, 56120475, 35316708, 4178474, 38275183,
    6733059, 30450531, 51452091, 94192409, 76515293, 64697231,
)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
def test_reaper_direct_attack_into_empty_hand_deals_damage_without_discard(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{REAPER}.lua", f"official/c{DROP_OFF}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"{relative} not installed")
    decks = (
        (REAPER, REAPER, REAPER, DROP_OFF, DROP_OFF, DROP_OFF,
         *VANILLA_DECK[6:]),
        (IDOL, IDOL, IDOL, *(trap for trap in TRAPS for _ in range(3)),
         MIRROR_FORCE),
    )
    paths = []
    for player, deck in enumerate(decks):
        assert len(deck) == 40
        path = tmp_path / f"player_{player}.ydk"
        path.write_text("#main\n" + "\n".join(map(str, deck)) + "\n#extra\n!side\n")
        paths.append(str(path))

    with GoatEnvironment(*paths, seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {REAPER, DROP_OFF} <= {card.code for card in obs.hand}
        reaper_summoned = drop_set = idol_summoned = drop_used = False
        attacks = 0
        direct_attack_checked = outcome_checked = False
        agents = (RandomAgent(18), RandomAgent(19))
        for _ in range(3000):
            if env.is_terminal():
                assert direct_attack_checked and outcome_checked and drop_used
                replay = tmp_path / "reaper_empty_hand.json"
                write_trajectory(replay, env.trajectory())
                loaded = read_trajectory(replay)
                assert verify_trajectory(loaded, ExperimentalOcgcoreEngine(root)) \
                    == len(loaded.decisions)
                audit_trajectory_visibility(loaded)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not reaper_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == REAPER), None)
                    reaper_summoned = action is not None
                if reaper_summoned and not drop_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == DROP_OFF), None)
                    drop_set = action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not idol_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == IDOL), None)
                    idol_summoned = action is not None
                if idol_summoned and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"), None)
            if obs.turn in (3, 5) and obs.acting_player == 0:
                if obs.phase == "main1":
                    action = next((a for a in actions if a.kind == "battle_phase"), action)
                if obs.phase in ("battle_start", "battle_step") \
                        and attacks < (1 if obs.turn == 3 else 2):
                    attack = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == REAPER), None)
                    if attack is not None:
                        attacks += 1
                        action = attack
                        if obs.turn == 5:
                            assert drop_used and obs.opponent_hand_count == 0
                            assert not any(card.zone == "monster"
                                           and card.controller == 1 for card in obs.field)
                            assert obs.life_points == (8000, 7700)
                            direct_attack_checked = True
            if obs.turn == 4 and obs.acting_player == 0 and not drop_used:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == DROP_OFF), action)
                drop_used = action is not None and action.kind == "chain"
            if action is None and not outcome_checked:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "main2", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if direct_attack_checked and not outcome_checked \
                    and obs.turn == 5 and obs.phase == "main2":
                assert obs.life_points == (8000, 7400)
                assert obs.opponent_hand_count == 0
                assert len(obs.graveyards[1]) == 2  # Idol and Drop Off's drawn card.
                assert {f"goat/c{REAPER}.lua", f"official/c{DROP_OFF}.lua"} \
                    <= env.engine.probe.loaded_script_sha256.keys()
                outcome_checked = True
    pytest.fail("Spirit Reaper's empty-hand direct attack did not complete")
