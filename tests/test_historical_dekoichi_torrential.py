"""Torrential destroys a Flip Summoned Dekoichi without stopping its draw."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

DEKOICHI = 87621407
TORRENTIAL = 53582587


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_torrential", [False, True])
def test_torrential_chained_to_dekoichi_flip_does_not_stop_draw(
        tmp_path, chain_torrential):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (DEKOICHI, TORRENTIAL)}
    if any(not (root / "scripts" / relative).is_file() for relative in scripts):
        pytest.skip("required card script not installed")
    dekoichi_deck = tmp_path / "dekoichi.ydk"
    dekoichi_deck.write_text("#main\n" + "\n".join(map(str, (
        *([DEKOICHI] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    trap_deck = tmp_path / "torrential.ydk"
    trap_deck.write_text("#main\n" + "\n".join(map(str, (
        TORRENTIAL, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(dekoichi_deck), str(trap_deck), seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert DEKOICHI in {c.code for c in obs.hand}
        assert TORRENTIAL in {c.code for c in env.engine.probe.observation(1).hand}
        set_monster = set_trap = flipped = responded = checked = False
        deck_before = hand_before = None
        agents = (RandomAgent(15), RandomAgent(16))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"dekoichi_torrential_{chain_torrential}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not set_monster:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == DEKOICHI), None)
                set_monster |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not set_trap:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == TORRENTIAL), None)
                set_trap |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not flipped:
                action = next((a for a in actions if a.kind == "flip_summon"
                               and a.parameters.get("code") == DEKOICHI), None)
                if action is not None:
                    deck_before = obs.deck_counts[0]
                    hand_before = len(obs.hand)
                    flipped = True
            if flipped and obs.acting_player == 1 and not responded and obs.chain:
                assert [link.card_code for link in obs.chain] == [DEKOICHI]
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == TORRENTIAL), None)
                assert option is not None
                action = option if chain_torrential else next(
                    a for a in actions if a.kind == "pass")
                responded = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if responded and not checked and obs.turn == 3 and obs.acting_player == 0 \
                    and obs.phase == "main1" and not obs.chain \
                    and obs.deck_counts[0] == deck_before - 1:
                assert len(obs.hand) == hand_before + 1
                assert obs.life_points == (8000, 8000)
                if chain_torrential:
                    assert DEKOICHI in {c.code for c in obs.graveyards[0]}
                    assert TORRENTIAL in {c.code for c in obs.graveyards[1]}
                    assert not any(c.code == DEKOICHI for c in obs.field)
                    assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                else:
                    assert any(c.code == DEKOICHI and c.position == "faceup"
                               for c in obs.field)
                    assert any(c.code == TORRENTIAL and c.position == "facedown"
                               for c in env.engine.probe.observation(1).field)
                    assert TORRENTIAL not in {c.code for c in obs.graveyards[1]}
                    assert f"official/c{DEKOICHI}.lua" in (
                        env.engine.probe.loaded_script_sha256)
                checked = True
    pytest.fail("Dekoichi / Torrential duel did not finish")
