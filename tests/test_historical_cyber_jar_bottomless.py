"""Bottomless after Cyber Jar affects only opposing face-up eligible Summons."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

CYBER_JAR = 504700188
BOTTOMLESS = 504700052


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
@pytest.mark.parametrize("chain_bottomless", [False, True])
def test_bottomless_after_cyber_jar_main_phase_flip(tmp_path, chain_bottomless):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    required = (f"goat/c{CYBER_JAR}.lua", f"goat/c{BOTTOMLESS}.lua")
    if any(not (root / "scripts" / script).is_file() for script in required):
        pytest.skip("GOAT card script not installed")
    own = tmp_path / "cyber_jar.ydk"
    other = tmp_path / "bottomless.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        CYBER_JAR, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    other.write_text("#main\n" + "\n".join(map(str, (
        *VANILLA_DECK[:3], BOTTOMLESS, *VANILLA_DECK[4:])))
        + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(other), seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert CYBER_JAR in {card.code for card in obs.hand}
        assert BOTTOMLESS in {card.code for card in
                              env.engine.probe.observation(1).hand}
        set_jar = set_trap = flipped = responded = checked = False
        revealed_own = ()
        agents = (RandomAgent(3), RandomAgent(4))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"cyber_jar_bottomless_{chain_bottomless}.json"
                write_trajectory(path, env.trajectory())
                replay = read_trajectory(path)
                assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(
                    replay.decisions)
                audit_trajectory_visibility(replay)
                return
            actions = env.legal_actions()
            action = None
            if not checked and obs.turn == 1 and obs.acting_player == 0 \
                    and not set_jar:
                action = next((a for a in actions if a.kind == "set_monster" and
                               a.parameters.get("code") == CYBER_JAR), None)
                set_jar = action is not None
            if not checked and obs.turn == 2 and obs.acting_player == 1 \
                    and not set_trap:
                action = next((a for a in actions if a.kind == "set_spell_trap" and
                               a.parameters.get("code") == BOTTOMLESS), None)
                set_trap = action is not None
            if not checked and obs.turn == 3 and obs.acting_player == 0 \
                    and not flipped:
                assert set_jar and set_trap
                action = next((a for a in actions if a.kind == "flip_summon" and
                               a.parameters.get("code") == CYBER_JAR), None)
                flipped = action is not None
            if flipped and not responded and actions[0].kind == "select_position":
                position = 1 if obs.acting_player == 0 else 8
                action = next(a for a in actions if a.parameters.get("position") == position)
            if flipped and obs.acting_player == 1 and not responded:
                option = next((a for a in actions if a.kind == "chain" and
                               a.parameters.get("code") == BOTTOMLESS), None)
                if option is not None:
                    assert obs.turn == 3 and obs.phase == "main1" and not obs.chain
                    assert [(reveal.player, len(reveal.codes)) for reveal in
                            obs.public_reveals] == [(0, 5), (1, 5)]
                    own_monsters = [card for card in obs.field
                                    if card.controller == 0 and card.zone == "monster"]
                    other_monsters = [card for card in obs.field
                                      if card.controller == 1 and card.zone == "monster"]
                    assert len(own_monsters) == len(other_monsters) == 5
                    assert all(card.position == "faceup" and card.attack >= 1500
                               for card in own_monsters)
                    assert all(card.position == "facedown" for card in other_monsters)
                    revealed_own = next(reveal.codes for reveal in obs.public_reveals
                                        if reveal.player == 0)
                    opponent_view = env.engine.probe.observation(0)
                    assert all(card.code is None for card in opponent_view.field
                               if card.controller == 1 and card.zone == "monster")
                    action = option if chain_bottomless else next(
                        a for a in actions if a.kind == "pass")
                    responded = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if responded and not checked and not obs.chain and obs.phase == "main1":
                opponent_monsters = [card for card in obs.field
                                     if card.controller == 1 and card.zone == "monster"]
                if len(opponent_monsters) == 5:
                    assert not obs.banished[1]
                    if chain_bottomless:
                        if BOTTOMLESS not in {card.code for card in obs.graveyards[1]}:
                            continue
                        assert Counter(card.code for card in obs.banished[0]) \
                            == Counter(revealed_own)
                        assert not any(card.controller == 0 and card.zone == "monster"
                                       for card in obs.field)
                    else:
                        assert BOTTOMLESS not in {card.code for card in obs.graveyards[1]}
                        assert len([card for card in obs.field if card.controller == 0
                                    and card.zone == "monster"]) == 5
                        assert not obs.banished[0]
                    assert {f"goat/c{code}.lua" for code in (CYBER_JAR, BOTTOMLESS)} \
                        <= set(env.engine.probe.loaded_script_sha256)
                    checked = True
    pytest.fail("Cyber Jar/Bottomless branch did not reach terminal state")
