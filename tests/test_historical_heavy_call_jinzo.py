"""Call of the Haunted chained to Heavy Storm: Jinzo versus a normal monster."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

GRACEFUL_CHARITY = 79571449
CALL_OF_THE_HAUNTED = 97077563
HEAVY_STORM = 19613556
JINZO = 77585513
MAD_DOG_OF_DARKNESS = 79182538


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("revived_code", [JINZO, MAD_DOG_OF_DARKNESS])
def test_call_chained_to_heavy_keeps_jinzo_but_loses_normal_monster(
        tmp_path, revived_code):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (GRACEFUL_CHARITY, CALL_OF_THE_HAUNTED, HEAVY_STORM, JINZO):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    caller = tmp_path / "caller.ydk"
    caller.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL_CHARITY, CALL_OF_THE_HAUNTED, JINZO,
        *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    storm = tmp_path / "storm.ydk"
    storm.write_text("#main\n" + "\n".join(map(str, (
        HEAVY_STORM, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(caller), str(storm), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL_CHARITY, CALL_OF_THE_HAUNTED, JINZO,
                MAD_DOG_OF_DARKNESS}.issubset(c.code for c in obs.hand)
        assert HEAVY_STORM in {
            c.code for c in env.engine.probe.observation(1).hand}
        graceful = discarded = call_set = heavy = call_chained = targeted = False
        for _ in range(70):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL_CHARITY), None)
                    graceful |= action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"] for c in
                                   a.parameters["cards"]} == {
                                       JINZO, MAD_DOG_OF_DARKNESS}), None)
                    discarded = action is not None
                if discarded and not call_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == CALL_OF_THE_HAUNTED), None)
                    call_set = action is not None
            if obs.turn == 2 and obs.acting_player == 1 and call_set and not heavy:
                assert any(c.controller == 0 and c.zone == "spell_trap"
                           and c.position == "facedown" and c.code is None
                           for c in obs.field)
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == HEAVY_STORM), None)
                heavy = action is not None
            if heavy and obs.acting_player == 0 and not call_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == CALL_OF_THE_HAUNTED), None)
                call_chained = action is not None
            if call_chained and not targeted and actions[0].kind == "select_card":
                assert [(link.index, link.card_code) for link in obs.chain] == [
                    (1, HEAVY_STORM), (2, CALL_OF_THE_HAUNTED)]
                action = next((a for a in actions if a.parameters.get("code")
                               == revived_code and a.parameters.get("location") == 16), None)
                targeted = action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "select_position", "pass", "end_phase")),
                    actions[0])
            obs = env.step(action)
            if targeted and HEAVY_STORM in {c.code for c in obs.graveyards[1]} \
                    and not obs.chain:
                assert CALL_OF_THE_HAUNTED in {c.code for c in obs.graveyards[0]}
                if revived_code == JINZO:
                    assert any(c.code == JINZO and c.controller == 0
                               and c.position == "faceup" for c in obs.field)
                    assert JINZO not in {c.code for c in obs.graveyards[0]}
                else:
                    assert not any(c.code == MAD_DOG_OF_DARKNESS for c in obs.field)
                    assert MAD_DOG_OF_DARKNESS in {
                        c.code for c in obs.graveyards[0]}
                assert not any(c.zone == "spell_trap" for c in obs.field)
                assert obs.life_points == (8000, 8000)
                assert {f"official/c{code}.lua" for code in (
                    GRACEFUL_CHARITY, CALL_OF_THE_HAUNTED, HEAVY_STORM)}.issubset(
                        env.engine.probe.loaded_script_sha256)
                if revived_code == JINZO:
                    assert f"official/c{JINZO}.lua" in (
                        env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Call/Heavy chain did not reach the comparison")
