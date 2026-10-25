"""Dekoichi draws after D.D. Warrior Lady banishes both battling monsters."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

WARRIOR_LADY = 7572887
DEKOICHI = 87621407


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("banish", [False, True])
def test_warrior_lady_banish_does_not_cancel_dekoichi_flip_draw(tmp_path, banish):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{WARRIOR_LADY}.lua", f"official/c{DEKOICHI}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card scripts not installed")
    attacker = tmp_path / "warrior_lady.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        WARRIOR_LADY, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    defender = tmp_path / "dekoichi.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        DEKOICHI, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert WARRIOR_LADY in {c.code for c in obs.hand}
        assert DEKOICHI in {c.code for c in env.engine.probe.observation(1).hand}
        summoned = set_done = attacked = choice_seen = False
        defender_hand_before = defender_deck_before = None
        for _ in range(85):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == WARRIOR_LADY), None)
                summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not set_done:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == DEKOICHI), None)
                set_done |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and set_done and not attacked:
                action = next((a for a in actions if a.kind in ("battle_phase", "attack")),
                              None)
                if action is not None and action.kind == "attack":
                    target = next(c for c in obs.field if c.zone == "monster"
                                  and c.controller == 1)
                    assert target.position == "facedown" and target.code is None
                    attacked = True
                    defender_view = env.engine.probe.observation(1)
                    defender_hand_before = len(defender_view.hand)
                    defender_deck_before = obs.deck_counts[1]
            if attacked and obs.acting_player == 0 and not choice_seen:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == WARRIOR_LADY), None)
                if option is not None:
                    assert obs.phase == "damage_step"
                    assert [(link.card_code, link.controller) for link in obs.chain] == [
                        (DEKOICHI, 1)]
                    assert any(c.controller == 1 and c.code == DEKOICHI
                               and c.position == "faceup" for c in obs.field)
                    action = option if banish else next(a for a in actions
                                                       if a.kind == "pass")
                    choice_seen = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "main2", "end_phase")), actions[0])
            obs = env.step(action)
            if choice_seen and obs.turn == 3 and obs.phase == "main2":
                defender_view = env.engine.probe.observation(1)
                assert obs.deck_counts[1] == defender_deck_before - 1
                assert len(defender_view.hand) == defender_hand_before + 1
                assert obs.opponent_hand_count == len(defender_view.hand)
                assert obs.life_points == (8000, 8000)
                assert (WARRIOR_LADY in {c.code for c in obs.banished[0]}) == banish
                assert (DEKOICHI in {c.code for c in obs.banished[1]}) == banish
                assert (DEKOICHI in {c.code for c in obs.graveyards[1]}) != banish
                assert not any(c.code == DEKOICHI for c in obs.field)
                assert (any(c.code == WARRIOR_LADY for c in obs.field)) != banish
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                agents = (RandomAgent(52), RandomAgent(53))
                for _ in range(3000):
                    if env.is_terminal():
                        break
                    obs = env.step(agents[obs.acting_player].select_action(
                        obs, env.legal_actions()))
                assert env.is_terminal()
                path = tmp_path / f"warrior_lady_dekoichi_{banish}.json"
                write_trajectory(path, env.trajectory())
                trajectory = read_trajectory(path)
                assert audit_trajectory_visibility(trajectory)["decisions"] == len(
                    trajectory.decisions)
                assert verify_trajectory(trajectory,
                                         ExperimentalOcgcoreEngine(root)) == len(
                                             env.trajectory().decisions)
                return
    pytest.fail(f"Warrior Lady / Dekoichi line stalled: turn={obs.turn} "
                f"phase={obs.phase} setup={summoned}/{set_done}/{attacked} "
                f"choice={choice_seen}")
