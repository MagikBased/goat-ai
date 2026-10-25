"""GOAT Thousand-Eyes Restrict can equip an opponent's Sheep Token."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.ocgcore_probe import UPSTREAM_GOAT_RESTRICT_SHA256
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

SCAPEGOAT = 504700123
METAMORPHOSIS = 46411259
RESTRICT = 504700102
SHEEP_CODES = {73915052, 73915053, 73915054, 73915055}


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("battle_case", ["equip_only", "attack_position", "set_defender"])
def test_restrict_equips_opponents_sheep_as_token_equip(tmp_path, battle_case):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{SCAPEGOAT}.lua", f"official/c{METAMORPHOSIS}.lua",
                     f"goat/c{RESTRICT}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    attacker = tmp_path / "restrict.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        *((SCAPEGOAT, METAMORPHOSIS) * 3), *VANILLA_DECK[6:])))
        + f"\n#extra\n{RESTRICT}\n!side\n")
    defender = tmp_path / "goat.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        SCAPEGOAT, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {SCAPEGOAT, METAMORPHOSIS}.issubset({c.code for c in obs.hand})
        assert SCAPEGOAT in {c.code for c in env.engine.probe.observation(1).hand}
        own_goat = other_goat = meta = own_token = fusion = restrict = False
        target = equip_checked = opponent_summoned = battle = attacked = False
        attack_target_chosen = False
        target_code = attack_target_code = attack_target_atk = None
        for _ in range(145):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not own_goat:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                own_goat |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not other_goat:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                other_goat |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not meta:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == METAMORPHOSIS), action)
                meta |= action is not None and action.kind == "activate"
            if meta and not own_token and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               in SHEEP_CODES and a.parameters.get("controller") == 0),
                              action)
                own_token |= action is not None and action.kind == "select_card"
            if own_token and not fusion and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == RESTRICT), action)
                fusion |= action is not None and action.kind == "select_card"
            if fusion and not restrict:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == RESTRICT), action)
                restrict |= action is not None and action.kind == "chain"
            if restrict and not target and actions[0].kind == "select_card":
                options = [a for a in actions if a.parameters.get("controller") == 1
                           and a.parameters.get("code") in SHEEP_CODES]
                assert len(options) == 4
                action = options[0]
                target_code = action.parameters["code"]
                target = True
            if battle_case != "equip_only" and equip_checked:
                if obs.turn == 4 and obs.acting_player == 1 and not opponent_summoned:
                    summon_kind = ("set_monster" if battle_case == "set_defender"
                                   else "normal_summon")
                    action = next((a for a in actions if a.kind == summon_kind), action)
                    if action is not None and action.kind == summon_kind:
                        attack_target_code = action.parameters["code"]
                        opponent_summoned = True
                if obs.turn == 5 and obs.acting_player == 0 and opponent_summoned:
                    if obs.phase == "main1" and not battle:
                        if battle_case == "attack_position":
                            attack_target_atk = next(c.attack for c in obs.field
                                                     if c.code == attack_target_code
                                                     and c.controller == 1)
                            assert attack_target_atk > 0
                        else:
                            assert all(c.code != attack_target_code for c in obs.field
                                       if c.controller == 1)
                        action = next((a for a in actions if a.kind == "battle_phase"),
                                      action)
                        battle |= action is not None and action.kind == "battle_phase"
                    elif obs.phase == "battle_start" and not attacked:
                        action = next((a for a in actions if a.kind == "attack"
                                       and a.parameters.get("code") == RESTRICT), action)
                        attacked |= action is not None and action.kind == "attack"
                    elif attacked and not attack_target_chosen \
                            and actions[0].kind == "select_card":
                        action = next((a for a in actions if a.parameters.get("controller") == 1
                                       and (a.parameters.get("code") == attack_target_code
                                            if battle_case == "attack_position"
                                            else a.parameters.get("code") is None)), action)
                        attack_target_chosen |= action is not None \
                            and action.kind == "select_card"
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if target and not equip_checked and obs.turn == 3 and obs.phase == "main1" \
                    and obs.acting_player == 0 and not obs.chain:
                assert own_goat and other_goat and meta and own_token and fusion
                assert sum(c.code in SHEEP_CODES and c.controller == 0
                           and c.zone == "monster" for c in obs.field) == 3
                assert sum(c.code in SHEEP_CODES and c.controller == 1
                           and c.zone == "monster" for c in obs.field) == 3
                restrict_card = next(c for c in obs.field if c.code == RESTRICT)
                assert restrict_card.controller == 0 and restrict_card.attack == 0
                assert any(c.code == target_code and c.zone == "spell_trap"
                           and c.controller == 0 for c in obs.field)
                assert not any(c.code in SHEEP_CODES for pile in obs.graveyards
                               for c in pile)
                assert obs.life_points == (8000, 8000)
                assert {f"goat/c{SCAPEGOAT}.lua", f"official/c{METAMORPHOSIS}.lua",
                        f"goat/c{RESTRICT}.lua"} \
                    <= env.engine.probe.loaded_script_sha256.keys()
                assert env.engine.probe.loaded_script_sha256[f"goat/c{RESTRICT}.lua"] \
                    != UPSTREAM_GOAT_RESTRICT_SHA256
                equip_checked = True
                if battle_case == "equip_only":
                    return
            if battle_case != "equip_only" and attack_target_chosen \
                    and obs.turn == 5 and obs.phase == "battle_step" \
                    and obs.life_points[0] < 8000:
                assert equip_checked and opponent_summoned and battle and attacked
                if battle_case == "set_defender":
                    defender = next(c for c in obs.field if c.code == attack_target_code
                                    and c.controller == 1)
                    assert defender.defense is not None and defender.defense > 0
                    expected_damage = defender.defense
                    assert defender.position == "faceup" and defender.orientation == "defense"
                else:
                    expected_damage = attack_target_atk
                assert obs.life_points == (8000 - expected_damage,
                                           8000 - expected_damage)
                assert any(c.code == RESTRICT and c.zone == "monster"
                           and c.controller == 0 for c in obs.field)
                token_equipped = any(c.code == target_code and c.zone == "spell_trap"
                                     for c in obs.field)
                assert token_equipped == (battle_case == "set_defender")
                assert not any(c.code in SHEEP_CODES for pile in obs.graveyards
                               for c in pile)
                assert any(c.code == attack_target_code and c.zone == "monster"
                           and c.controller == 1 for c in obs.field)
                return
    pytest.fail("Restrict token-equip or battle substitution did not resolve")
