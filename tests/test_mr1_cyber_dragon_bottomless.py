"""Cyber Dragon's inherent MR1 Summon and Bottomless response window."""

import hashlib
import os
import random
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.mr1_synchro_probe import (
    BOTTOMLESS_TRAP_HOLE,
    CYBER_DRAGON,
    Mr1SynchroProbeEngine,
)
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory


def _deck_with_opening_card(tmp_path, seat, card):
    permutation = list(range(40))
    random.Random(52 * 2 + seat).shuffle(permutation)
    main = list(VANILLA_DECK)
    main[permutation[34]] = card
    deck = tmp_path / f"cyber_seat_{seat}.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, main)) + "\n#extra\n!side\n")
    return deck


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
def test_cyber_dragon_special_summon_opens_bottomless_response(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    required = [root / f"scripts/official/c{code}.lua"
                for code in (CYBER_DRAGON, BOTTOMLESS_TRAP_HOLE)]
    if not all(path.is_file() for path in required):
        pytest.skip("required official scripts not installed")
    own = _deck_with_opening_card(tmp_path, 0, CYBER_DRAGON)
    other = _deck_with_opening_card(tmp_path, 1, BOTTOMLESS_TRAP_HOLE)
    results = {}
    for activate in (False, True):
        with GoatEnvironment(str(own), str(other), seed=52,
                             engine=Mr1SynchroProbeEngine(root)) as env:
            view = env.reset()
            assert CYBER_DRAGON in {card.code for card in view.hand}
            summoned_other = trap_set = cyber_summoned = False
            offered = resolved = None
            agents = (RandomAgent(52), RandomAgent(53))
            for index in range(3000):
                if env.is_terminal():
                    break
                actions = env.legal_actions()
                action = None
                if resolved is None:
                    if view.turn == 1 and view.acting_player == 0:
                        assert not any(a.kind == "special_summon" and
                                       a.parameters.get("code") == CYBER_DRAGON
                                       for a in actions)
                    if view.turn == 2 and view.acting_player == 1:
                        if not summoned_other:
                            action = next((a for a in actions if a.kind == "normal_summon"), None)
                            summoned_other = action is not None
                        elif not trap_set:
                            action = next((a for a in actions if a.kind == "set_spell_trap"
                                           and a.parameters.get("code") == BOTTOMLESS_TRAP_HOLE), None)
                            trap_set = action is not None
                    if (view.turn == 3 and view.acting_player == 0
                            and summoned_other and trap_set and not cyber_summoned):
                        action = next((a for a in actions if a.kind == "special_summon"
                                       and a.parameters.get("code") == CYBER_DRAGON), None)
                        cyber_summoned = action is not None
                    if cyber_summoned and offered is None and view.acting_player == 1:
                        trap = next((a for a in actions if a.kind == "chain"
                                     and a.parameters.get("code") == BOTTOMLESS_TRAP_HOLE), None)
                        if trap is not None:
                            offered = index
                            assert any(card.code == CYBER_DRAGON and card.attack == 2100
                                       for card in view.field)
                            action = trap if activate else next(
                                a for a in actions if a.kind == "pass")
                    if action is None:
                        action = next((a for kind in ("place", "select_position", "pass",
                                                       "end_phase", "yes", "select_card")
                                       for a in actions if a.kind == kind), actions[0])
                else:
                    action = agents[view.acting_player].select_action(view, actions)
                view = env.step(action)
                if offered is not None and resolved is None and index > offered \
                        and not view.chain:
                    resolved = index + 1
                    if activate:
                        assert CYBER_DRAGON in {card.code for card in view.banished[0]}
                        assert not any(card.code == CYBER_DRAGON for card in view.field)
                    else:
                        assert any(card.code == CYBER_DRAGON for card in view.field)
                        assert CYBER_DRAGON not in {card.code for card in view.banished[0]}
            assert env.is_terminal() and summoned_other and trap_set and cyber_summoned
            assert offered is not None and resolved is not None
            for path in required:
                assert env.engine.probe.loaded_script_sha256[
                    f"official/{path.name}"] == hashlib.sha256(path.read_bytes()).hexdigest()
            trajectory = env.trajectory()
            replay_path = tmp_path / f"cyber_bottomless_{activate}.json"
            write_trajectory(replay_path, trajectory)
        replay = read_trajectory(replay_path)
        assert verify_trajectory(replay, Mr1SynchroProbeEngine(root)) == len(replay.decisions)
        assert audit_trajectory_visibility(replay)["decisions"] == len(replay.decisions)
        results[activate] = (replay, offered)
    assert results[False][1] == results[True][1]
    assert results[False][0].decisions[:results[False][1]] == (
        results[True][0].decisions[:results[True][1]])
