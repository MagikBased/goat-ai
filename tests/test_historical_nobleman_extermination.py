"""GOAT Nobleman of Extermination distinguishes a hidden Trap from a Spell."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

EXTERMINATION = 504700025  # historical Deck-verification script
SAKURETSU = 56120475
BOOK = 14087893


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_extermination_hidden_trap_vs_spell_has_same_target_choice(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{EXTERMINATION}.lua",
                     f"official/c{SAKURETSU}.lua", f"official/c{BOOK}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    attacker = tmp_path / "attacker.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        EXTERMINATION, *([SAKURETSU] * 3), *VANILLA_DECK[4:])))
        + "\n#extra\n!side\n")

    def run(target_code):
        defender = tmp_path / f"defender_{target_code}.ydk"
        defender.write_text("#main\n" + "\n".join(map(str, (
            *([target_code] * 3), *VANILLA_DECK[3:])))
            + "\n#extra\n!side\n")
        with GoatEnvironment(str(attacker), str(defender), seed=18,
                             engine=ExperimentalOcgcoreEngine(root)) as env:
            obs = env.reset()
            assert EXTERMINATION in {card.code for card in obs.hand}
            assert target_code in {card.code for card in
                                   env.engine.probe.observation(1).hand}
            set_target = activated = targeted = checked = False
            decision = None
            deck_before = hand_copies = None
            agents = (RandomAgent(18), RandomAgent(19))
            for _ in range(3000):
                if env.is_terminal():
                    break
                actions = env.legal_actions()

                def choose(kind, code=None):
                    return next((a for a in actions if a.kind == kind and
                                 (code is None or a.parameters.get("code") == code)), None)

                action = None
                if obs.turn == 2 and obs.acting_player == 1 and not set_target:
                    action = choose("set_spell_trap", target_code)
                    set_target = action is not None
                if obs.turn == 3 and obs.acting_player == 0 and set_target \
                        and not activated:
                    action = choose("activate", EXTERMINATION)
                    activated = action is not None
                if activated and not targeted and actions[0].kind == "select_card":
                    assert obs.viewer == obs.acting_player == 0
                    assert not obs.private_reveals
                    assert any(card.controller == 1 and card.zone == "spell_trap"
                               and card.position == "facedown" and card.code is None
                               for card in obs.field)
                    assert all("code" not in a.parameters for a in actions)
                    decision = (obs, actions)
                    deck_before = obs.deck_counts
                    hand_copies = tuple(sum(card.code == SAKURETSU for card in
                                            env.engine.probe.observation(seat).hand)
                                        for seat in (0, 1))
                    action = next(a for a in actions
                                  if a.parameters.get("controller") == 1)
                    targeted = True
                if action is None and not checked:
                    action = (choose("place") or choose("select_position")
                              or choose("pass") or choose("end_phase"))
                if action is None:
                    action = agents[obs.acting_player].select_action(obs, actions)
                obs = env.step(action)
                if targeted and not checked and not obs.chain and any(
                        card.code == target_code for card in obs.banished[1]):
                    assert EXTERMINATION in {card.code for card in obs.graveyards[0]}
                    if target_code == SAKURETSU:
                        assert sum(card.code == SAKURETSU for card in obs.banished[0]) \
                            == 3 - hand_copies[0]
                        assert sum(card.code == SAKURETSU for card in obs.banished[1]) \
                            == 3 - hand_copies[1]
                        assert obs.deck_counts == (
                            deck_before[0] - (3 - hand_copies[0]),
                            deck_before[1] - (2 - hand_copies[1]))
                        assert env.engine.probe.observation(0).private_reveals
                        assert env.engine.probe.observation(1).private_reveals
                    else:
                        assert obs.deck_counts == deck_before
                        assert sum(card.code == BOOK for card in obs.banished[1]) == 1
                        assert not env.engine.probe.observation(0).private_reveals
                        assert not env.engine.probe.observation(1).private_reveals
                    checked = True
            assert set_target and activated and targeted and checked
            assert env.is_terminal()
            assert f"goat/c{EXTERMINATION}.lua" in env.engine.probe.loaded_script_sha256
            path = tmp_path / f"extermination_{target_code}.json"
            write_trajectory(path, env.trajectory())
            replay = read_trajectory(path)
            audit_trajectory_visibility(replay)
            assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(
                replay.decisions)
            return decision

    trap_decision = run(SAKURETSU)
    spell_decision = run(BOOK)
    assert trap_decision == spell_decision
