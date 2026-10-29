"""MST removes a chained continuous Decree before Mirror Force resolves."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

ROYAL_DECREE = 51452091
MIRROR_FORCE = 44095762
MYSTICAL_SPACE_TYPHOON = 5318639


def _deck(path, cards):
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
@pytest.mark.parametrize("chain_mst", [False, True])
def test_mst_chained_to_decree_restores_mirror_force(tmp_path, chain_mst):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (ROYAL_DECREE, MIRROR_FORCE, MYSTICAL_SPACE_TYPHOON):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    attacker = _deck(tmp_path / "decree.ydk", (
        *([ROYAL_DECREE] * 3), *VANILLA_DECK[3:]))
    defender_cards = [MIRROR_FORCE, *VANILLA_DECK[1:]]
    defender_cards[7] = MYSTICAL_SPACE_TYPHOON
    defender = _deck(tmp_path / "mirror_mst.ydk", defender_cards)

    with GoatEnvironment(attacker, defender, seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {MIRROR_FORCE, MYSTICAL_SPACE_TYPHOON} <= {
            card.code for card in env.engine.probe.observation(1).hand}
        summoned = decree_set = mirror_set = mst_set = battle = attacked = False
        mirror_chained = decree_chained = mst_chained = mst_targeted = checked = False
        attacker_code = None
        agents = (RandomAgent(515), RandomAgent(516))
        for _ in range(5000):
            if env.is_terminal():
                break
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        attacker_code = action.parameters["code"]
                        summoned = True
                if action is None and not decree_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == ROYAL_DECREE), None)
                    decree_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                for code, done in ((MIRROR_FORCE, mirror_set),
                                   (MYSTICAL_SPACE_TYPHOON, mst_set)):
                    if action is None and not done:
                        action = next((a for a in actions if a.kind == "set_spell_trap"
                                       and a.parameters.get("code") == code), None)
                        if action is not None:
                            if code == MIRROR_FORCE:
                                mirror_set = True
                            else:
                                mst_set = True
            if obs.turn == 3 and obs.acting_player == 0 \
                    and obs.phase == "main1" and not battle:
                action = next((a for a in actions if a.kind == "battle_phase"), None)
                battle |= action is not None
            if battle and obs.turn == 3 and obs.acting_player == 0 \
                    and obs.phase == "battle_start" and not attacked:
                action = next((a for a in actions if a.kind == "attack"
                               and a.parameters.get("code") == attacker_code), None)
                attacked |= action is not None
            if attacked and obs.acting_player == 1 and not mirror_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == MIRROR_FORCE), None)
                mirror_chained |= action is not None
            if mirror_chained and obs.acting_player == 0 and not decree_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == ROYAL_DECREE), None)
                decree_chained |= action is not None
            if (chain_mst and decree_chained and obs.acting_player == 1
                    and not mst_chained):
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == MYSTICAL_SPACE_TYPHOON), None)
                mst_chained |= action is not None
            if (mst_chained and not mst_targeted and obs.acting_player == 1
                    and any(a.kind == "select_card" for a in actions)):
                assert [link.card_code for link in obs.chain] == [
                    MIRROR_FORCE, ROYAL_DECREE, MYSTICAL_SPACE_TYPHOON]
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == ROYAL_DECREE), None)
                mst_targeted |= action is not None
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if (mirror_chained and not checked and
                    MIRROR_FORCE in {card.code for card in obs.graveyards[1]}):
                assert decree_chained
                assert obs.life_points == (8000, 8000)
                surviving = [card for card in obs.field
                             if card.controller == 0 and card.zone == "monster"]
                if chain_mst:
                    assert mst_chained and mst_targeted
                    assert not surviving
                    assert attacker_code in {card.code for card in obs.graveyards[0]}
                    assert ROYAL_DECREE in {card.code for card in obs.graveyards[0]}
                    assert MYSTICAL_SPACE_TYPHOON in {
                        card.code for card in obs.graveyards[1]}
                else:
                    assert len(surviving) == 1
                    assert surviving[0].code == attacker_code
                    assert any(card.code == ROYAL_DECREE and card.position == "faceup"
                               for card in obs.field)
                checked = True
        assert checked and env.is_terminal(), "Decree/MST/Mirror duel did not finish"
        assert {f"official/c{code}.lua" for code in (
            ROYAL_DECREE, MIRROR_FORCE)} <= env.engine.probe.loaded_script_sha256.keys()
        if chain_mst:
            assert f"official/c{MYSTICAL_SPACE_TYPHOON}.lua" in (
                env.engine.probe.loaded_script_sha256)
        trajectory = env.trajectory()
    path = tmp_path / f"decree_mst_{chain_mst}.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    assert verify_trajectory(loaded, ExperimentalOcgcoreEngine(root)) == len(
        trajectory.decisions)
    assert audit_trajectory_visibility(loaded)["decisions"] == len(
        trajectory.decisions)
