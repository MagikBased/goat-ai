"""A Tributed Sinister Serpent can return after making Thousand-Eyes Restrict."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SERPENT = 511000818  # GOAT pre-errata identity
METAMORPHOSIS = 46411259
RESTRICT = 504700102  # GOAT Thousand-Eyes Restrict


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
@pytest.mark.parametrize("accept_return", [True, False])
def test_serpent_tributed_for_metamorphosis_has_optional_next_standby_return(
    tmp_path, accept_return,
):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"pre-errata/c{SERPENT}.lua", f"official/c{METAMORPHOSIS}.lua",
               f"goat/c{RESTRICT}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required historical scripts not installed")
    deck = tmp_path / "serpent_meta.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        SERPENT, METAMORPHOSIS, *VANILLA_DECK[2:])))
        + f"\n#extra\n{RESTRICT}\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {SERPENT, METAMORPHOSIS} <= {card.code for card in obs.hand}
        summoned = activated = tributed = fusion_chosen = responded = checked = False
        hand_before = None
        for _ in range(5000):
            if env.is_terminal():
                break
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == SERPENT), None)
                    summoned |= action is not None
                elif not activated:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == METAMORPHOSIS), None)
                    activated |= action is not None
                elif activated and not tributed and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == SERPENT
                                   and a.parameters.get("controller") == 0), None)
                    tributed |= action is not None
                elif tributed and not fusion_chosen and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == RESTRICT),
                                  None)
                    fusion_chosen |= action is not None
            if fusion_chosen and not checked and not obs.chain:
                assert SERPENT in {card.code for card in obs.graveyards[0]}
                assert METAMORPHOSIS in {card.code for card in obs.graveyards[0]}
                assert RESTRICT in {card.code for card in obs.field}
                assert obs.extra_deck_counts[0] == 0
                checked = True
            if (checked and obs.turn == 3 and obs.phase == "standby"
                    and obs.acting_player == 0 and not responded):
                choices = {a.kind: a for a in actions
                           if a.parameters.get("code") == SERPENT}
                assert {"yes", "no"} <= choices.keys()
                assert SERPENT in {card.code for card in obs.graveyards[0]}
                hand_before = len(obs.hand)
                action = choices["yes" if accept_return else "no"]
                responded = True
            if responded and obs.turn == 3 and obs.phase == "main1" and not obs.chain:
                assert (SERPENT in {card.code for card in obs.hand}) is accept_return
                assert (SERPENT in {card.code for card in obs.graveyards[0]}) is not accept_return
                assert len(obs.hand) == hand_before + int(accept_return)
                opponent = env.engine.probe.observation(1)
                assert (SERPENT in opponent.known_opponent_hand_cards) is accept_return
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                break
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            obs = env.step(action)
        else:
            pytest.fail("Serpent / Metamorphosis did not reach its return choice")
        assert summoned and activated and tributed and fusion_chosen and checked and responded
        agents = (RandomAgent(18), RandomAgent(19))
        for _ in range(5000):
            if env.is_terminal():
                break
            obs = env.step(agents[obs.acting_player].select_action(obs, env.legal_actions()))
        assert env.is_terminal(), "Serpent / Metamorphosis duel did not finish"
        path = tmp_path / f"serpent_meta_{int(accept_return)}.json"
        write_trajectory(path, env.trajectory())
        replay = read_trajectory(path)
        assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(
            replay.decisions)
        audit_trajectory_visibility(replay)
