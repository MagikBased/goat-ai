"""Pre-errata Ring can choose a 0-ATK Sheep Token or a normal monster."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

RING = 511000824
SCAPEGOAT = 504700123
GEMINI_ELF = 49881766
SHEEP_CODES = {73915052, 73915053, 73915054, 73915055}


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("target_token", [False, True])
def test_ring_choices_and_damage_with_scapegoat_tokens(tmp_path, target_token):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"pre-errata/c{RING}.lua", f"goat/c{SCAPEGOAT}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    ring_deck = tmp_path / "ring.ydk"
    ring_deck.write_text("#main\n" + "\n".join(map(str, (
        RING, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    goat_deck = tmp_path / "goat.ydk"
    goat_deck.write_text("#main\n" + "\n".join(map(str, (
        SCAPEGOAT, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(ring_deck), str(goat_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {RING, GEMINI_ELF}.issubset({c.code for c in obs.hand})
        assert SCAPEGOAT in {c.code for c in env.engine.probe.observation(1).hand}
        elf_summoned = ring_set = goat_used = ring_used = target_chosen = False
        for _ in range(95):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not elf_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == GEMINI_ELF), None)
                    elf_summoned |= action is not None
                if elf_summoned and not ring_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == RING), None)
                    ring_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not goat_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SCAPEGOAT), action)
                goat_used |= action is not None and action.kind == "activate"
            if obs.turn == 3 and obs.acting_player == 0 and not ring_used:
                token_codes = {c.code for c in obs.field if c.controller == 1
                               and c.zone == "monster"}
                if token_codes == SHEEP_CODES:
                    assert all(c.attack == 0 and c.position == "faceup"
                               for c in obs.field if c.code in SHEEP_CODES)
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == RING), action)
                    ring_used |= action is not None and action.kind == "activate"
            if ring_used and not target_chosen and actions[0].kind == "select_card":
                choices = {a.parameters.get("code") for a in actions}
                assert choices == SHEEP_CODES | {GEMINI_ELF}
                assert len(actions) == 5
                assert all(a.parameters.get("location") == 4 for a in actions)
                action = next((a for a in actions if (a.parameters.get("code")
                               in SHEEP_CODES) == target_token), None)
                target_chosen |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if target_chosen and RING in {c.code for c in obs.graveyards[0]}:
                assert obs.life_points == ((8000, 8000) if target_token
                                           else (6100, 6100))
                remaining_tokens = [c for c in obs.field if c.code in SHEEP_CODES]
                assert len(remaining_tokens) == (3 if target_token else 4)
                assert {c.code for c in remaining_tokens} <= SHEEP_CODES
                assert not any(c.code in SHEEP_CODES for pile in obs.graveyards
                               for c in pile)
                assert (GEMINI_ELF in {c.code for c in obs.graveyards[0]}) \
                    != target_token
                assert (GEMINI_ELF in {c.code for c in obs.field}) == target_token
                assert {f"pre-errata/c{RING}.lua", f"goat/c{SCAPEGOAT}.lua"} \
                    <= env.engine.probe.loaded_script_sha256.keys()
                return
    pytest.fail("Ring / Scapegoat choice did not resolve within 95 decisions")
