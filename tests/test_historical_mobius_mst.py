"""Mobius targets one or two hidden backrow cards and resolves surviving targets."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

MOBIUS = 4929256
TRIBUTE = 15025844
BOOK_OF_MOON = 14087893
SAKURETSU_ARMOR = 56120475
MST = 5318639


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("mode", ["one_target", "two_targets", "mst_response"])
def test_mobius_target_count_and_partial_resolution(tmp_path, mode):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (MOBIUS, MST)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("Mobius / Mystical Space Typhoon scripts not installed")
    own = tmp_path / "mobius.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        TRIBUTE, MOBIUS, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    other = tmp_path / "backrow.ydk"
    other.write_text("#main\n" + "\n".join(map(str, (
        BOOK_OF_MOON, SAKURETSU_ARMOR, MST, *VANILLA_DECK[3:])))
                     + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(other), seed=215,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {TRIBUTE, MOBIUS} <= {c.code for c in obs.hand}
        assert {BOOK_OF_MOON, SAKURETSU_ARMOR, MST} <= {
            c.code for c in env.engine.probe.observation(1).hand}
        tribute_summoned = mobius_summoned = tributed = effect_accepted = False
        backrow_set: set[int] = set()
        targets_selected = mst_chained = mst_targeted = False
        for _ in range(110):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not tribute_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == TRIBUTE), None)
                tribute_summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                for code in (BOOK_OF_MOON, SAKURETSU_ARMOR, MST):
                    if code not in backrow_set:
                        action = next((a for a in actions if a.kind == "set_spell_trap"
                                       and a.parameters.get("code") == code), None)
                        if action is not None:
                            backrow_set.add(code)
                            break
            if obs.turn == 3 and obs.acting_player == 0 and not mobius_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == MOBIUS), None)
                mobius_summoned |= action is not None
            if mobius_summoned and not tributed and action is None:
                action = next((a for a in actions if a.kind == "tribute"
                               and a.parameters.get("code") == TRIBUTE), None)
                tributed |= action is not None
            if tributed and not effect_accepted and obs.acting_player == 0:
                action = next((a for a in actions if a.kind == "yes"
                               and a.parameters.get("code") == MOBIUS), action)
                effect_accepted |= action is not None and action.kind == "yes"
            if effect_accepted and not targets_selected \
                    and actions[0].kind in ("select_card", "select_cards"):
                assert [link.card_code for link in obs.chain] == [MOBIUS]
                assert len([c for c in obs.field if c.zone == "spell_trap"
                            and c.controller == 1 and c.code is None]) == 3
                for candidate in actions:
                    if candidate.kind == "select_card":
                        assert "code" not in candidate.parameters
                    else:
                        assert all("code" not in card
                                   for card in candidate.parameters["cards"])
                if mode == "one_target":
                    action = next((a for a in actions if a.kind == "select_card"
                                   and a.parameters["sequence"] == 0), None)
                else:
                    action = next((a for a in actions if a.kind == "select_cards"
                                   and {c["sequence"] for c in a.parameters["cards"]}
                                   == {0, 1}), None)
                assert action is not None
                targets_selected = True
            if mode == "mst_response" and targets_selected \
                    and obs.acting_player == 1 and not mst_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == MST), None)
                assert action is not None
                mst_chained = True
            if mst_chained and not mst_targeted and obs.acting_player == 1 \
                    and actions[0].kind == "select_card":
                assert [link.card_code for link in obs.chain] == [MOBIUS, MST]
                action = next((a for a in actions if a.parameters.get("code")
                               == BOOK_OF_MOON and a.parameters.get("controller") == 1),
                              None)
                assert action is not None
                mst_targeted = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if targets_selected and obs.turn == 3 and obs.acting_player == 0 \
                    and obs.chain == () and any(a.kind == "battle_phase"
                                                for a in env.legal_actions()):
                own_view = env.engine.probe.observation(0)
                assert {TRIBUTE} <= {c.code for c in own_view.graveyards[0]}
                assert any(c.code == MOBIUS and c.position == "faceup"
                           for c in own_view.field)
                assert BOOK_OF_MOON in {c.code for c in own_view.graveyards[1]}
                if mode == "one_target":
                    assert SAKURETSU_ARMOR not in {
                        c.code for c in own_view.graveyards[1]}
                    assert MST not in {c.code for c in own_view.graveyards[1]}
                    assert len([c for c in own_view.field if c.controller == 1
                                and c.zone == "spell_trap"]) == 2
                else:
                    assert SAKURETSU_ARMOR in {
                        c.code for c in own_view.graveyards[1]}
                    assert (MST in {c.code for c in own_view.graveyards[1]}) \
                        == (mode == "mst_response")
                    assert len([c for c in own_view.field if c.controller == 1
                                and c.zone == "spell_trap"]) == (
                                    0 if mode == "mst_response" else 1)
                assert own_view.life_points == (8000, 8000)
                required = ({f"official/c{MOBIUS}.lua"} if mode != "mst_response"
                            else scripts)
                assert required <= env.engine.probe.loaded_script_sha256.keys()
                agents = (RandomAgent(215), RandomAgent(216))
                for _ in range(5000):
                    obs = env.step(agents[obs.acting_player].select_action(
                        obs, env.legal_actions()))
                    if env.is_terminal():
                        path = tmp_path / f"mobius_{mode}.json"
                        write_trajectory(path, env.trajectory())
                        assert verify_trajectory(read_trajectory(path),
                                                 ExperimentalOcgcoreEngine(root)) == len(
                                                     env.trajectory().decisions)
                        return
                pytest.fail("Mobius duel did not finish")
    pytest.fail(f"Mobius did not resolve: {mode}")
