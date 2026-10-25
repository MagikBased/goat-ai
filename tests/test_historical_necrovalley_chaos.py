"""Necrovalley blocks Chaos summon costs until the Field Spell leaves play."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

NECROVALLEY = 511002998
SORCERER = 9596126
GRACEFUL = 79571449
MST = 5318639
LIGHT = 15025844
DARK = 7359741
OTHER_LIGHT = 62651957


def _deck(path, cards):
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_necrovalley_blocks_sorcerer_until_mst_destroys_it(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (SORCERER, GRACEFUL, MST)}
    scripts.add(f"pre-errata/c{NECROVALLEY}.lua")
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card scripts not installed")
    lights = (LIGHT, OTHER_LIGHT)
    darks = (49881766, DARK)
    filler = [code for code in VANILLA_DECK if code not in (*lights, *darks)]
    filler[filler.index(69140098)] = MST
    chaos_cards = (GRACEFUL, *([SORCERER] * 3),
                   *(code for code in lights for _ in range(3)),
                   *(code for code in darks for _ in range(3)), *filler[:24])
    assert len(chaos_cards) == 40
    chaos = _deck(tmp_path / "chaos.ydk", chaos_cards)
    valley = _deck(tmp_path / "valley.ydk", (NECROVALLEY, *VANILLA_DECK[1:]))

    with GoatEnvironment(chaos, valley, seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, SORCERER, MST} <= {c.code for c in obs.hand}
        assert NECROVALLEY in {c.code for c in env.engine.probe.observation(1).hand}
        graceful = discarded = valley_active = locked = mst = targeted = summoned = False
        costs = set()
        cost_codes = set()
        for _ in range(75):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not graceful:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == GRACEFUL), None)
                graceful |= action is not None
            if graceful and not discarded and actions[0].kind == "select_cards":
                action = next((a for a in actions if len(a.parameters["cards"]) == 2
                               and any(c["code"] in lights for c in a.parameters["cards"])
                               and any(c["code"] in darks for c in a.parameters["cards"])),
                              None)
                if action is not None:
                    cost_codes = {c["code"] for c in action.parameters["cards"]}
                discarded |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not valley_active:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == NECROVALLEY), None)
                valley_active |= action is not None
            if (obs.turn == 3 and obs.acting_player == 0 and obs.phase == "main1"
                    and not locked):
                assert discarded and valley_active
                assert cost_codes <= {c.code for c in obs.graveyards[0]}
                assert any(c.code == NECROVALLEY and c.position == "faceup"
                           for c in obs.field)
                assert SORCERER in {c.code for c in obs.hand}
                assert not any(a.kind == "special_summon"
                               and a.parameters.get("code") == SORCERER for a in actions)
                locked = True
            if locked and not mst and obs.acting_player == 0:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == MST), action)
                mst |= action is not None and action.parameters.get("code") == MST
            if mst and not targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == NECROVALLEY
                               and a.parameters.get("controller") == 1), None)
                targeted |= action is not None
            if targeted and not summoned and obs.turn == 3 and obs.acting_player == 0:
                summon = next((a for a in actions if a.kind == "special_summon"
                               and a.parameters.get("code") == SORCERER), None)
                if summon is not None:
                    assert NECROVALLEY in {c.code for c in obs.graveyards[1]}
                    action = summon
                    summoned = True
            if summoned and costs != cost_codes and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               in cost_codes - costs
                               and a.parameters.get("location") == 16), None)
                if action is not None:
                    costs.add(action.parameters["code"])
            if summoned and costs == cost_codes and any(
                    c.code == SORCERER and c.controller == 0 for c in obs.field):
                assert {c.code for c in obs.banished[0]} == cost_codes
                assert {GRACEFUL, MST} <= {c.code for c in obs.graveyards[0]}
                assert NECROVALLEY in {c.code for c in obs.graveyards[1]}
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
    pytest.fail(f"Necrovalley/Chaos line stalled: {graceful}/{discarded}, "
                f"valley={valley_active}, lock={locked}, mst={mst}/{targeted}, "
                f"summon={summoned}, costs={costs}")
