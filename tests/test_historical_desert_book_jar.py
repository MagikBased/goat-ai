"""June 2005 Desert Sunlight / Book of Moon / Morphing Jar chain."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.ocgcore_probe import UPSTREAM_BOOK_SHA256
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

JAR = 33508719
DESERT = 93747864
BOOK = 14087893
NOBLEMAN = 504700116


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_desert_book_desert_doubles_jar_flip_after_nobleman(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    own_cards = list(VANILLA_DECK)
    for index, code in ((0, JAR), (1, DESERT), (12, DESERT), (14, BOOK)):
        own_cards[index] = code
    other_cards = (NOBLEMAN, *VANILLA_DECK[1:])
    own_deck = tmp_path / "own.ydk"
    other_deck = tmp_path / "other.ydk"
    for path, cards in ((own_deck, own_cards), (other_deck, other_cards)):
        path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own_deck), str(other_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {JAR, BOOK, DESERT} <= {c.code for c in obs.hand}
        assert NOBLEMAN in {c.code for c in env.engine.probe.observation(1).hand}
        jar_set = book_set = noble_activated = book_chained = False
        deserts_set = deserts_chained = 0
        four_link_seen = two_flips_seen = False
        before_decks = None
        for _ in range(170):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not jar_set:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == JAR), None)
                    jar_set |= action is not None
                elif deserts_set < 2:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == DESERT), None)
                    deserts_set += action is not None
                elif not book_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOOK), None)
                    book_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not noble_activated:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == NOBLEMAN), None)
                noble_activated |= action is not None
            if (noble_activated and actions[0].kind == "select_card"
                    and obs.acting_player == 1):
                action = next((a for a in actions if a.parameters.get("controller") == 0
                               and a.parameters.get("location") == 4), None)
                assert action is not None and action.parameters.get("code") is None
                before_decks = obs.deck_counts
            chain = [link.card_code for link in obs.chain]
            if chain == [NOBLEMAN] and obs.acting_player == 0 and deserts_chained == 0:
                assert not any(a.kind == "chain" and a.parameters.get("code") == BOOK
                               for a in actions)
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == DESERT), None)
                assert action is not None
                deserts_chained = 1
            if chain == [NOBLEMAN, DESERT] and obs.acting_player == 0 and not book_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK), None)
                assert action is not None, "Book must be legal against pending Desert"
                book_chained = True
            if book_chained and actions[0].kind == "select_card" and obs.acting_player == 0:
                action = next((a for a in actions if a.parameters.get("controller") == 0
                               and a.parameters.get("location") == 4), None)
                assert action is not None and action.parameters.get("code") == JAR
            if (chain == [NOBLEMAN, DESERT, BOOK] and obs.acting_player == 0
                    and actions[0].kind in ("chain", "pass")
                    and deserts_chained == 1):
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == DESERT), None)
                assert action is not None, (obs.acting_player, actions)
                deserts_chained = 2
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            chain = [link.card_code for link in obs.chain]
            four_link_seen |= chain == [NOBLEMAN, DESERT, BOOK, DESERT]
            two_flips_seen |= chain == [JAR, JAR]
            if (two_flips_seen and not obs.chain and before_decks is not None
                    and obs.deck_counts == (before_decks[0] - 10,
                                            before_decks[1] - 10)):
                assert four_link_seen
                assert any(c.code == JAR and c.position == "faceup"
                           for c in obs.field)
                assert JAR not in {c.code for c in obs.banished[0]}
                assert len(obs.hand) == 5
                assert len(env.engine.probe.observation(1).hand) == 5
                assert env.engine.probe.loaded_script_sha256[
                    "official/c14087893.lua"] != UPSTREAM_BOOK_SHA256
                agents = (RandomAgent(52), RandomAgent(53))
                for _ in range(5000):
                    obs = env.step(agents[obs.acting_player].select_action(
                        obs, env.legal_actions()))
                    if env.is_terminal():
                        path = tmp_path / "desert_book_jar.json"
                        write_trajectory(path, env.trajectory())
                        trajectory = read_trajectory(path)
                        audit_trajectory_visibility(trajectory)
                        assert verify_trajectory(
                            trajectory, ExperimentalOcgcoreEngine(root)) == len(
                                trajectory.decisions)
                        return
                pytest.fail("four-link duel did not reach terminal within 5000 decisions")
    pytest.fail("four-link historical chain did not resolve within 170 decisions")
