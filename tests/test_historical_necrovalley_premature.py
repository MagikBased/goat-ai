"""Pinned Premature/Necrovalley timing, with disputed activation legality."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

GRACEFUL = 79571449
PREMATURE = 70828912
NECROVALLEY = 511002998
MST = 5318639
MYSTICAL_ELF = 15025844
MAD_DOG = 79182538


def _deck(path, cards):
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("premature_first,chain_mst", [
    (True, False), (False, False), (False, True)])
def test_pinned_necrovalley_premature_timing(
        tmp_path, premature_first, chain_mst):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (GRACEFUL, PREMATURE, MST)}
    scripts.add(f"pre-errata/c{NECROVALLEY}.lua")
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card scripts not installed")
    owner = _deck(tmp_path / "owner.ydk", (
        GRACEFUL, PREMATURE, MST, *VANILLA_DECK[3:]))
    valley = _deck(tmp_path / "valley.ydk", (
        NECROVALLEY, *VANILLA_DECK[1:]))

    with GoatEnvironment(owner, valley, seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, PREMATURE, MYSTICAL_ELF, MST} <= {c.code for c in obs.hand}
        assert NECROVALLEY in {c.code for c in env.engine.probe.observation(1).hand}
        graceful = discarded = premature = premature_targeted = valley_active = False
        locked = mst = mst_targeted = False
        for _ in range(85):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    graceful |= action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"] for c in
                                   a.parameters["cards"]} == {MYSTICAL_ELF, MAD_DOG}), None)
                    discarded |= action is not None
                if premature_first and discarded and not premature and action is None:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == PREMATURE), None)
                    premature |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not valley_active:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == NECROVALLEY), None)
                valley_active |= action is not None
            if premature and not premature_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == MYSTICAL_ELF
                               and a.parameters.get("location") == 16
                               and a.parameters.get("controller") == 0), None)
                premature_targeted |= action is not None
            if (valley_active and obs.turn == 3 and obs.acting_player == 0
                    and obs.phase == "main1" and not locked):
                if premature_first:
                    assert any(c.code == MYSTICAL_ELF and c.zone == "monster"
                               for c in obs.field)
                else:
                    assert MYSTICAL_ELF in {c.code for c in obs.graveyards[0]}
                assert any(c.code == NECROVALLEY and c.position == "faceup"
                           for c in obs.field)
                if premature_first:
                    assert obs.life_points == (7200, 8000)
                    assert any(c.code == PREMATURE and c.zone == "spell_trap"
                               for c in obs.field)
                    assert any(c.code == MYSTICAL_ELF and c.zone == "monster"
                               for c in obs.field)
                    assert scripts - {f"official/c{MST}.lua"} <= (
                        env.engine.probe.loaded_script_sha256.keys())
                    return
                assert PREMATURE in {c.code for c in obs.hand}
                assert any(a.kind == "activate" and a.parameters.get("code") == PREMATURE
                           for a in actions)
                assert obs.life_points == (8000, 8000)
                locked = True
            if (locked and not premature and obs.turn == 3
                    and obs.acting_player == 0):
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == PREMATURE), action)
                premature |= action is not None and action.parameters.get("code") == PREMATURE
            if (chain_mst and premature_targeted and not mst
                    and obs.acting_player == 0
                    and [link.card_code for link in obs.chain] == [PREMATURE]):
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == MST), action)
                mst |= action is not None and action.kind == "chain"
            if mst and not mst_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == NECROVALLEY
                               and a.parameters.get("controller") == 1), None)
                mst_targeted |= action is not None
            if (not premature_first and premature_targeted and not obs.chain
                    and (PREMATURE in {c.code for c in obs.graveyards[0]}
                         or any(c.code == MYSTICAL_ELF and c.zone == "monster"
                                for c in obs.field))):
                assert obs.life_points == (7200, 8000)
                if chain_mst:
                    assert mst_targeted
                    assert NECROVALLEY in {c.code for c in obs.graveyards[1]}
                    assert MST in {c.code for c in obs.graveyards[0]}
                    assert any(c.code == MYSTICAL_ELF and c.zone == "monster"
                               for c in obs.field)
                    assert any(c.code == PREMATURE and c.zone == "spell_trap"
                               for c in obs.field)
                    assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                else:
                    assert not mst
                    assert MYSTICAL_ELF in {c.code for c in obs.graveyards[0]}
                    assert PREMATURE in {c.code for c in obs.graveyards[0]}
                    assert any(c.code == NECROVALLEY and c.position == "faceup"
                               for c in obs.field)
                    assert not any(c.zone == "monster" for c in obs.field)
                    assert scripts - {f"official/c{MST}.lua"} <= (
                        env.engine.probe.loaded_script_sha256.keys())
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
    pytest.fail(f"Necrovalley/Premature line stalled: before={premature_first}, "
                f"discarded={discarded}, premature={premature}/{premature_targeted}, "
                f"valley={valley_active}, lock={locked}, mst={mst}/{mst_targeted}")
