"""2005 Hand of Nephthys token cost and Sacred Phoenix revival."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

HAND = 504700175
PHOENIX = 504700099
SCAPEGOAT = 504700123
TORRENTIAL = 53582587
BOOK = 14087893
SHEEP = {73915052, 73915053, 73915054, 73915055}


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_hand_tributes_sheep_and_phoenix_revives_after_torrential(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    own = tmp_path / "phoenix.ydk"
    other = tmp_path / "opponent.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        *([HAND] * 3), *([SCAPEGOAT] * 3), PHOENIX, TORRENTIAL,
        BOOK, BOOK, *VANILLA_DECK[10:]))) + "\n#extra\n!side\n")
    other.write_text("#main\n" + "\n".join(map(str, (
        *([BOOK] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    scripts = {f"goat/c{HAND}.lua", f"goat/c{PHOENIX}.lua",
               f"goat/c{SCAPEGOAT}.lua", f"official/c{TORRENTIAL}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required Phoenix scripts not installed")

    with GoatEnvironment(str(own), str(other), seed=476,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {HAND, SCAPEGOAT, TORRENTIAL}.issubset(c.code for c in obs.hand)
        assert PHOENIX not in {c.code for c in obs.hand}
        assert BOOK in {c.code for c in env.engine.probe.observation(1).hand}
        hand_summoned = goat_set = torrential_set = opponent_book_set = False
        goat_used = hand_used = sheep_tributed = phoenix_chosen = False
        phoenix_summoned = torrential_used = phoenix_destroyed = False
        revived = backrow_destroyed = False
        for _ in range(160):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.phase == "main1" and obs.acting_player == 0:
                if not hand_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == HAND), None)
                    hand_summoned |= action is not None
                if hand_summoned and not goat_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == SCAPEGOAT), None)
                    goat_set |= action is not None
                if goat_set and not torrential_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == TORRENTIAL), None)
                    torrential_set |= action is not None
            if obs.turn == 2 and obs.phase == "main1" and obs.acting_player == 1 \
                    and not opponent_book_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == BOOK), None)
                opponent_book_set |= action is not None
            if obs.turn == 2 and obs.phase == "end" and obs.acting_player == 0 \
                    and not goat_used:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                goat_used |= action is not None
            if obs.turn == 3 and obs.phase == "main1" and obs.acting_player == 0:
                if goat_used and not hand_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == HAND), None)
                    hand_used |= action is not None
                if hand_used and not sheep_tributed and action is None \
                        and actions[0].kind in ("select_card", "tribute"):
                    action = next((a for a in actions if a.parameters.get("code") in SHEEP), None)
                    sheep_tributed |= action is not None
                if sheep_tributed and not phoenix_chosen and action is None \
                        and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == PHOENIX),
                                  None)
                    phoenix_chosen |= action is not None
            if any(c.code == PHOENIX and c.zone == "monster" for c in obs.field):
                phoenix_summoned = True
            if phoenix_summoned and not torrential_used and obs.acting_player == 0:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == TORRENTIAL), action)
                torrential_used |= action is not None and action.kind == "chain" \
                    and action.parameters.get("code") == TORRENTIAL
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if torrential_used and PHOENIX in {c.code for c in obs.graveyards[0]}:
                phoenix_destroyed = True
            if obs.turn == 5 and phoenix_destroyed and PHOENIX in {
                    c.code for c in obs.field if c.controller == 0 and c.zone == "monster"}:
                revived = True
                if BOOK in {c.code for c in obs.graveyards[1]} and not obs.chain:
                    assert not any(c.code == BOOK and c.zone == "spell_trap"
                                   for c in obs.field)
                    assert obs.turn_player == 0
                    assert {HAND, TORRENTIAL}.issubset(
                        c.code for c in obs.graveyards[0])
                    assert not any(c.code in SHEEP for c in obs.field)
                    backrow_destroyed = True
                    break
        assert all((hand_summoned, goat_set, torrential_set, opponent_book_set,
                    goat_used, hand_used, sheep_tributed, phoenix_chosen,
                    phoenix_summoned, torrential_used, phoenix_destroyed, revived,
                    backrow_destroyed)), (
                        obs.turn, obs.phase, obs.acting_player)
        assert scripts.issubset(env.engine.probe.loaded_script_sha256)
        agents = (RandomAgent(476), RandomAgent(477))
        for _ in range(3000):
            if env.is_terminal():
                break
            obs = env.step(agents[obs.acting_player].select_action(obs, env.legal_actions()))
        assert env.is_terminal(), "Phoenix fixture duel exceeded 3000 decisions"
        trajectory = env.trajectory()
    path = tmp_path / "phoenix.json"
    write_trajectory(path, trajectory)
    assert verify_trajectory(read_trajectory(path), ExperimentalOcgcoreEngine(root)) == len(
        trajectory.decisions)
    assert audit_trajectory_visibility(trajectory)["decisions"] == len(
        trajectory.decisions)
