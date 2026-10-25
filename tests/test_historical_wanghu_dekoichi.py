"""GOAT Wanghu distinguishes Dekoichi's Normal Summon from Flip Summon."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

WANGHU = 504700143  # GOAT variant
DEKOICHI = 87621407


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("flip", [False, True])
def test_wanghu_destroys_normal_summoned_but_not_flip_summoned_dekoichi(
        tmp_path, flip):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{WANGHU}.lua", f"official/c{DEKOICHI}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required GOAT card script not installed")
    decks = []
    for name, code in (("wanghu", WANGHU), ("dekoichi", DEKOICHI)):
        deck = tmp_path / f"{name}.ydk"
        deck.write_text("#main\n" + "\n".join(map(str, (
            *([code] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
        decks.append(str(deck))

    with GoatEnvironment(*decks, seed=11,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert WANGHU in {card.code for card in obs.hand}
        assert DEKOICHI in {card.code for card in env.engine.probe.observation(1).hand}
        wanghu_summoned = dekoichi_committed = dekoichi_flipped = checked = False
        deck_before = hand_before = None
        agents = (RandomAgent(11), RandomAgent(12))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"wanghu_dekoichi_{flip}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not wanghu_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == WANGHU), None)
                wanghu_summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not dekoichi_committed:
                action = next((a for a in actions if a.kind == (
                    "set_monster" if flip else "normal_summon")
                               and a.parameters.get("code") == DEKOICHI), None)
                dekoichi_committed |= action is not None
            if flip and dekoichi_committed and not dekoichi_flipped \
                    and obs.turn == 4 and obs.acting_player == 1:
                action = next((a for a in actions if a.kind == "flip_summon"
                               and a.parameters.get("code") == DEKOICHI), None)
                if action is not None:
                    deck_before = obs.deck_counts[1]
                    hand_before = len(obs.hand)
                    dekoichi_flipped = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if dekoichi_committed and not checked and obs.acting_player == 1 \
                    and obs.phase == "main1" and not obs.chain:
                if not flip and DEKOICHI in {card.code for card in obs.graveyards[1]}:
                    assert not any(card.code == DEKOICHI for card in obs.field)
                    assert obs.life_points == (8000, 8000)
                    assert f"goat/c{WANGHU}.lua" in (
                        env.engine.probe.loaded_script_sha256)
                    checked = True
                elif flip and dekoichi_flipped and obs.deck_counts[1] == deck_before - 1:
                    assert len(obs.hand) == hand_before + 1
                    assert any(card.code == DEKOICHI and card.position == "faceup"
                               for card in obs.field)
                    assert DEKOICHI not in {card.code for card in obs.graveyards[1]}
                    assert obs.life_points == (8000, 8000)
                    assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                    checked = True
    pytest.fail("Wanghu / Dekoichi duel did not finish")
