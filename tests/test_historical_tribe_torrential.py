"""Tribe can spend its summon priority before Torrential Tribute responds."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

TRIBE = 33184167
SERPENT = 511000818
SCAPEGOAT = 504700123
TORRENTIAL = 53582587
SHEEP_CODES = {73915052, 73915053, 73915054, 73915055}
BEAST = 16384


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("use_priority", [False, True])
def test_tribe_priority_before_opposing_torrential(tmp_path, use_priority):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"official/c{TRIBE}.lua", f"pre-errata/c{SERPENT}.lua",
                     f"goat/c{SCAPEGOAT}.lua", f"official/c{TORRENTIAL}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    attacker = tmp_path / "tribe.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        TRIBE, SERPENT, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    defender_cards = list(VANILLA_DECK)
    defender_cards[2] = SCAPEGOAT
    defender_cards[5] = TORRENTIAL
    defender = tmp_path / "goat_torrential.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, defender_cards))
                        + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {TRIBE, SERPENT}.issubset({c.code for c in obs.hand})
        assert {SCAPEGOAT, TORRENTIAL}.issubset(
            {c.code for c in env.engine.probe.observation(1).hand})
        goat_used = trap_set = tribe_summoned = priority_seen = False
        effect_used = discarded = announced = torrential_used = False
        for _ in range(100):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1:
                if not goat_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == SCAPEGOAT), None)
                    goat_used |= action is not None
                if goat_used and not trap_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == TORRENTIAL), None)
                    trap_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0:
                if trap_set and not tribe_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == TRIBE), None)
                    tribe_summoned |= action is not None
                if tribe_summoned and not priority_seen:
                    option = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == TRIBE), None)
                    if option is not None:
                        assert obs.chain == ()
                        assert sum(c.code in SHEEP_CODES for c in obs.field) == 4
                        assert any(c.controller == 1 and c.zone == "spell_trap"
                                   and c.position == "facedown" and c.code is None
                                   for c in obs.field)
                        priority_seen = True
                        action = option if use_priority else next(
                            a for a in actions if a.kind == "pass")
                        effect_used = use_priority
                if effect_used and not discarded and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == SERPENT and a.parameters.get("location") == 2), None)
                    discarded |= action is not None
                if discarded and not announced and actions[0].kind == "announce_race":
                    action = next((a for a in actions if a.parameters["race"] == BEAST), None)
                    announced |= action is not None
            if priority_seen and obs.acting_player == 1 and not torrential_used:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == TORRENTIAL), None)
                if action is not None:
                    assert (len(obs.chain) == 1) == use_priority
                    if use_priority:
                        assert obs.chain[0].card_code == TRIBE
                    torrential_used = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if torrential_used and TORRENTIAL in {c.code for c in obs.graveyards[1]}:
                assert priority_seen and trap_set and tribe_summoned
                assert obs.chain == ()
                assert not any(c.zone == "monster" for c in obs.field)
                assert TRIBE in {c.code for c in obs.graveyards[0]}
                assert SERPENT in {c.code for c in (
                    obs.graveyards[0] if use_priority else obs.hand)}
                assert SERPENT not in {c.code for c in (
                    obs.hand if use_priority else obs.graveyards[0])}
                assert discarded == announced == use_priority
                assert not any(c.code in SHEEP_CODES for pile in obs.graveyards
                               for c in pile)
                assert obs.life_points == (8000, 8000)
                assert {f"official/c{TRIBE}.lua", f"goat/c{SCAPEGOAT}.lua",
                        f"official/c{TORRENTIAL}.lua"} \
                    <= env.engine.probe.loaded_script_sha256.keys()
                if use_priority:
                    assert f"pre-errata/c{SERPENT}.lua" in \
                        env.engine.probe.loaded_script_sha256
                return
    pytest.fail("Tribe summon priority / Torrential did not resolve")
