"""Zaborg's mandatory Tribute Summon trigger and hidden field targeting."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.decks import read_ydk
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment

ZABORG = 51945556
TRIBUTE = 15025844


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("opponent_has_monster", [False, True])
def test_zaborg_must_destroy_a_monster_including_itself(tmp_path, opponent_has_monster):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{ZABORG}.lua").is_file():
        pytest.skip("Zaborg script not installed")
    decks = Path(__file__).resolve().parent.parent / "examples/decks"
    cards = list(read_ydk(decks / "cannon_probe.ydk").main)
    cards[:2] = [TRIBUTE, ZABORG]
    own = tmp_path / "zaborg.ydk"
    own.write_text("#main\n" + "\n".join(map(str, cards)) + "\n")

    with GoatEnvironment(str(own), str(decks / "vanilla_probe.ydk"), seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert ZABORG in {card.code for card in obs.hand}
        tribute_summoned = opponent_set = zaborg_summoned = tributed = targeted = False
        opponent_code = None
        for _ in range(55):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not tribute_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == TRIBUTE), None)
                tribute_summoned |= action is not None
            if opponent_has_monster and obs.turn == 2 \
                    and obs.acting_player == 1 and not opponent_set:
                action = next((a for a in actions if a.kind == "set_monster"), None)
                opponent_set |= action is not None
                if action is not None:
                    opponent_code = action.parameters["code"]
            if obs.turn == 3 and obs.acting_player == 0 and not zaborg_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == ZABORG), None)
                zaborg_summoned |= action is not None
            if zaborg_summoned and not tributed and action is None:
                action = next((a for a in actions if a.kind == "tribute"
                               and a.parameters.get("code") == TRIBUTE), None)
                tributed |= action is not None
            if tributed and not targeted and actions[0].kind == "select_card":
                assert obs.acting_player == obs.viewer == 0
                assert obs.chain and obs.chain[0].card_code == ZABORG
                if opponent_has_monster:
                    assert any(c.controller == 1 and c.code is None
                               and c.position == "facedown" for c in obs.field)
                    action = next((a for a in actions if a.parameters.get("controller") == 1),
                                  None)
                    assert action is not None
                    assert "code" not in action.parameters
                else:
                    assert len(actions) == 1
                    action = actions[0]
                    assert action.parameters.get("code") == ZABORG
                targeted = True
            if targeted and not obs.chain:
                assert TRIBUTE in {c.code for c in obs.graveyards[0]}
                assert obs.life_points == (8000, 8000)
                if opponent_has_monster:
                    assert any(c.code == ZABORG for c in obs.field)
                    assert any(c.code == opponent_code for c in obs.graveyards[1])
                    assert not any(c.controller == 1 for c in obs.field)
                else:
                    assert ZABORG in {c.code for c in obs.graveyards[0]}
                    assert not any(c.code == ZABORG for c in obs.field)
                assert f"official/c{ZABORG}.lua" in env.engine.probe.loaded_script_sha256
                return
            if action is None:
                action = next((a for a in actions if a.kind in ("end_phase", "pass")),
                              actions[0])
            obs = env.step(action)
    pytest.fail("Zaborg's mandatory target did not resolve")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_tribute_set_zaborg_does_not_trigger_or_destroy_a_monster(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{ZABORG}.lua").is_file():
        pytest.skip("Zaborg script not installed")
    decks = Path(__file__).resolve().parent.parent / "examples/decks"
    cards = list(read_ydk(decks / "cannon_probe.ydk").main)
    cards[:2] = [TRIBUTE, ZABORG]
    own = tmp_path / "zaborg_set.ydk"
    own.write_text("#main\n" + "\n".join(map(str, cards)) + "\n")

    with GoatEnvironment(str(own), str(decks / "vanilla_probe.ydk"), seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        first_summoned = opponent_set = zaborg_set = tributed = False
        opponent_code = None
        for _ in range(55):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not first_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == TRIBUTE), None)
                first_summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not opponent_set:
                action = next((a for a in actions if a.kind == "set_monster"), None)
                opponent_set |= action is not None
                if action is not None:
                    opponent_code = action.parameters["code"]
            if obs.turn == 3 and obs.acting_player == 0 and not zaborg_set:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == ZABORG), None)
                zaborg_set |= action is not None
            if zaborg_set and not tributed and action is None:
                action = next((a for a in actions if a.kind == "tribute"
                               and a.parameters.get("code") == TRIBUTE), None)
                tributed |= action is not None
            if tributed and obs.turn == 3 and obs.phase == "main1" \
                    and any(c.code == ZABORG for c in obs.field):
                assert not obs.chain
                assert not any(a.kind == "select_card" for a in actions)
                assert any(c.code == ZABORG and c.position == "facedown"
                           and c.controller == 0 for c in obs.field)
                assert any(c.controller == 1 and c.code is None
                           and c.position == "facedown" for c in obs.field)
                opponent_view = env.engine.probe.observation(1)
                assert any(c.controller == 0 and c.code is None
                           and c.position == "facedown" for c in opponent_view.field)
                assert not any(c.code == opponent_code for c in obs.graveyards[1])
                assert TRIBUTE in {c.code for c in obs.graveyards[0]}
                assert obs.life_points == (8000, 8000)
                return
            if action is None:
                action = next((a for a in actions if a.kind in ("end_phase", "pass")),
                              actions[0])
            obs = env.step(action)
    pytest.fail("Zaborg Tribute Set did not finish")
