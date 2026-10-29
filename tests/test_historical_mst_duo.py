"""Destroying an activated Delinquent Duo with MST does not negate it."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

MST = 5318639
DUO = 44763025


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_mst", (False, True))
def test_mst_response_destroys_duo_but_duo_still_discards(tmp_path, chain_mst):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (MST, DUO)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required official card script not installed")
    decks = []
    for name, code in (("mst", MST), ("duo", DUO)):
        deck = tmp_path / f"{name}.ydk"
        deck.write_text("#main\n" + "\n".join(map(str, (code, *VANILLA_DECK[1:])))
                        + "\n#extra\n!side\n")
        decks.append(deck)

    with GoatEnvironment(*(str(deck) for deck in decks), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert MST in {card.code for card in obs.hand}
        assert DUO in {card.code for card in env.engine.probe.observation(1).hand}
        mst_set = duo_activated = response_made = mst_targeted = False
        defender_hand_before = None
        for _ in range(90):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not mst_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == MST), None)
                mst_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and mst_set \
                    and not duo_activated:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == DUO), None)
                if action is not None:
                    duo_activated = True
                    defender_hand_before = obs.opponent_hand_count
            if duo_activated and obs.acting_player == 0 and not response_made:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == MST), None)
                if option is not None:
                    assert [link.card_code for link in obs.chain] == [DUO]
                    assert obs.life_points == (8000, 7000)
                    action = (option if chain_mst else next(a for a in actions
                                                             if a.kind == "pass"))
                    response_made = True
            if (chain_mst and response_made and not mst_targeted
                    and actions[0].kind == "select_card"):
                action = next((a for a in actions if a.parameters.get("code") == DUO
                               and a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 8), None)
                mst_targeted = action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if response_made and DUO in {c.code for c in obs.graveyards[1]} \
                    and not obs.chain and len(env.engine.probe.observation(0).hand) \
                    == defender_hand_before - 2:
                assert mst_targeted == chain_mst
                assert obs.life_points == (8000, 7000)
                assert (MST in {c.code for c in obs.graveyards[0]}) == chain_mst
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                break
        else:
            pytest.fail("MST / Duo chain did not resolve and discard two cards")

        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(3000):
            if env.is_terminal():
                break
            obs = env.step(agents[obs.acting_player].select_action(
                obs, env.legal_actions()))
        assert env.is_terminal(), "MST / Duo duel did not finish"
        path = tmp_path / f"mst_duo_{chain_mst}.json"
        write_trajectory(path, env.trajectory())
        saved = read_trajectory(path)
        assert verify_trajectory(saved, ExperimentalOcgcoreEngine(root)) == len(saved.decisions)
        audit_trajectory_visibility(saved)
