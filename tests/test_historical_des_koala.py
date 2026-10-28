"""Des Koala's GOAT Flip damage uses the hand count at resolution."""

import hashlib
import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

DES_KOALA = 69579761
BOOK_OF_MOON = 14087893
JAR_OF_GREED = 83968380
PINNED_KOALA_SCRIPT_SHA256 = "6bf1d8a387bad90479c7fad6e7dd61b03e4a7fc6927f10f3070009bdabb1d4a7"


@pytest.mark.parametrize("set_card,chain_card", [
    (None, None), (BOOK_OF_MOON, None),
    (BOOK_OF_MOON, BOOK_OF_MOON), (JAR_OF_GREED, JAR_OF_GREED),
])
@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_des_koala_flip_damage_tracks_opponent_hand_count(
        tmp_path, set_card, chain_card):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    script = root / f"scripts/official/c{DES_KOALA}.lua"
    assert hashlib.sha256(script.read_bytes()).hexdigest() == PINNED_KOALA_SCRIPT_SHA256
    attacker = tmp_path / "koala.ydk"
    defender = tmp_path / "response.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        *(DES_KOALA for _ in range(3)), *VANILLA_DECK[3:])))
        + "\n#extra\n!side\n")
    defender.write_text("#main\n" + "\n".join(map(str, (
        *((set_card or BOOK_OF_MOON) for _ in range(3)), *VANILLA_DECK[3:])))
        + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=11,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        view = env.reset()
        koala_set = response_set = flipped = response_chained = book_targeted = False
        hand_count = None
        starting_lp = None
        damaged = False
        for _ in range(100):
            legal = env.legal_actions()

            def choose(kind, code=None, legal=legal):
                return next((a for a in legal if a.kind == kind and (
                    code is None or a.parameters.get("code") == code)), None)

            action = None
            if view.turn == 1 and view.acting_player == 0 and not koala_set:
                action = choose("set_monster", DES_KOALA)
                koala_set = action is not None
            if (set_card and view.turn == 2 and view.acting_player == 1
                    and not response_set):
                action = choose("set_spell_trap", set_card)
                response_set = action is not None
            if (chain_card and flipped and view.acting_player == 1
                    and view.chain and not response_chained):
                action = choose("chain", chain_card)
                response_chained = action is not None
            if (chain_card == BOOK_OF_MOON and response_chained
                    and not book_targeted and view.acting_player == 1):
                target = next((a for a in legal if a.kind == "select_card"
                               and a.parameters.get("controller") == 0
                               and a.parameters.get("location") == 4), None)
                if target is not None:
                    action = target
                    book_targeted = True
            if view.turn == 3 and view.acting_player == 0 and not flipped:
                action = choose("flip_summon", DES_KOALA)
                if action is not None:
                    flipped = True
                    hand_count = view.opponent_hand_count
                    assert hand_count == (5 if set_card else 6)
                    starting_lp = view.life_points[1]
                    assert len(view.known_opponent_hand_cards) == 0
            action = action or choose("place") or choose("pass") or choose("end_phase")
            assert action is not None
            view = env.step(action)
            if flipped and view.life_points[1] < starting_lp:
                resolved_count = hand_count + (chain_card == JAR_OF_GREED)
                assert view.life_points[1] == starting_lp - 400 * resolved_count
                assert view.opponent_hand_count == resolved_count
                if chain_card == BOOK_OF_MOON:
                    koala = next(card for card in view.field
                                 if card.controller == 0 and card.zone == "monster")
                    assert koala.position == "facedown"
                damaged = True
                break
        assert koala_set and flipped and damaged
        assert response_set == bool(set_card)
        assert response_chained == bool(chain_card)
        assert book_targeted == (chain_card == BOOK_OF_MOON)
        assert env.engine.probe.loaded_script_sha256[f"official/c{DES_KOALA}.lua"] == (
            PINNED_KOALA_SCRIPT_SHA256)

        agents = (RandomAgent(11), RandomAgent(12))
        for _ in range(3000):
            if env.is_terminal():
                break
            view = env.step(agents[view.acting_player].select_action(
                view, env.legal_actions()))
        assert env.is_terminal()
        trajectory = env.trajectory()

    path = tmp_path / "des_koala.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    assert verify_trajectory(loaded, ExperimentalOcgcoreEngine(root)) == len(
        loaded.decisions)
    assert audit_trajectory_visibility(loaded)["decisions"] == len(
        loaded.decisions)
