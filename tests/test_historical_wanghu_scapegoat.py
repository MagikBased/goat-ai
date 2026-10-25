"""GOAT King Tiger Wanghu destroys new Sheep Tokens, not existing ones."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

WANGHU = 504700143  # GOAT variant
SCAPEGOAT = 504700123  # GOAT variant
SHEEP_TOKENS = {73915052, 73915053, 73915054, 73915055}


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("wanghu_first", [False, True])
def test_wanghu_only_destroys_sheep_summoned_while_faceup(tmp_path, wanghu_first):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{code}.lua" for code in (WANGHU, SCAPEGOAT)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("GOAT card script not installed")
    decks = []
    for name, code in (("wanghu", WANGHU), ("scapegoat", SCAPEGOAT)):
        deck = tmp_path / f"{name}.ydk"
        deck.write_text("#main\n" + "\n".join(map(str, (
            *([code] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
        decks.append(str(deck))

    with GoatEnvironment(*decks, seed=11,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert WANGHU in {card.code for card in obs.hand}
        assert SCAPEGOAT in {card.code for card in env.engine.probe.observation(1).hand}
        wanghu_summoned = goat_activated = goat_resolved = checked = False
        agents = (RandomAgent(11), RandomAgent(12))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"wanghu_goat_{wanghu_first}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.acting_player == 0 and not wanghu_summoned and (
                    (wanghu_first and obs.turn == 1)
                    or (not wanghu_first and obs.turn == 3 and goat_activated)):
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == WANGHU), None)
                wanghu_summoned |= action is not None
            if obs.acting_player == 1 and obs.turn == 2 and not goat_activated:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SCAPEGOAT), action)
                goat_activated |= action is not None and action.kind == "activate"
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if goat_activated and not goat_resolved and SCAPEGOAT in {
                    card.code for card in obs.graveyards[1]} and not obs.chain:
                sheep = [card for card in obs.field if card.controller == 1
                         and card.code in SHEEP_TOKENS]
                assert len(sheep) == (0 if wanghu_first else 4)
                goat_resolved = True
            if wanghu_summoned and goat_activated and not checked \
                    and goat_resolved \
                    and obs.turn >= (2 if wanghu_first else 3) \
                    and obs.acting_player == (1 if wanghu_first else 0) \
                    and obs.phase == "main1" and not obs.chain \
                    and any(card.code == WANGHU and card.position == "faceup"
                            for card in obs.field):
                sheep = [card for card in obs.field if card.controller == 1
                         and card.zone == "monster" and card.code in SHEEP_TOKENS]
                assert len(sheep) == (0 if wanghu_first else 4)
                assert SCAPEGOAT in {card.code for card in obs.graveyards[1]}
                assert obs.life_points == (8000, 8000)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail("Wanghu / Scapegoat duel did not finish")
