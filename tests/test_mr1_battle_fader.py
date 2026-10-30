"""Period Battle Fader timing in the separate MR1 protocol probe."""

import hashlib
import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.mr1_synchro_probe import (
    BATTLE_FADER,
    TORRENTIAL_TRIBUTE,
    Mr1SynchroProbeEngine,
)
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
@pytest.mark.parametrize("use_fader", [False, True])
def test_battle_fader_ends_direct_attack_without_torrential_window(tmp_path, use_fader):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    script = root / f"scripts/official/c{BATTLE_FADER}.lua"
    if not script.is_file():
        pytest.skip("Battle Fader script not installed")
    attacker = tmp_path / "attacker.ydk"
    defender = tmp_path / "defender.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, VANILLA_DECK))
                        + "\n#extra\n!side\n")
    defender_cards = list(VANILLA_DECK)
    defender_cards[0] = BATTLE_FADER
    defender_cards[4] = TORRENTIAL_TRIBUTE
    defender.write_text("#main\n" + "\n".join(map(str, defender_cards))
                        + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), 100,
                         Mr1SynchroProbeEngine(root)) as env:
        view = env.reset()
        assert {BATTLE_FADER, TORRENTIAL_TRIBUTE} <= {
            card.code for card in env.engine.probe.observation(1).hand}
        summoned = set_torrential = attacked = answered = checked = False
        fader_on_field = fader_attack_started = fader_banished = False
        agents = (RandomAgent(200), RandomAgent(201))
        for _ in range(4000):
            if env.is_terminal():
                break
            actions = env.legal_actions()
            action = None
            if view.turn == 1 and view.acting_player == 0 and not summoned:
                action = next((candidate for candidate in actions
                               if candidate.kind == "normal_summon"), None)
                summoned |= action is not None
            if view.turn == 2 and view.acting_player == 1 and not set_torrential:
                action = next((candidate for candidate in actions
                               if candidate.kind == "set_spell_trap"
                               and candidate.parameters.get("code")
                               == TORRENTIAL_TRIBUTE), None)
                set_torrential |= action is not None
            if view.turn == 3 and view.acting_player == 0 and not attacked:
                if view.phase == "main1":
                    action = next((candidate for candidate in actions
                                   if candidate.kind == "battle_phase"), None)
                elif view.phase == "battle_start":
                    assert any(card.controller == 1 and card.zone == "spell_trap"
                               and card.position == "facedown" and card.code is None
                               for card in view.field)
                    assert not any(card.controller == 1 and card.zone == "monster"
                                   for card in view.field)
                    action = next((candidate for candidate in actions
                                   if candidate.kind == "attack"), None)
                    attacked |= action is not None
            if attacked and view.acting_player == 1 and not answered:
                fader = next((candidate for candidate in actions
                              if candidate.kind == "chain"
                              and candidate.parameters.get("code") == BATTLE_FADER), None)
                if fader is not None:
                    action = fader if use_fader else next(
                        candidate for candidate in actions if candidate.kind == "pass")
                    answered = True
            if answered and not checked and view.turn == 3 and not view.chain:
                if use_fader:
                    fader_on_field |= any(card.code == BATTLE_FADER for card in view.field)
                    if fader_on_field:
                        assert view.life_points == (8000, 8000)
                        assert any(card.code == TORRENTIAL_TRIBUTE
                                   and card.position == "facedown"
                                   for card in env.engine.probe.observation(1).field)
                        assert BATTLE_FADER not in {
                            card.code for card in env.engine.probe.observation(1).hand}
                        assert not any(candidate.kind == "chain"
                                       and candidate.parameters.get("code")
                                       == TORRENTIAL_TRIBUTE for candidate in actions)
                        assert not any(candidate.kind == "attack" for candidate in actions)
                        checked = view.phase == "main2"
                elif view.life_points[1] < 8000:
                    assert BATTLE_FADER in {
                        card.code for card in env.engine.probe.observation(1).hand}
                    checked = True
            if use_fader and checked and not fader_banished:
                if view.turn == 5 and view.acting_player == 0:
                    if view.phase == "main1":
                        action = next((candidate for candidate in actions
                                       if candidate.kind == "battle_phase"), None)
                    elif view.phase == "battle_start" and not fader_attack_started:
                        action = next((candidate for candidate in actions
                                       if candidate.kind == "attack"), None)
                        fader_attack_started |= action is not None
                    elif fader_attack_started and actions[0].kind == "select_card":
                        action = next((candidate for candidate in actions
                                       if candidate.parameters.get("controller") == 1
                                       and candidate.parameters.get("code") == BATTLE_FADER),
                                      None)
                if fader_attack_started and any(
                        card.code == BATTLE_FADER for card in view.banished[1]):
                    assert BATTLE_FADER not in {
                        card.code for card in view.graveyards[1]}
                    assert not any(card.code == BATTLE_FADER for card in view.field)
                    fader_banished = True
            if action is None:
                action = (next((candidate for candidate in actions
                                if candidate.kind in ("place", "select_position",
                                                      "pass", "end_phase")), None)
                          if not checked or use_fader and not fader_banished else None)
            if action is None:
                action = agents[view.acting_player].select_action(view, actions)
            view = env.step(action)
        assert summoned and set_torrential and attacked and answered and checked
        assert not use_fader or fader_attack_started and fader_banished
        assert env.is_terminal()
        trajectory = env.trajectory()
        assert trajectory.ruleset == "mr1-synchro-protocol"
        assert env.engine.probe.loaded_script_sha256[
            f"official/c{BATTLE_FADER}.lua"] == hashlib.sha256(script.read_bytes()).hexdigest()

    path = tmp_path / f"battle_fader_{use_fader}.json"
    write_trajectory(path, trajectory)
    replay = read_trajectory(path)
    assert replay == trajectory
    assert verify_trajectory(replay, Mr1SynchroProbeEngine(root)) == len(replay.decisions)
    assert audit_trajectory_visibility(replay)["decisions"] == len(replay.decisions)
