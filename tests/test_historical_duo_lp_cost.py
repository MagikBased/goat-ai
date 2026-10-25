"""A staple's fixed LP cost cannot consume all of its controller's LP."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

DUO = 44763025
WALL = 17078030
PATCHED_UTILITY_SHA256 = "04c4555a7491a6fa958688f270e28a3212255cfbc23e390040cfb18969936b24"


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_duo_is_not_legal_when_its_1000_lp_cost_would_leave_zero(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"official/c{DUO}.lua", f"official/c{WALL}.lua")
    for script in scripts:
        if not (root / "scripts" / script).is_file():
            pytest.skip(f"script {script} not installed")
    deck = tmp_path / "duo_wall.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        WALL, DUO, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {WALL, DUO} <= {c.code for c in obs.hand}
        wall_set = wall_activated = cost_chosen = False
        for _ in range(70):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and obs.phase == "main1" \
                    and any(a.kind == "set_spell_trap" for a in actions):
                assert obs.life_points[0] == 8000
                assert obs.opponent_hand_count > 0
                assert any(a.kind == "activate" and a.parameters.get("code") == DUO
                           for a in actions)
            if obs.turn == 1 and obs.acting_player == 0 and not wall_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == WALL), None)
                wall_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 0 and wall_set \
                    and not wall_activated:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == WALL), None)
                wall_activated |= action is not None
            if wall_activated and not cost_chosen and actions[0].kind == "announce_number":
                action = next((a for a in actions if a.parameters.get("number") == 7000), None)
                cost_chosen |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 \
                    and obs.phase == "main1" and cost_chosen \
                    and any(a.kind == "end_phase" for a in actions):
                assert obs.life_points[0] == 1000
                assert DUO in {c.code for c in obs.hand}
                assert obs.opponent_hand_count > 0
                assert not any(a.kind == "activate" and a.parameters.get("code") == DUO
                               for a in actions)
                assert set(scripts).issubset(env.engine.probe.loaded_script_sha256)
                assert env.engine.probe.loaded_script_sha256["utility.lua"] \
                    == PATCHED_UTILITY_SHA256
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
    pytest.fail("Wall did not leave Duo's controller at 1000 LP by turn 3")
