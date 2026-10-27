"""Period one-active-Field-Spell rule in the separate MR1 native protocol."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.mr1_synchro_probe import UMI, YAMI, Mr1SynchroProbeEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_second_players_umi_replaces_first_players_yami_and_duel_completes(tmp_path):
    native_root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    decks = []
    for name, field_code in (("yami", YAMI), ("umi", UMI)):
        path = tmp_path / f"{name}.ydk"
        path.write_text("#main\n" + "\n".join(map(str, (
            field_code, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
        decks.append(path)

    agents = (RandomAgent(52), RandomAgent(53))
    with GoatEnvironment(*(str(path) for path in decks), seed=52,
                         engine=Mr1SynchroProbeEngine(native_root)) as env:
        view = env.reset()
        activated = set()
        replacement_seen = False
        for index in range(3000):
            if env.is_terminal():
                break
            legal = env.legal_actions()
            intended = YAMI if view.acting_player == 0 else UMI
            action = None
            if intended not in activated:
                action = next((choice for choice in legal
                               if choice.kind == "activate"
                               and choice.parameters.get("code") == intended), None)
                if action is not None:
                    activated.add(intended)
            if action is None and not replacement_seen:
                action = next((choice for choice in legal
                               if choice.kind == "end_phase"), None)
            if action is None and not replacement_seen:
                action = next((choice for choice in legal
                               if choice.kind == "pass"), None)
            if action is None:
                action = agents[view.acting_player].select_action(view, legal)
            view = env.step(action)
            if not replacement_seen and activated == {YAMI, UMI}:
                fields = {(card.controller, card.code) for card in view.field
                          if card.zone == "spell_trap" and card.sequence == 5}
                if fields == {(1, UMI)}:
                    assert any(card.code == YAMI for card in view.graveyards[0])
                    replacement_seen = True
        assert replacement_seen, "MR1 Field Spell replacement was not observed"
        assert env.is_terminal(), "MR1 Field Spell duel exceeded 3000 decisions"
        trajectory = env.trajectory()

    assert trajectory.ruleset == "mr1-synchro-protocol"
    path = tmp_path / "mr1_field_spell.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    assert verify_trajectory(loaded, Mr1SynchroProbeEngine(native_root)) == len(
        loaded.decisions)
    assert audit_trajectory_visibility(loaded)["decisions"] == len(
        loaded.decisions)
