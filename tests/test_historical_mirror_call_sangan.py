"""Call chained to Mirror Force exposes Sangan to destruction and its search."""

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
SANGAN = 504700178  # GOAT variant
CALL = 97077563
MIRROR = 44095762


def _write_deck(path, replacements):
    cards = list(VANILLA_DECK)
    for index, code in replacements:
        cards[index] = code
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_call", [False, True])
def test_call_chained_to_mirror_revives_and_destroys_sangan(tmp_path, chain_call):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (GRACEFUL, CALL, MIRROR)}
    scripts.add(f"goat/c{SANGAN}.lua")
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required historical scripts not installed")
    own = _write_deck(tmp_path / "call_sangan.ydk", (
        (2, GRACEFUL), (1, SANGAN), (9, CALL)))
    other = _write_deck(tmp_path / "mirror.ydk", ((4, MIRROR),))

    with GoatEnvironment(own, other, seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert {GRACEFUL, SANGAN, CALL} <= {c.code for c in observation.hand}
        assert MIRROR in {c.code for c in env.engine.probe.observation(1).hand}
        graceful = discarded = call_set = summoned = mirror_set = attacked = False
        mirror_chained = call_responded = sangan_targeted = searched = False
        attacker_code = None
        before_deck = None
        for _ in range(110):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate" and
                                   a.parameters.get("code") == GRACEFUL), None)
                    graceful |= action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if SANGAN in {
                        c["code"] for c in a.parameters["cards"]} and CALL not in {
                            c["code"] for c in a.parameters["cards"]}), None)
                    discarded |= action is not None
                if discarded and not call_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap" and
                                   a.parameters.get("code") == CALL), None)
                    call_set |= action is not None
                if call_set and not summoned and action is None:
                    action = next((a for a in actions if a.kind == "normal_summon" and
                                   a.parameters.get("code") != SANGAN), None)
                    if action is not None:
                        attacker_code = action.parameters["code"]
                        summoned = True
            if observation.turn == 2 and observation.acting_player == 1 and \
                    not mirror_set:
                action = next((a for a in actions if a.kind == "set_spell_trap" and
                               a.parameters.get("code") == MIRROR), None)
                mirror_set |= action is not None
            if observation.turn == 3 and observation.acting_player == 0:
                if observation.phase == "main1":
                    action = next((a for a in actions if a.kind == "battle_phase"), action)
                if observation.phase == "battle_start" and not attacked:
                    action = next((a for a in actions if a.kind == "attack" and
                                   a.parameters.get("code") == attacker_code), None)
                    attacked |= action is not None
                if mirror_chained and not call_responded:
                    call = next((a for a in actions if a.kind == "chain" and
                                 a.parameters.get("code") == CALL), None)
                    if call is not None:
                        assert [link.card_code for link in observation.chain] == [MIRROR]
                        action = call if chain_call else next(
                            a for a in actions if a.kind == "pass")
                        call_responded = True
                if chain_call and call_responded and not sangan_targeted and \
                        actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") ==
                                   SANGAN and a.parameters.get("location") == 16), None)
                    sangan_targeted |= action is not None
                if sangan_targeted and not searched and action is None and \
                        actions[0].kind == "select_card" \
                        and SANGAN in {c.code for c in observation.graveyards[0]}:
                    assert all(a.parameters.get("location") == 1 and
                               "sequence" not in a.parameters for a in actions)
                    action = actions[0]
                    searched = True
            if observation.turn == 3 and observation.acting_player == 1 and \
                    attacked and not mirror_chained:
                action = next((a for a in actions if a.kind == "chain" and
                               a.parameters.get("code") == MIRROR), None)
                mirror_chained |= action is not None
                if mirror_chained:
                    before_deck = observation.deck_counts[0]
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase", "main2")), actions[0])
            observation = env.step(action)
            if call_responded and MIRROR in {c.code for c in observation.graveyards[1]}:
                assert attacker_code in {c.code for c in observation.graveyards[0]}
                assert SANGAN in {c.code for c in observation.graveyards[0]}
                assert (CALL in {c.code for c in observation.graveyards[0]}) == \
                    chain_call
                assert not any(c.zone == "monster" and c.controller == 0
                               for c in observation.field)
                if not chain_call:
                    assert observation.deck_counts[0] == before_deck
                    assert not searched
                    break
            if searched and observation.deck_counts[0] == before_deck - 1:
                assert chain_call and call_responded and sangan_targeted
                selected_code = action.parameters["code"]
                assert selected_code in {c.code for c in observation.hand}
                opponent = env.engine.probe.observation(1)
                assert selected_code in opponent.known_opponent_hand_cards
                assert len(opponent.private_reveals) == 1
                assert opponent.private_reveals[0].recipient == 1
                assert {c.code for c in opponent.private_reveals[0].cards} == {
                    selected_code}
                assert not env.engine.probe.observation(0).private_reveals
                break
        else:
            pytest.fail("Mirror / Call / Sangan line did not resolve")

        required = scripts if chain_call else scripts - {f"goat/c{SANGAN}.lua"}
        assert required <= env.engine.probe.loaded_script_sha256.keys()
        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(5000):
            if env.is_terminal():
                break
            legal = env.legal_actions()
            observation = env.step(
                agents[observation.acting_player].select_action(observation, legal))
        assert env.is_terminal(), "Mirror / Call duel exceeded 5000 decisions"
        trajectory = env.trajectory()
        path = tmp_path / f"mirror_call_{chain_call}.json"
        write_trajectory(path, trajectory)
        assert verify_trajectory(read_trajectory(path),
                                 ExperimentalOcgcoreEngine(root)) == len(
                                     trajectory.decisions)
        assert audit_trajectory_visibility(trajectory)["decisions"] == len(
            trajectory.decisions)
