"""Removing Restrict's equipped monster does not reset its per-turn effect use."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

SCAPEGOAT = 504700123
METAMORPHOSIS = 46411259
MST = 5318639
RESTRICT = 504700102
SHEEP_CODES = {73915052, 73915053, 73915054, 73915055}


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_restrict_cannot_equip_twice_after_mst_removes_equip(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{SCAPEGOAT}.lua", f"official/c{METAMORPHOSIS}.lua",
               f"official/c{MST}.lua", f"goat/c{RESTRICT}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    deck = tmp_path / "restrict_mst.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        *((SCAPEGOAT, METAMORPHOSIS) * 3), MST, *VANILLA_DECK[7:])))
        + f"\n#extra\n{RESTRICT}\n!side\n")
    opposing_cards = [SCAPEGOAT if code == 49003308 else code
                      for code in VANILLA_DECK]
    opposing_deck = tmp_path / "scapegoat_response.ydk"
    opposing_deck.write_text("#main\n" + "\n".join(map(str, opposing_cards))
                             + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), str(opposing_deck), seed=111,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {SCAPEGOAT, METAMORPHOSIS, MST} <= {c.code for c in obs.hand}
        assert SCAPEGOAT in {c.code for c in env.engine.probe.observation(1).hand}
        goat = first_summon = opposing_goat_set = opposing_goat_chained = False
        meta = token = fusion = restrict = first_target = False
        first_equipped = mst_used = mst_target = detached = False
        second_summon = second_effect = second_target = False
        first_code = second_code = None
        for _ in range(140):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not goat:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                goat |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not first_summon:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                first_summon |= action is not None
                if first_summon:
                    first_code = action.parameters["code"]
            if obs.turn == 2 and obs.acting_player == 1 and first_summon \
                    and not opposing_goat_set and action is None:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                opposing_goat_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0:
                if not meta:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == METAMORPHOSIS), action)
                    meta |= action is not None and action.kind == "activate"
                if meta and not token and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   in SHEEP_CODES and a.parameters.get("controller") == 0),
                                  action)
                    token |= action is not None and action.kind == "select_card"
                if token and not fusion and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == RESTRICT), action)
                    fusion |= action is not None and action.kind == "select_card"
                if fusion and not restrict:
                    action = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == RESTRICT), action)
                    restrict |= action is not None and action.kind == "chain"
                if restrict and not first_target and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == first_code and a.parameters.get("controller") == 1),
                                  action)
                    first_target |= action is not None and action.kind == "select_card"
                if first_target and not obs.chain and not first_equipped:
                    first_equipped = any(c.code == first_code and c.zone == "spell_trap"
                                         and c.controller == 0 for c in obs.field)
                    if first_equipped:
                        assert opposing_goat_chained
                        assert sum(c.code in SHEEP_CODES for c in obs.field
                                   if c.controller == 1 and c.zone == "monster") == 4
                        restrict_card = next(c for c in obs.field if c.code == RESTRICT)
                        absorbed = next(c for c in obs.field if c.code == first_code
                                        and c.zone == "spell_trap")
                        assert absorbed.equipped_to == (0, restrict_card.sequence)
                if first_equipped and not mst_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == MST), action)
                    mst_used |= action is not None and action.kind == "activate"
                if mst_used and not mst_target and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == first_code and a.parameters.get("location") == 8
                                   and a.parameters.get("controller") == 0), None)
                    mst_target |= action is not None
                if mst_target and not obs.chain and not detached \
                        and MST in {c.code for c in obs.graveyards[0]}:
                    assert first_code in {c.code for c in obs.graveyards[1]}
                    assert not any(c.code == first_code and c.zone == "spell_trap"
                                   for c in obs.field)
                    assert any(c.code == RESTRICT and c.attack == 0 for c in obs.field)
                    assert sum(c.code in SHEEP_CODES for c in obs.field
                               if c.controller == 1 and c.zone == "monster") == 4
                    assert not any(a.parameters.get("code") == RESTRICT
                                   and a.kind in ("activate", "chain") for a in actions)
                    detached = True
            if first_target and obs.acting_player == 1 and not opposing_goat_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SCAPEGOAT), action)
                opposing_goat_chained |= action is not None and action.kind == "chain"
            if obs.turn == 4 and obs.acting_player == 1 and detached \
                    and not second_summon:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                second_summon |= action is not None
                if second_summon:
                    second_code = action.parameters["code"]
            if obs.turn == 5 and obs.acting_player == 0 and second_summon:
                if not second_effect:
                    action = next((a for a in actions if a.kind in ("activate", "chain")
                                   and a.parameters.get("code") == RESTRICT), action)
                    second_effect |= action is not None and action.parameters.get("code") \
                        == RESTRICT
                if second_effect and not second_target and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == second_code and a.parameters.get("controller") == 1),
                                  action)
                    second_target |= action is not None and action.kind == "select_card"
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if second_target and not obs.chain and obs.turn == 5:
                assert goat and meta and token and fusion and restrict
                assert first_summon and opposing_goat_set and opposing_goat_chained
                assert first_equipped and mst_used and mst_target and detached
                assert second_effect and second_summon
                assert second_code in {c.code for c in obs.field
                                       if c.zone == "spell_trap" and c.controller == 0}
                restrict_card = next(c for c in obs.field if c.code == RESTRICT)
                absorbed = next(c for c in obs.field if c.code == second_code
                                and c.zone == "spell_trap")
                assert absorbed.equipped_to == (0, restrict_card.sequence)
                assert first_code in {c.code for c in obs.graveyards[1]}
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                return
    pytest.fail(f"Restrict equip limit stalled: equip={first_equipped} "
                f"MST={mst_used}/{mst_target}/{detached} "
                f"second={second_summon}/{second_effect}/{second_target} turn={obs.turn}")
