"""Tribe-Infecting Virus can declare Beast to clear Scapegoat tokens."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

TRIBE = 33184167
SERPENT = 511000818
SCAPEGOAT = 504700123
SHEEP_CODES = {73915052, 73915053, 73915054, 73915055}
AQUA = 64
BEAST = 16384


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("declare_beast", [False, True])
def test_tribe_declaration_destroys_only_the_chosen_type(tmp_path, declare_beast):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"official/c{TRIBE}.lua", f"pre-errata/c{SERPENT}.lua",
                     f"goat/c{SCAPEGOAT}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    attacker = tmp_path / "tribe.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        TRIBE, SERPENT, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    defender = tmp_path / "scapegoat.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        *VANILLA_DECK[:2], SCAPEGOAT, *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {TRIBE, SERPENT}.issubset({c.code for c in obs.hand})
        assert SCAPEGOAT in {c.code for c in env.engine.probe.observation(1).hand}
        tribe_summoned = goat_used = tribe_used = serpent_discarded = announced = False
        for _ in range(85):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not tribe_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == TRIBE), None)
                tribe_summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not goat_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                goat_used |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not tribe_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == TRIBE), action)
                tribe_used |= action is not None and action.kind == "activate"
            if tribe_used and not serpent_discarded and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == SERPENT and a.parameters.get("location") == 2), None)
                serpent_discarded |= action is not None
            if serpent_discarded and not announced and actions[0].kind == "announce_race":
                assert {a.parameters["race"] for a in actions} == {AQUA, BEAST}
                assert SERPENT in {c.code for c in obs.graveyards[0]}
                assert sum(c.code in SHEEP_CODES for c in obs.field) == 4
                action = next(a for a in actions if a.parameters["race"] == (
                    BEAST if declare_beast else AQUA))
                announced = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if announced and obs.turn == 3 and obs.phase == "main1" \
                    and obs.acting_player == 0 and not obs.chain:
                remaining = [c for c in obs.field if c.zone == "monster"]
                tokens = [c for c in remaining if c.code in SHEEP_CODES]
                assert len(tokens) == (0 if declare_beast else 4)
                assert (TRIBE in {c.code for c in remaining}) == declare_beast
                assert (TRIBE in {c.code for c in obs.graveyards[0]}) != declare_beast
                assert not any(c.code in SHEEP_CODES for pile in obs.graveyards
                               for c in pile)
                assert SERPENT in {c.code for c in obs.graveyards[0]}
                assert obs.life_points == (8000, 8000)
                assert {f"official/c{TRIBE}.lua", f"pre-errata/c{SERPENT}.lua",
                        f"goat/c{SCAPEGOAT}.lua"} \
                    <= env.engine.probe.loaded_script_sha256.keys()
                return
    pytest.fail("Tribe / Scapegoat effect did not resolve within 85 decisions")
