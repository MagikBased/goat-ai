"""Balter cannot negate a Spirit Reaper it fails to destroy in battle."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

THUNDER_DRAGON = 504700054
METAMORPHOSIS = 46411259
DARK_BALTER = 80071763
SPIRIT_REAPER = 504700038
ENEMY_CONTROLLER = 98045062


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("target_after_battle", [False, True])
def test_balter_cannot_negate_surviving_spirit_reaper(tmp_path, target_after_battle):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"goat/c{THUNDER_DRAGON}.lua", f"official/c{METAMORPHOSIS}.lua",
               f"official/c{DARK_BALTER}.lua", f"goat/c{SPIRIT_REAPER}.lua",
               f"official/c{ENEMY_CONTROLLER}.lua")
    if any(not (root / "scripts" / name).is_file() for name in scripts):
        pytest.skip("Balter / Reaper scripts not installed")
    own = tmp_path / "balter.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        *([THUNDER_DRAGON] * 3), *([METAMORPHOSIS] * 3),
        ENEMY_CONTROLLER, *VANILLA_DECK[7:])))
                   + f"\n#extra\n{DARK_BALTER}\n!side\n")
    other = tmp_path / "reaper.ydk"
    other.write_text("#main\n" + "\n".join(map(str, (
        SPIRIT_REAPER, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(other), seed=184,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {THUNDER_DRAGON, METAMORPHOSIS, ENEMY_CONTROLLER} <= {
            card.code for card in obs.hand}
        assert SPIRIT_REAPER in {card.code
                                 for card in env.engine.probe.observation(1).hand}
        filler = None
        reaper_set = thunder_summoned = filler_tributed = meta_used = False
        thunder_tributed = balter_chosen = battle = attacked = targeted = False
        controller_used = controller_targeted = survived = False
        for _ in range(115):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and filler is None:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") != THUNDER_DRAGON), None)
                if action is not None:
                    filler = action.parameters["code"]
            if obs.turn == 2 and obs.acting_player == 1 and not reaper_set:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == SPIRIT_REAPER), None)
                reaper_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and reaper_set:
                if not thunder_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == THUNDER_DRAGON), None)
                    thunder_summoned |= action is not None
                if thunder_summoned and not filler_tributed and actions[0].kind == "tribute":
                    action = next((a for a in actions if a.parameters.get("code") == filler),
                                  None)
                    filler_tributed |= action is not None
                if filler_tributed and not meta_used and action is None:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == METAMORPHOSIS), None)
                    meta_used |= action is not None
                if meta_used and not thunder_tributed and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == THUNDER_DRAGON and a.parameters.get("location") == 4),
                                  None)
                    thunder_tributed |= action is not None
                if thunder_tributed and not balter_chosen and action is None \
                        and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == DARK_BALTER), None)
                    balter_chosen |= action is not None
                if balter_chosen and not battle and action is None:
                    action = next((a for a in actions if a.kind == "battle_phase"), None)
                    battle |= action is not None
                if battle and obs.phase == "battle_start" and not attacked:
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == DARK_BALTER), None)
                    if action is not None:
                        assert any(c.controller == 1 and c.zone == "monster"
                                   and c.position == "facedown" and c.code is None
                                   for c in obs.field)
                        attacked = True
                if attacked and not targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("controller")
                                   == 1 and a.parameters.get("location") == 4), None)
                    targeted |= action is not None
                if targeted and obs.phase == "main2" and not survived:
                    assert obs.life_points == (8000, 8000)
                    assert any(c.code == SPIRIT_REAPER and c.controller == 1
                               and c.position == "faceup" and c.orientation == "defense"
                               for c in obs.field)
                    assert SPIRIT_REAPER not in {c.code for c in obs.graveyards[1]}
                    survived = True
                if survived and target_after_battle and not controller_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == ENEMY_CONTROLLER), None)
                    controller_used |= action is not None
            if controller_used and actions[0].kind == "select_option":
                action = actions[0]  # Change battle position; no Tribute cost.
            if controller_used and not controller_targeted \
                    and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == SPIRIT_REAPER and a.parameters.get("controller") == 1),
                              None)
                controller_targeted |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_position", "select_card", "place", "pass", "main2",
                    "end_phase")), actions[0])
            obs = env.step(action)
            resolved = (controller_targeted and ENEMY_CONTROLLER in {
                card.code for card in obs.graveyards[0]})
            if survived and (not target_after_battle or resolved):
                if target_after_battle:
                    assert SPIRIT_REAPER in {c.code for c in obs.graveyards[1]}
                    assert not any(c.code == SPIRIT_REAPER for c in obs.field)
                assert {f"goat/c{SPIRIT_REAPER}.lua",
                        f"official/c{DARK_BALTER}.lua"} <= (
                            env.engine.probe.loaded_script_sha256.keys())
                agents = (RandomAgent(184), RandomAgent(185))
                for _ in range(3000):
                    obs = env.step(agents[obs.acting_player].select_action(
                        obs, env.legal_actions()))
                    if env.is_terminal():
                        path = tmp_path / f"balter_reaper_{target_after_battle}.json"
                        write_trajectory(path, env.trajectory())
                        trajectory = read_trajectory(path)
                        assert verify_trajectory(trajectory,
                                                 ExperimentalOcgcoreEngine(root)) == (
                                                     len(trajectory.decisions))
                        audit_trajectory_visibility(trajectory)
                        return
                pytest.fail("Balter / Reaper duel did not terminate")
        pytest.fail("Balter did not battle Spirit Reaper")
