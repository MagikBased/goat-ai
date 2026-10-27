"""A battle-destroyed Sangan searches unless Dark Balter negates it."""

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
SANGAN = 504700178
MYSTICAL_ELF = 15025844


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("use_balter", [False, True])
def test_balter_battle_destruction_suppresses_sangan_search(tmp_path, use_balter):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{THUNDER_DRAGON}.lua",
                     f"official/c{METAMORPHOSIS}.lua",
                     f"official/c{DARK_BALTER}.lua", f"goat/c{SANGAN}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    own = tmp_path / "balter.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        *([THUNDER_DRAGON] * 3), *([METAMORPHOSIS] * 3),
        *VANILLA_DECK[6:]))) + f"\n#extra\n{DARK_BALTER}\n!side\n")
    other = tmp_path / "sangan.ydk"
    other.write_text("#main\n" + "\n".join(map(str, (
        SANGAN, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(other), seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {THUNDER_DRAGON, METAMORPHOSIS} <= {c.code for c in obs.hand}
        assert SANGAN in {c.code for c in env.engine.probe.observation(1).hand}
        filler = None
        sangan_set = thunder_summoned = filler_tributed = False
        meta_used = thunder_tributed = balter_chosen = False
        battle = attacked = target_selected = search_selected = False
        deck_before = hand_before = None
        for _ in range(110):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and filler is None:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") != THUNDER_DRAGON), None)
                if action is not None:
                    filler = action.parameters["code"]
            if obs.turn == 2 and obs.acting_player == 1 and not sangan_set:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == SANGAN), None)
                sangan_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and sangan_set:
                if not thunder_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == THUNDER_DRAGON), None)
                    thunder_summoned |= action is not None
                if thunder_summoned and not filler_tributed and actions[0].kind == "tribute":
                    action = next((a for a in actions if a.parameters.get("code") == filler),
                                  None)
                    filler_tributed |= action is not None
                if use_balter and filler_tributed and not meta_used and action is None:
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
                if filler_tributed and (not use_balter or balter_chosen) \
                        and not battle and action is None:
                    action = next((a for a in actions if a.kind == "battle_phase"), None)
                    battle |= action is not None
                if battle and obs.phase == "battle_start" and not attacked:
                    attacker = DARK_BALTER if use_balter else THUNDER_DRAGON
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == attacker), None)
                    if action is not None:
                        assert any(c.controller == 1 and c.zone == "monster"
                                   and c.position == "facedown" and c.code is None
                                   for c in obs.field)
                        defender_view = env.engine.probe.observation(1)
                        deck_before = defender_view.deck_counts[1]
                        hand_before = len(defender_view.hand)
                        attacked = True
                if attacked and not target_selected and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("controller")
                                   == 1 and a.parameters.get("location") == 4), None)
                    target_selected |= action is not None
            if target_selected and obs.acting_player == 1 \
                    and actions[0].kind == "select_card" and not search_selected:
                assert not use_balter, "Balter let battle-destroyed Sangan search"
                action = next((a for a in actions if a.parameters.get("code")
                               == MYSTICAL_ELF and a.parameters.get("location") == 1), None)
                search_selected = action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_position", "select_card", "place", "pass", "main2",
                    "end_phase")), actions[0])
            obs = env.step(action)
            if target_selected and SANGAN in {c.code for c in obs.graveyards[1]} \
                    and obs.turn == 3 and obs.phase == "main2":
                assert deck_before is not None and hand_before is not None
                assert search_selected == (not use_balter)
                defender_view = env.engine.probe.observation(1)
                assert defender_view.deck_counts[1] == deck_before - int(not use_balter)
                assert len(defender_view.hand) == hand_before + int(not use_balter)
                if search_selected:
                    assert MYSTICAL_ELF in {c.code for c in defender_view.hand}
                    assert [[c.code for c in reveal.cards]
                            for reveal in env.engine.probe.observation(0).private_reveals] \
                        == [[MYSTICAL_ELF]]
                else:
                    assert not env.engine.probe.observation(0).private_reveals
                loaded = env.engine.probe.loaded_script_sha256
                assert f"goat/c{SANGAN}.lua" in loaded
                assert f"goat/c{THUNDER_DRAGON}.lua" in loaded
                if use_balter:
                    assert f"official/c{DARK_BALTER}.lua" in loaded
                agents = (RandomAgent(150), RandomAgent(151))
                for _ in range(3000):
                    obs = env.step(agents[obs.acting_player].select_action(
                        obs, env.legal_actions()))
                    if env.is_terminal():
                        path = tmp_path / f"balter_sangan_{use_balter}.json"
                        write_trajectory(path, env.trajectory())
                        trajectory = read_trajectory(path)
                        assert verify_trajectory(trajectory,
                                                 ExperimentalOcgcoreEngine(root)) == (
                                                     len(trajectory.decisions))
                        audit_trajectory_visibility(trajectory)
                        return
                pytest.fail("Balter / Sangan duel did not terminate")
        pytest.fail("Sangan was not battle-destroyed")
