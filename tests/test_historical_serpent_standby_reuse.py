"""Pre-errata Serpent may return again after a Standby Phase discard."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

GRACEFUL = 79571449
SERPENT = 511000818
RAIGEKI_BREAK = 4178474


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_serpent_returns_twice_in_one_standby_after_raigeki_break(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{GRACEFUL}.lua", f"pre-errata/c{SERPENT}.lua",
               f"official/c{RAIGEKI_BREAK}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("Graceful / Serpent / Raigeki Break scripts not installed")
    own_deck = tmp_path / "serpent_break.ydk"
    own_deck.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL, SERPENT, RAIGEKI_BREAK, *VANILLA_DECK[3:])))
                        + "\n#extra\n!side\n")
    with GoatEnvironment(str(own_deck), "examples/decks/vanilla_probe.ydk", seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, SERPENT, RAIGEKI_BREAK} <= {card.code for card in obs.hand}
        graceful_used = serpent_discarded = trap_set = monster_set = False
        first_returned = break_used = break_discarded = break_targeted = False
        second_returned = False
        target_code = None
        for _ in range(110):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not graceful_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    graceful_used |= action is not None
                if graceful_used and not serpent_discarded \
                        and actions[0].kind == "select_cards":
                    action = next((a for a in actions if SERPENT in {
                        card["code"] for card in a.parameters["cards"]}
                        and RAIGEKI_BREAK not in {
                            card["code"] for card in a.parameters["cards"]}), None)
                    serpent_discarded |= action is not None
                if serpent_discarded and not trap_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == RAIGEKI_BREAK), None)
                    trap_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not monster_set:
                action = next((a for a in actions if a.kind == "set_monster"), None)
                if action is not None:
                    target_code = action.parameters["code"]
                    monster_set = True
            if obs.turn == 3 and obs.phase == "standby" \
                    and obs.acting_player == 0:
                if not first_returned:
                    assert SERPENT in {card.code for card in obs.graveyards[0]}
                    action = next((a for a in actions if a.kind in ("yes", "chain")
                                   and a.parameters.get("code") == SERPENT), action)
                    first_returned |= action is not None and action.parameters.get(
                        "code") == SERPENT
                elif not break_used and SERPENT in {card.code for card in obs.hand}:
                    action = next((a for a in actions if a.kind in ("activate", "chain")
                                   and a.parameters.get("code") == RAIGEKI_BREAK), action)
                    break_used |= action is not None and action.parameters.get(
                        "code") == RAIGEKI_BREAK
                elif break_targeted and not second_returned:
                    action = next((a for a in actions if a.kind in ("yes", "chain")
                                   and a.parameters.get("code") == SERPENT), action)
                    second_returned |= action is not None and action.parameters.get(
                        "code") == SERPENT
            if break_used and not break_discarded and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == SERPENT
                               and a.parameters.get("location") == 2), None)
                break_discarded |= action is not None
            if break_discarded and not break_targeted and action is None \
                    and actions[0].kind == "select_card":
                assert SERPENT in {card.code for card in obs.graveyards[0]}
                hidden = next(card for card in obs.field if card.controller == 1
                              and card.zone == "monster")
                assert hidden.position == "facedown" and hidden.code is None
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 4
                               and a.parameters.get("sequence") == hidden.sequence), None)
                assert action is not None and "code" not in action.parameters
                break_targeted = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if second_returned and obs.phase == "main1" and obs.turn == 3:
                assert SERPENT in {card.code for card in obs.hand}
                assert SERPENT not in {card.code for card in obs.graveyards[0]}
                assert target_code in {card.code for card in obs.graveyards[1]}
                assert obs.life_points == (8000, 8000)
                assert SERPENT in env.engine.probe.observation(
                    1).known_opponent_hand_cards
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                agents = (RandomAgent(100), RandomAgent(101))
                for _ in range(5000):
                    choice = agents[obs.acting_player].select_action(
                        obs, env.legal_actions())
                    obs = env.step(choice)
                    if env.is_terminal():
                        path = tmp_path / "serpent_standby_reuse.json"
                        write_trajectory(path, env.trajectory())
                        assert verify_trajectory(read_trajectory(path),
                                                 ExperimentalOcgcoreEngine(root)) == len(
                                                     env.trajectory().decisions)
                        return
                pytest.fail("Serpent Standby reuse duel did not finish")
    pytest.fail("Serpent was not offered a second Standby Phase return")
