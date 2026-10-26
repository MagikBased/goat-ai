"""Airknight's attack replay against Scapegoat still pierces and draws."""

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
SCAPEGOAT = 504700123  # GOAT variant
SECOND_DISCARD = 79182538
SHEEP = {73915052, 73915053, 73915054, 73915055}


def _deck(path, cards):
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_scapegoat", [False, True])
def test_airknight_draws_after_direct_or_replayed_sheep_attack(
    tmp_path, chain_scapegoat,
):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in
               (GRACEFUL, PREMATURE, AIRKNIGHT)} | {f"goat/c{SCAPEGOAT}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required historical scripts not installed")
    own = _deck(tmp_path / "airknight.ydk", (
        GRACEFUL, PREMATURE, AIRKNIGHT, *VANILLA_DECK[3:]))
    other = _deck(tmp_path / "scapegoat.ydk", (
        SCAPEGOAT, SCAPEGOAT, SCAPEGOAT, *VANILLA_DECK[3:]))

    with GoatEnvironment(own, other, seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert {GRACEFUL, PREMATURE, AIRKNIGHT} <= {
            c.code for c in observation.hand}
        assert SCAPEGOAT in {c.code for c in env.engine.probe.observation(1).hand}
        graceful = discarded = premature = goat_set = attacked = False
        response_seen = goat_chained = replayed = token_chosen = False
        before_deck = before_hand = None
        for _ in range(100):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0:
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
            if observation.turn == 2 and observation.acting_player == 1 and not goat_set:
                action = next((a for a in actions if a.kind == "set_spell_trap" and
                               a.parameters.get("code") == SCAPEGOAT), None)
                goat_set |= action is not None
            if observation.turn == 3 and observation.acting_player == 0:
                if observation.phase == "main1":
                    action = next((a for a in actions if a.kind == "battle_phase"), action)
                if observation.phase == "battle_start" and not attacked:
                    assert not any(c.zone == "monster" and c.controller == 1
                                   for c in observation.field)
                    action = next((a for a in actions if a.kind == "attack" and
                                   a.parameters.get("code") == AIRKNIGHT), None)
                    if action is not None:
                        before_deck = observation.deck_counts[0]
                        before_hand = len(observation.hand)
                        attacked = True
                if attacked and goat_chained and not replayed and \
                        actions[0].kind == "attack":
                    assert sum(c.code in SHEEP and c.controller == 1
                               for c in observation.field) == 4
                    action = next((a for a in actions if a.kind == "attack" and
                                   a.parameters.get("code") == AIRKNIGHT), None)
                    replayed |= action is not None
                if replayed and not token_chosen and actions[0].kind == "select_card":
                    assert {a.parameters.get("code") for a in actions
                            if a.kind == "select_card"} == SHEEP
                    action = next(a for a in actions if a.kind == "select_card")
                    token_chosen = True
            if observation.turn == 3 and observation.acting_player == 1 and \
                    attacked and not response_seen:
                goat = next((a for a in actions if a.kind == "chain" and
                             a.parameters.get("code") == SCAPEGOAT), None)
                if goat is not None:
                    action = goat if chain_scapegoat else next(
                        a for a in actions if a.kind == "pass")
                    response_seen = True
                    goat_chained = chain_scapegoat
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase", "main2")), actions[0])
            observation = env.step(action)
            owner = env.engine.probe.observation(0)
            if attacked and owner.life_points[1] == 6100 and \
                    owner.deck_counts[0] == before_deck - 1:
                assert response_seen
                assert len(owner.hand) == before_hand + 1
                assert replayed == token_chosen == chain_scapegoat
                assert sum(c.code in SHEEP and c.controller == 1
                           for c in owner.field) == (4 if chain_scapegoat else 0)
                break
        else:
            pytest.fail("Airknight did not inflict damage and draw")

        # Damage and draw precede the destroyed Sheep Token leaving the field.
        if chain_scapegoat:
            for _ in range(12):
                if sum(c.code in SHEEP for c in observation.field) == 3:
                    break
                legal = env.legal_actions()
                action = next((a for a in legal if a.kind == "pass"), legal[0])
                observation = env.step(action)
            assert sum(c.code in SHEEP for c in observation.field) == 3
            assert all(c.code not in SHEEP for zone in
                       (*observation.graveyards, *observation.banished)
                       for c in zone)
        assert {f"official/c{code}.lua" for code in
                (GRACEFUL, PREMATURE, AIRKNIGHT)} <= (
                    env.engine.probe.loaded_script_sha256.keys())
        if chain_scapegoat:
            assert f"goat/c{SCAPEGOAT}.lua" in (
                env.engine.probe.loaded_script_sha256)

        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(5000):
            if env.is_terminal():
                break
            legal = env.legal_actions()
            observation = env.step(
                agents[observation.acting_player].select_action(observation, legal))
        assert env.is_terminal(), "Airknight / Scapegoat duel exceeded 5000 decisions"
        trajectory = env.trajectory()
        path = tmp_path / f"airknight_scapegoat_{chain_scapegoat}.json"
        write_trajectory(path, trajectory)
        assert verify_trajectory(read_trajectory(path),
                                 ExperimentalOcgcoreEngine(root)) == len(
                                     trajectory.decisions)
        assert audit_trajectory_visibility(trajectory)["decisions"] == len(
            trajectory.decisions)
