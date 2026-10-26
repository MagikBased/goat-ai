"""Delinquent Duo remains legal against one opposing hand card."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

DUO = 44763025

# All 40 cards are legal to Set, so five Set backrow cards leave one hand card
# after the second player's first draw. The mix is a synthetic hand-size fixture.
SETTABLE_TRIPLES = (
    14087893, 64697231, 46411259, 41420027, 4178474,
    27174286, 56120475, 60082869, 98045062, 6733059,
)
SETTABLE_SINGLES = (
    DUO, 79571449, 19613556, 55144522, 45986603,
    44095762, 53582587, 5318639, 72892473, 97077563,
)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_duo_discards_the_only_opposing_hand_card_without_second_choice(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{DUO}.lua").is_file():
        pytest.skip("Delinquent Duo script not installed")
    duo_deck = tmp_path / "duo.ydk"
    duo_deck.write_text("#main\n" + "\n".join(map(str, (
        DUO, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    settable_deck = tmp_path / "settable.ydk"
    settable_deck.write_text("#main\n" + "\n".join(map(str, (
        *(code for code in SETTABLE_TRIPLES for _ in range(3)),
        *SETTABLE_SINGLES))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(duo_deck), str(settable_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert DUO in {c.code for c in obs.hand}
        set_count = 0
        activated = checked = False
        last_card = None
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / "duo_one_card.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1 and set_count < 5:
                action = next((a for a in actions if a.kind == "set_spell_trap"), None)
                if action is not None:
                    set_count += 1
            if obs.turn == 3 and obs.phase == "main1" \
                    and obs.acting_player == 0 and not activated:
                assert set_count == 5
                assert obs.opponent_hand_count == 1
                assert obs.known_opponent_hand_cards == ()
                assert all(c.code is None for c in obs.field
                           if c.controller == 1 and c.zone == "spell_trap")
                last_card = env.engine.probe.observation(1).hand[0].code
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == DUO), None)
                assert action is not None
                activated = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if activated and not checked and DUO in {c.code for c in obs.graveyards[0]}:
                assert obs.chain == ()
                assert obs.life_points == (7000, 8000)
                assert obs.opponent_hand_count == 0
                assert len(env.engine.probe.observation(1).hand) == 0
                assert last_card in {c.code for c in obs.graveyards[1]}
                assert not any(a.kind == "select_card" and a.parameters.get(
                    "location") == 2 for a in env.legal_actions())
                assert f"official/c{DUO}.lua" in env.engine.probe.loaded_script_sha256
                checked = True
    pytest.fail("one-card Delinquent Duo duel did not finish")
