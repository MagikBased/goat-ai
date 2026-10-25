"""BLS attacks through a Scapegoat response to a direct attack."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

BLS = 504700118
GRACEFUL = 79571449
SCAPEGOAT = 504700123
LIGHT = 15025844
DARK = 7359741
TOKEN_CODES = {73915052, 73915053, 73915054, 73915055}
OTHER_ATTACKER = 49881766


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("replay_choice", ["bls", "other_attacker_first"])
def test_bls_retargets_sheep_after_scapegoat_interrupts_direct_attack(
        tmp_path, replay_choice):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{BLS}.lua", f"official/c{GRACEFUL}.lua",
                     f"goat/c{SCAPEGOAT}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    lights = (LIGHT, 62651957)
    darks = (49881766, DARK)
    filler = [code for code in VANILLA_DECK if code not in (*lights, *darks)]
    attacker = tmp_path / "bls.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL, BLS,
        *(code for code in lights for _ in range(3)),
        *(code for code in darks for _ in range(3)), *filler[:26])))
        + "\n#extra\n!side\n")
    defender = tmp_path / "scapegoat.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        SCAPEGOAT, SCAPEGOAT, SCAPEGOAT, *VANILLA_DECK[3:])))
        + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        graceful = discarded = summoned = goat_set = first_attack = False
        goat_chained = replay_chosen = second_attack = trigger_accepted = False
        other_summoned = other_attack = False
        costs = []
        for _ in range(120):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not graceful:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == GRACEFUL), None)
                graceful |= action is not None
            if graceful and not discarded and actions[0].kind == "select_cards":
                action = next((a for a in actions if {c["code"] for c in a.parameters["cards"]}
                               == {LIGHT, DARK}), None)
                discarded |= action is not None
            if action is None and discarded and observation.turn == 1 \
                    and observation.acting_player == 0 \
                    and not summoned:
                assert {c.code for c in observation.graveyards[0]} == {
                    LIGHT, DARK, GRACEFUL}
                action = next((a for a in actions if a.kind == "special_summon"
                               and a.parameters.get("code") == BLS), None)
                summoned |= action is not None
            if summoned and len(costs) < 2 and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               in ({LIGHT, DARK} - set(costs))), action)
                if action is not None:
                    costs.append(action.parameters["code"])
            if replay_choice == "other_attacker_first" and len(costs) == 2 \
                    and observation.turn == 1 and observation.acting_player == 0 \
                    and not other_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == OTHER_ATTACKER), action)
                other_summoned |= action is not None and action.kind == "normal_summon"
            if observation.turn == 2 and observation.acting_player == 1 and not goat_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                goat_set |= action is not None
            if observation.turn == 3 and observation.acting_player == 0 \
                    and observation.phase == "main1":
                action = next((a for a in actions if a.kind == "battle_phase"), action)
            if observation.turn == 3 and observation.acting_player == 0 \
                    and observation.phase == "battle_start" and not first_attack:
                assert not any(c.controller == 1 and c.zone == "monster"
                               for c in observation.field)
                action = next((a for a in actions if a.kind == "attack"
                               and a.parameters.get("code") == BLS), None)
                first_attack |= action is not None
            if first_attack and observation.acting_player == 1 and not goat_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SCAPEGOAT), action)
                goat_chained |= action is not None and action.kind == "chain"
            token_count = sum(c.code in TOKEN_CODES for c in observation.field)
            if replay_choice == "other_attacker_first" and goat_chained \
                    and token_count == 4 and not other_attack:
                action = next((a for a in actions if a.kind == "attack"
                               and a.parameters.get("code") == OTHER_ATTACKER), action)
                other_attack |= action is not None and action.kind == "attack"
            if goat_chained and not replay_chosen and (
                    (replay_choice == "bls" and token_count == 4) or
                    (replay_choice == "other_attacker_first" and other_attack
                     and token_count == 3)):
                action = next((a for a in actions if a.kind == "attack"
                               and a.parameters.get("code") == BLS), action)
                replay_chosen |= action is not None and action.kind == "attack"
            if goat_chained and not trigger_accepted and any(
                    a.kind == "yes" and a.parameters.get("code") == BLS for a in actions):
                action = next(a for a in actions if a.kind == "yes"
                              and a.parameters.get("code") == BLS)
                trigger_accepted = True
            if trigger_accepted and not second_attack and observation.phase == "battle_step":
                action = next((a for a in actions if a.kind == "attack"
                               and a.parameters.get("code") == BLS), action)
                second_attack |= action is not None and action.kind == "attack"
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "select_position", "pass", "end_phase")),
                    actions[0])
            observation = env.step(action)
            expected_tokens = 2 if replay_choice == "bls" else 1
            if second_attack and observation.phase == "battle_step" and sum(
                    c.code in TOKEN_CODES for c in observation.field) == expected_tokens:
                assert all((graceful, discarded, summoned, goat_set, first_attack,
                            goat_chained, replay_chosen, trigger_accepted))
                assert replay_choice == "bls" or (other_summoned and other_attack)
                assert observation.life_points == (8000, 8000)
                assert not any(c.code in TOKEN_CODES for pile in observation.graveyards
                               for c in pile)
                assert not any(a.kind == "attack" and a.parameters.get("code") == BLS
                               for a in env.legal_actions())
                assert f"goat/c{BLS}.lua" in env.engine.probe.loaded_script_sha256
                assert f"goat/c{SCAPEGOAT}.lua" in env.engine.probe.loaded_script_sha256
                return
    pytest.fail("BLS / Scapegoat battle line did not complete")
