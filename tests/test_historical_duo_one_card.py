"""Delinquent Duo is legal against one opposing hand card, not an empty hand."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

DUO = 44763025
SETTABLE = (14087893, 94192409, 56120475, 60082869,
            4178474, 504700123)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("remaining", [0, 1])
def test_duo_one_card_activation_boundary(tmp_path, remaining):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{DUO}.lua").is_file():
        pytest.skip("Delinquent Duo script not installed")
    attacker = tmp_path / "duo.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        DUO, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    defender = tmp_path / "sets.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        *(code for code in SETTABLE for _ in range(3)),
        *VANILLA_DECK[18:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=285,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert DUO in {c.code for c in obs.hand}
        set_monster = used = checked = False
        set_backrow = 0
        last_card = None
        agents = (RandomAgent(285), RandomAgent(286))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"duo_{remaining}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1:
                if not set_monster:
                    action = next((a for a in actions if a.kind == "set_monster"), None)
                    set_monster |= action is not None
                elif set_backrow < 5 - remaining:
                    action = next((a for a in actions if a.kind == "set_spell_trap"), None)
                    set_backrow += action is not None
            if obs.turn == 3 and obs.phase == "main1" \
                    and obs.acting_player == 0 and set_backrow == 5 - remaining \
                    and not used and not checked and any(a.kind == "end_phase"
                                                       for a in actions):
                assert obs.opponent_hand_count == remaining
                assert not obs.known_opponent_hand_cards
                option = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == DUO), None)
                if remaining:
                    assert option is not None
                    last_card = env.engine.probe.observation(1).hand[0].code
                    action = option
                    used = True
                else:
                    assert option is None
                    assert obs.life_points == (8000, 8000)
                    checked = True
            if used and not checked and obs.acting_player == 1:
                assert actions[0].kind != "select_card"
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if used and not checked and DUO in {c.code for c in obs.graveyards[0]} \
                    and not obs.chain:
                assert obs.life_points == (7000, 8000)
                assert obs.opponent_hand_count == 0
                assert last_card in {c.code for c in obs.graveyards[1]}
                assert env.engine.probe.observation(1).hand == ()
                assert f"official/c{DUO}.lua" in env.engine.probe.loaded_script_sha256
                checked = True
    pytest.fail("Duo one-card/empty-hand duel did not finish")
