"""Mirror Force and Sakuretsu are distinct legal attack responses."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

MIRROR = 44095762
SAKURETSU = 56120475


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chosen_trap", [MIRROR, SAKURETSU])
def test_both_attack_traps_are_legal_with_distinct_outcomes(tmp_path, chosen_trap):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (MIRROR, SAKURETSU)}
    if any(not (root / "scripts" / relative).is_file() for relative in scripts):
        pytest.skip("Mirror Force or Sakuretsu script not installed")
    defender = tmp_path / "defender.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        MIRROR, *([SAKURETSU] * 3), *VANILLA_DECK[4:])))
                        + "\n#extra\n!side\n")

    with GoatEnvironment("examples/decks/vanilla_probe.ydk", str(defender), seed=7,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert {MIRROR, SAKURETSU}.issubset(
            c.code for c in env.engine.probe.observation(1).hand)
        summons = 0
        mirror_set = sakuretsu_set = battle = attacked = trap_used = False
        for _ in range(85):
            actions = env.legal_actions()
            action = None
            if observation.acting_player == 0 and observation.turn in (1, 3) \
                    and summons < (1 if observation.turn == 1 else 2):
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                summons += action is not None
            if observation.turn == 2 and observation.acting_player == 1:
                if not mirror_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == MIRROR), None)
                    mirror_set |= action is not None
                if mirror_set and not sakuretsu_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == SAKURETSU), None)
                    sakuretsu_set |= action is not None
            if observation.turn == 3 and observation.acting_player == 0 \
                    and summons == 2 and not battle and action is None:
                action = next((a for a in actions if a.kind == "battle_phase"), None)
                battle |= action is not None
            if battle and observation.phase == "battle_start" \
                    and observation.acting_player == 0 and not attacked:
                action = next((a for a in actions if a.kind == "attack"), None)
                attacked |= action is not None
            if attacked and observation.acting_player == 1 and not trap_used:
                trap_options = {a.parameters.get("code"): a for a in actions
                                if a.kind == "chain" and a.parameters.get("code")
                                in (MIRROR, SAKURETSU)}
                if trap_options:
                    assert observation.phase == "battle_step"
                    assert set(trap_options) == {MIRROR, SAKURETSU}
                    assert sum(c.zone == "monster" and c.controller == 0
                               and c.position == "faceup" for c in observation.field) == 2
                    attacker = env.engine.probe.observation(0)
                    assert sum(c.zone == "spell_trap" and c.controller == 1
                               and c.position == "facedown" and c.code is None
                               for c in attacker.field) == 2
                    action = trap_options[chosen_trap]
                    trap_used = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if trap_used and chosen_trap in {
                    c.code for c in observation.graveyards[1]}:
                assert observation.chain == ()
                survivors = [c for c in observation.field
                             if c.zone == "monster" and c.controller == 0]
                destroyed = [c for c in observation.graveyards[0]
                             if c.code in VANILLA_DECK]
                assert len(survivors) == (0 if chosen_trap == MIRROR else 1)
                assert len(destroyed) == (2 if chosen_trap == MIRROR else 1)
                assert observation.life_points == (8000, 8000)
                assert f"official/c{chosen_trap}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail(f"Attack-trap choice stalled: summons={summons} "
                f"sets={mirror_set}/{sakuretsu_set} "
                f"battle={battle}/{attacked} trap={trap_used}")
