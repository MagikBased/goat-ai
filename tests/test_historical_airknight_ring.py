"""Ring at attack declaration prevents Airknight's battle-damage draw."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

GRACEFUL = 79571449
PREMATURE = 70828912
AIRKNIGHT = 18036057
RING = 511000824  # pre-errata: either player's face-up monster
SECOND_DISCARD = 79182538


def _deck(path, cards):
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("use_ring", [False, True])
def test_ring_at_airknight_attack_declaration_prevents_draw(tmp_path, use_ring):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"official/c{GRACEFUL}.lua", f"official/c{PREMATURE}.lua",
               f"official/c{AIRKNIGHT}.lua", f"pre-errata/c{RING}.lua")
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required pinned scripts not installed")
    own = _deck(tmp_path / "airknight.ydk", (
        GRACEFUL, PREMATURE, AIRKNIGHT, *VANILLA_DECK[3:]))
    other = _deck(tmp_path / "ring.ydk", (RING, *VANILLA_DECK[1:]))

    with GoatEnvironment(own, other, seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, PREMATURE, AIRKNIGHT} <= {c.code for c in obs.hand}
        assert RING in {c.code for c in env.engine.probe.observation(1).hand}
        graceful = discarded = premature = ring_set = attacked = responded = False
        ring_activated = target_selected = False
        before_deck = before_hand = None
        for _ in range(110):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate" and
                                   a.parameters.get("code") == GRACEFUL), None)
                    graceful |= action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {
                        c["code"] for c in a.parameters["cards"]} ==
                        {AIRKNIGHT, SECOND_DISCARD}), None)
                    discarded |= action is not None
                if discarded and not premature and action is None:
                    action = next((a for a in actions if a.kind == "activate" and
                                   a.parameters.get("code") == PREMATURE), None)
                    premature |= action is not None
                if premature and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") ==
                                   AIRKNIGHT and a.parameters.get("location") == 16), action)
            if obs.turn == 2 and obs.acting_player == 1 and not ring_set:
                action = next((a for a in actions if a.kind == "set_spell_trap" and
                               a.parameters.get("code") == RING), None)
                ring_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0:
                if obs.phase == "main1":
                    action = next((a for a in actions if a.kind == "battle_phase"), action)
                if obs.phase == "battle_start" and not attacked:
                    action = next((a for a in actions if a.kind == "attack" and
                                   a.parameters.get("code") == AIRKNIGHT), action)
                    if action is not None and action.kind == "attack":
                        before_deck = obs.deck_counts[0]
                        before_hand = len(obs.hand)
                        attacked = True
            if attacked and obs.acting_player == 1 and not responded:
                ring = next((a for a in actions if a.kind == "chain" and
                             a.parameters.get("code") == RING), None)
                if ring is not None:
                    assert obs.phase == "battle_step"
                    action = ring if use_ring else next(a for a in actions if a.kind == "pass")
                    responded = True
                    ring_activated = use_ring
            if ring_activated and not target_selected and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == AIRKNIGHT
                               and a.parameters.get("controller") == 0), None)
                target_selected |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase", "main2")), actions[0])
            obs = env.step(action)
            owner = env.engine.probe.observation(0)
            if use_ring and target_selected and owner.life_points == (5300, 6100):
                assert owner.deck_counts[0] == before_deck
                assert len(owner.hand) == before_hand
                assert any(c.code == AIRKNIGHT for c in owner.graveyards[0])
                break
            if not use_ring and responded and owner.life_points == (7200, 6100) and \
                    owner.deck_counts[0] == before_deck - 1:
                assert owner.deck_counts[0] == before_deck - 1
                assert len(owner.hand) == before_hand + 1
                assert any(c.code == AIRKNIGHT for c in owner.field)
                break
        else:
            pytest.fail(f"Airknight attack did not reach the Ring/pass outcome: "
                        f"turn={obs.turn} phase={obs.phase} lp={obs.life_points} "
                        f"flags={(graceful, discarded, premature, ring_set, attacked, responded, target_selected)}")

        assert set(scripts[:3]) <= env.engine.probe.loaded_script_sha256.keys()
        if use_ring:
            assert scripts[3] in env.engine.probe.loaded_script_sha256
        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(5000):
            if env.is_terminal():
                break
            legal = env.legal_actions()
            obs = env.step(agents[obs.acting_player].select_action(obs, legal))
        assert env.is_terminal()
        trajectory = env.trajectory()
        path = tmp_path / f"airknight_ring_{use_ring}.json"
        write_trajectory(path, trajectory)
        assert verify_trajectory(read_trajectory(path),
                                 ExperimentalOcgcoreEngine(root)) == len(trajectory.decisions)
        assert audit_trajectory_visibility(trajectory)["decisions"] == len(
            trajectory.decisions)
