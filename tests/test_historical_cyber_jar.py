"""Cyber Jar's public reveal and placement order in the pinned GOAT core."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

CYBER_JAR = 504700188


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_cyber_jar_reveals_both_decks_before_placements(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / "scripts/goat/c504700188.lua").is_file():
        pytest.skip("GOAT Cyber Jar script not installed")
    deck = tmp_path / "cyber_jar.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (CYBER_JAR, *VANILLA_DECK[1:]))) + "\n")
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        set_done = flip_done = False
        placement_players = []
        first_reveal = None
        for _ in range(80):
            actions = env.legal_actions()
            action = None
            if observation.acting_player == 0 and observation.turn == 1 and not set_done:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == CYBER_JAR), None)
                set_done |= action is not None
            if observation.acting_player == 0 and observation.turn == 3 and not flip_done:
                action = next((a for a in actions if a.kind == "flip_summon"
                               and a.parameters.get("code") == CYBER_JAR), None)
                flip_done |= action is not None
            if flip_done and action is None and observation.public_reveals:
                first_reveal = first_reveal or observation.public_reveals
                if any(a.kind == "place" for a in actions):
                    placement_players.append(observation.acting_player)
            if action is None and observation.acting_player == 1 and any(
                    a.kind == "select_position" and a.parameters.get("position") == 8
                    for a in actions):
                action = next(a for a in actions if a.kind == "select_position"
                              and a.parameters.get("position") == 8)
            if action is None:
                action = next((a for a in actions if a.kind == "end_phase"), None)
            if action is None:
                action = next((a for a in actions if a.kind == "pass"), actions[0])
            observation = env.step(action)
            if len(observation.field) == 10:
                break
        assert set_done and flip_done
        assert first_reveal is not None
        assert [(r.player, len(r.codes)) for r in first_reveal] == [(0, 5), (1, 5)]
        assert placement_players == [0] * 5 + [1] * 5
        assert len(observation.field) == 10
        opponent_set = [c for c in observation.field if c.controller == 1
                        and c.position == "facedown"]
        assert opponent_set and all(c.code is None for c in opponent_set)
