"""Returning Premature Burial preserves its monster and permits reuse."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

GRACEFUL_CHARITY = 79571449
PREMATURE_BURIAL = 70828912
GIANT_TRUNADE = 42703248
HEAVY_STORM = 19613556
MYSTICAL_ELF = 15025844
MAD_DOG = 79182538


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("removal", (GIANT_TRUNADE, HEAVY_STORM))
def test_premature_return_vs_destruction(tmp_path, removal):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in
               (GRACEFUL_CHARITY, PREMATURE_BURIAL, removal)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card scripts not installed")
    deck = tmp_path / "premature_return.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL_CHARITY, PREMATURE_BURIAL, removal, *VANILLA_DECK[3:])))
        + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL_CHARITY, PREMATURE_BURIAL, removal} <= {
            card.code for card in obs.hand}
        graceful = discarded = first_revive = removed = second_revive = False
        for _ in range(100):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL_CHARITY), None)
                    graceful = action is not None
                elif not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"]
                                   for c in a.parameters["cards"]} ==
                                   {MYSTICAL_ELF, MAD_DOG}), None)
                    discarded = action is not None
                elif discarded and not first_revive:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == PREMATURE_BURIAL), None)
                    first_revive = action is not None
                elif first_revive and not removed and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == MYSTICAL_ELF and a.parameters.get("location") == 16), None)
                elif first_revive and not removed and any(
                        card.code == MYSTICAL_ELF and card.zone == "monster"
                        for card in obs.field):
                    assert obs.life_points == (7200, 8000)
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == removal), None)
                    removed = action is not None
                elif removed and removal == GIANT_TRUNADE and not second_revive:
                    if PREMATURE_BURIAL in {card.code for card in obs.hand}:
                        assert MYSTICAL_ELF in {card.code for card in obs.field}
                        assert PREMATURE_BURIAL not in {card.code for card in obs.graveyards[0]}
                        opponent = env.engine.probe.observation(1)
                        assert PREMATURE_BURIAL in opponent.known_opponent_hand_cards
                        action = next((a for a in actions if a.kind == "activate"
                                       and a.parameters.get("code") == PREMATURE_BURIAL), None)
                        second_revive = action is not None
                elif second_revive and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == MAD_DOG and a.parameters.get("location") == 16), None)
            if removed and removal == HEAVY_STORM and \
                    {HEAVY_STORM, PREMATURE_BURIAL} <= {
                        card.code for card in obs.graveyards[0]}:
                assert MYSTICAL_ELF in {card.code for card in obs.graveyards[0]}
                assert not any(card.zone == "monster" and card.controller == 0
                               for card in obs.field)
                break
            if second_revive and {MYSTICAL_ELF, MAD_DOG} <= {
                    card.code for card in obs.field}:
                assert obs.life_points == (6400, 8000)
                assert PREMATURE_BURIAL in {card.code for card in obs.field}
                break
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
        else:
            pytest.fail("Premature Burial removal line did not resolve")
        assert graceful and discarded and first_revive and removed
        assert second_revive == (removal == GIANT_TRUNADE)
        assert scripts <= env.engine.probe.loaded_script_sha256.keys()
        agents = (RandomAgent(701), RandomAgent(702))
        for _ in range(5000):
            if env.is_terminal():
                break
            obs = env.step(agents[obs.acting_player].select_action(obs, env.legal_actions()))
        assert env.is_terminal()
        path = tmp_path / "premature_return.json"
        write_trajectory(path, env.trajectory())
        replay = read_trajectory(path)
        assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(replay.decisions)
        assert audit_trajectory_visibility(replay)["decisions"] == len(replay.decisions)
