"""Dustshoot still resolves after Scapegoat lowers the target hand below four."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

GOAT = 504700123
DUSTSHOOT = 64697231
BOOK = 14087893
BOTTOMLESS = 504700052
SAKURETSU = 56120475
SHEEP = {73915052, 73915053, 73915054, 73915055}


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_goat", [False, True])
def test_dustshoot_four_card_gate_survives_chained_scapegoat(tmp_path, chain_goat):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{GOAT}.lua", f"official/c{DUSTSHOOT}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card scripts not installed")
    own_cards = [GOAT, BOOK, BOOK, *VANILLA_DECK[3:]]
    own_cards = [BOTTOMLESS if code == 49003308 else
                 SAKURETSU if code == 49881766 else code for code in own_cards]
    own = tmp_path / "scapegoat.ydk"
    own.write_text("#main\n" + "\n".join(map(str, own_cards)) + "\n#extra\n!side\n")
    other = tmp_path / "dustshoot.ydk"
    other.write_text("#main\n" + "\n".join(map(str, (
        DUSTSHOOT, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(other), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GOAT, BOOK, BOTTOMLESS, SAKURETSU} <= {c.code for c in obs.hand}
        assert DUSTSHOOT in {c.code for c in env.engine.probe.observation(1).hand}
        backrow_set = 0
        dust_set = dust_used = goat_responded = selected = checked = False
        hand_before = selected_code = deck_before = None
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"dustshoot_goat_response_{chain_goat}.json"
                write_trajectory(path, env.trajectory())
                trajectory = read_trajectory(path)
                assert audit_trajectory_visibility(trajectory)["decisions"] == len(
                    trajectory.decisions)
                assert verify_trajectory(trajectory,
                                         ExperimentalOcgcoreEngine(root)) == len(
                                             trajectory.decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and backrow_set < 3:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") in
                               {BOOK, BOTTOMLESS, SAKURETSU}), None)
                backrow_set += action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not dust_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                dust_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 1 and dust_set \
                    and not dust_used:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                if option is not None:
                    assert backrow_set == 3 and obs.opponent_hand_count == 4
                    assert obs.known_opponent_hand_cards == ()
                    hand_before = Counter(c.code for c in
                                          env.engine.probe.observation(0).hand)
                    assert hand_before[GOAT] == 1
                    deck_before = obs.deck_counts[0]
                    action = option
                    dust_used = True
            if dust_used and obs.acting_player == 0 and not goat_responded:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == GOAT), None)
                if option is not None:
                    assert tuple(link.card_code for link in obs.chain) == (DUSTSHOOT,)
                    assert len(obs.hand) == 4
                    action = option if chain_goat else next(a for a in actions
                                                            if a.kind == "pass")
                    goat_responded = True
            if dust_used and goat_responded and not selected \
                    and actions[0].kind == "select_card":
                assert obs.acting_player == 1
                expected_hand = hand_before - (Counter((GOAT,)) if chain_goat
                                               else Counter())
                assert obs.opponent_hand_count == sum(expected_hand.values())
                assert Counter(obs.known_opponent_hand_cards) == expected_hand
                assert all("sequence" not in a.parameters for a in actions)
                assert not env.engine.probe.observation(0).private_reveals
                assert (sum(c.code in SHEEP for c in obs.field) == 4) == chain_goat
                action = actions[0]
                selected_code = action.parameters["code"]
                selected = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if selected and not checked and DUSTSHOOT in {c.code for c in
                                                            obs.graveyards[1]} \
                    and not obs.chain:
                own_view = env.engine.probe.observation(0)
                dust_view = env.engine.probe.observation(1)
                expected_hand = (hand_before - (Counter((GOAT,)) if chain_goat
                                                else Counter())
                                 - Counter((selected_code,)))
                assert own_view.deck_counts[0] == deck_before + 1
                assert Counter(c.code for c in own_view.hand) == expected_hand
                assert Counter(dust_view.known_opponent_hand_cards) == expected_hand
                assert (sum(c.code in SHEEP for c in own_view.field) == 4) == chain_goat
                assert (GOAT in {c.code for c in own_view.graveyards[0]}) == chain_goat
                assert not own_view.private_reveals
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail(f"Dustshoot / Scapegoat reverse chain stalled: turn={obs.turn} "
                f"phase={obs.phase} setup={backrow_set}/{dust_set}/{dust_used} "
                f"response={goat_responded}/{selected}/{checked}")
