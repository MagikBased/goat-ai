"""Sangan's search waits for Metamorphosis, even if Solemn negates it."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SANGAN = 504700178
METAMORPHOSIS = 46411259
DRAGONESS = 70681994
MYSTICAL_ELF = 15025844
SOLEMN = 41420027


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("negate", [False, True])
def test_sangan_tributes_for_metamorphosis_then_searches_after_chain(tmp_path, negate):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{SANGAN}.lua", f"official/c{METAMORPHOSIS}.lua",
               f"official/c{DRAGONESS}.lua", f"official/c{SOLEMN}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required pinned card script not installed")
    actor = tmp_path / "sangan_meta.ydk"
    cards = (SANGAN, METAMORPHOSIS, METAMORPHOSIS, METAMORPHOSIS,
             MYSTICAL_ELF, *VANILLA_DECK[5:])
    assert len(cards) == 40
    actor.write_text("#main\n" + "\n".join(map(str, cards))
                     + f"\n#extra\n{DRAGONESS}\n!side\n")
    defender = tmp_path / "solemn.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (SOLEMN, *VANILLA_DECK[1:])))
                        + "\n#extra\n!side\n")

    with GoatEnvironment(str(actor), str(defender), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert {SANGAN, METAMORPHOSIS} <= {card.code for card in observation.hand}
        assert SOLEMN in {card.code for card in env.engine.probe.observation(1).hand}
        done: set[str] = set()
        checked_wait = False
        for _ in range(75):
            actions = env.legal_actions()
            action = None
            if observation.turn == 2 and observation.acting_player == 1 and "set" not in done:
                action = next((choice for choice in actions
                               if choice.kind == "set_spell_trap"
                               and choice.parameters.get("code") == SOLEMN), None)
                if action is not None:
                    done.add("set")
            if observation.turn == 3 and observation.acting_player == 0:
                for marker, kind, code in (
                    ("summon", "normal_summon", SANGAN),
                    ("meta", "activate", METAMORPHOSIS),
                    ("cost", "select_card", SANGAN),
                    ("fusion", "select_card", DRAGONESS),
                    ("search", "select_card", MYSTICAL_ELF),
                ):
                    if marker not in done and action is None:
                        action = next((choice for choice in actions
                                       if choice.kind == kind
                                       and choice.parameters.get("code") == code), None)
                        if action is not None:
                            done.add(marker)
                            break
            if (observation.turn == 3 and observation.acting_player == 1
                    and "cost" in done and "response" not in done):
                assert SANGAN in {card.code for card in observation.graveyards[0]}
                assert DRAGONESS not in {card.code for card in observation.field}
                assert not env.engine.probe.observation(1).private_reveals
                assert any(choice.kind == "chain"
                           and choice.parameters.get("code") == SOLEMN for choice in actions)
                checked_wait = True
                action = next((choice for choice in actions
                               if choice.kind == ("chain" if negate else "pass")
                               and (not negate or choice.parameters.get("code") == SOLEMN)),
                              None)
                assert action is not None
                done.add("response")
            if action is None:
                action = next((choice for choice in actions if choice.kind in
                               ("place", "select_position", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if "search" in done:
                assert checked_wait and {"set", "summon", "meta", "cost", "response"} <= done
                assert ("fusion" in done) is not negate
                assert SANGAN in {card.code for card in observation.graveyards[0]}
                assert METAMORPHOSIS in {card.code for card in observation.graveyards[0]}
                assert MYSTICAL_ELF in {card.code for card in observation.hand}
                assert observation.deck_counts[0] == 32
                assert (DRAGONESS in {card.code for card in observation.field}) is not negate
                assert observation.extra_deck_counts[0] == int(negate)
                assert observation.life_points == ((8000, 4000) if negate else (8000, 8000))
                reveal = env.engine.probe.observation(1).private_reveals
                assert len(reveal) == 1 and [card.code for card in reveal[0].cards] == [
                    MYSTICAL_ELF]
                assert env.engine.probe.observation(1).known_opponent_hand_cards == (
                    MYSTICAL_ELF,)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                break
        else:
            pytest.fail("Sangan / Metamorphosis did not reach its Deck search")
        agents = (RandomAgent(92), RandomAgent(93))
        for _ in range(5000):
            if env.is_terminal():
                break
            observation = env.step(agents[observation.acting_player].select_action(
                observation, env.legal_actions()))
        assert env.is_terminal()
        path = tmp_path / f"sangan_meta_solemn_{int(negate)}.json"
        write_trajectory(path, env.trajectory())
        trajectory = read_trajectory(path)
        assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) == len(
            trajectory.decisions)
        audit_trajectory_visibility(trajectory)
