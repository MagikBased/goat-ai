"""Gravekeeper's Spear Soldier pierces a Set monster with the GOAT field boost."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SPEAR_SOLDIER = 63695531
NECROVALLEY = 511002998  # pinned pre-errata variant
MECHANICALCHASER = VANILLA_DECK[20]  # 800 DEF; already at the seeded hand slot


def _deck(path, substitutions):
    cards = list(VANILLA_DECK)
    for index, code in substitutions:
        cards[index] = code
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
@pytest.mark.parametrize("field_active", [False, True], ids=("no-field", "necrovalley"))
def test_spear_soldier_pierces_hidden_defender(tmp_path, field_active):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"official/c{SPEAR_SOLDIER}.lua",
               f"pre-errata/c{NECROVALLEY}.lua")
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("historical Spear Soldier or Necrovalley script not installed")
    substitutions = [(2, SPEAR_SOLDIER)]
    if field_active:
        substitutions.append((1, NECROVALLEY))
    own = _deck(tmp_path / "spear.ydk", substitutions)
    other = _deck(tmp_path / "defender.ydk", ())

    with GoatEnvironment(own, other, seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        view = env.reset()
        assert SPEAR_SOLDIER in {card.code for card in view.hand}
        assert MECHANICALCHASER in {card.code for card in env.engine.probe.observation(1).hand}
        activated = not field_active
        summoned = set_defender = attacked = resolved = False
        for _ in range(120):
            actions = env.legal_actions()
            action = None
            if view.turn == 1 and view.acting_player == 0:
                if not activated:
                    action = next((a for a in actions if a.kind == "activate" and
                                   a.parameters.get("code") == NECROVALLEY), None)
                    activated = action is not None
                if activated and not summoned and action is None:
                    action = next((a for a in actions if a.kind == "normal_summon" and
                                   a.parameters.get("code") == SPEAR_SOLDIER), None)
                    summoned = action is not None
            if view.turn == 2 and view.acting_player == 1 and not set_defender:
                action = next((a for a in actions if a.kind == "set_monster" and
                               a.parameters.get("code") == MECHANICALCHASER), None)
                set_defender = action is not None
            if view.turn == 3 and view.acting_player == 0:
                if view.phase == "main1":
                    action = next((a for a in actions if a.kind == "battle_phase"), None)
                if view.phase == "battle_start" and not attacked:
                    assert any(card.controller == 1 and card.zone == "monster" and
                               card.code is None and card.position == "facedown"
                               for card in view.field)
                    attacker = next(card for card in view.field
                                    if card.code == SPEAR_SOLDIER)
                    assert attacker.attack == (2000 if field_active else 1500)
                    action = next((a for a in actions if a.kind == "attack" and
                                   a.parameters.get("code") == SPEAR_SOLDIER), None)
                    attacked = action is not None
                if attacked and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("controller") == 1),
                                  None)
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase", "main2")), actions[0])
            view = env.step(action)
            if attacked and MECHANICALCHASER in {card.code for card in view.graveyards[1]}:
                assert view.life_points == (8000, 6800 if field_active else 7300)
                assert SPEAR_SOLDIER in {card.code for card in view.field}
                resolved = True
                break
        assert all((activated, summoned, set_defender, attacked, resolved))
        assert f"official/c{SPEAR_SOLDIER}.lua" in env.engine.probe.loaded_script_sha256
        if field_active:
            assert f"pre-errata/c{NECROVALLEY}.lua" in (
                env.engine.probe.loaded_script_sha256)

        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(5000):
            if env.is_terminal():
                break
            actions = env.legal_actions()
            view = env.step(agents[view.acting_player].select_action(view, actions))
        assert env.is_terminal()
        trajectory = env.trajectory()
        path = tmp_path / f"spear_{field_active}.json"
        write_trajectory(path, trajectory)
    replay = read_trajectory(path)
    assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(replay.decisions)
    assert audit_trajectory_visibility(replay)["decisions"] == len(replay.decisions)
