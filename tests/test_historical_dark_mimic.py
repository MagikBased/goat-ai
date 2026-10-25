"""Dark Mimic LV1 Flip draw into a Level 1 Metamorphosis target."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

DARK_MIMIC_LV1 = 504700129
METAMORPHOSIS = 46411259
RESTRICT = 504700102


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_dark_mimic_flip_draw_then_metamorphosis_into_restrict(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{DARK_MIMIC_LV1}.lua",
                     f"official/c{METAMORPHOSIS}.lua", f"goat/c{RESTRICT}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    deck = tmp_path / "mimic_control.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        *([DARK_MIMIC_LV1] * 3), *([METAMORPHOSIS] * 3),
        *VANILLA_DECK[6:]))) + f"\n#extra\n{RESTRICT}\n!side\n")
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {DARK_MIMIC_LV1, METAMORPHOSIS}.issubset(c.code for c in obs.hand)
        set_mimic = opponent_summoned = flipped = draw_seen = False
        meta = tribute_paid = restrict_chosen = restrict_effect = target_chosen = False
        hidden_checked = False
        deck_before = opponent_code = opponent_hand_before = None
        for _ in range(95):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not set_mimic:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == DARK_MIMIC_LV1), None)
                set_mimic |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not opponent_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    opponent_code = action.parameters["code"]
                    opponent_summoned = True
            if obs.turn == 3 and obs.acting_player == 0:
                if not flipped:
                    action = next((a for a in actions if a.kind == "flip_summon"
                                   and a.parameters.get("code") == DARK_MIMIC_LV1), None)
                    if action is not None:
                        deck_before = obs.deck_counts[0]
                        opponent_hand_before = (
                            env.engine.probe.observation(1).opponent_hand_count)
                        flipped = True
                if flipped and not draw_seen and deck_before is not None \
                        and obs.deck_counts[0] == deck_before - 1:
                    draw_seen = True
                    opponent_view = env.engine.probe.observation(1)
                    assert opponent_view.opponent_hand_count == opponent_hand_before + 1
                    assert not opponent_view.known_opponent_hand_cards
                if draw_seen and not meta and action is None:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == METAMORPHOSIS), None)
                    meta |= action is not None
                if meta and not tribute_paid and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == DARK_MIMIC_LV1 and a.parameters.get("location") == 4),
                                  action)
                    tribute_paid |= action is not None and action.kind == "select_card"
                if tribute_paid and not restrict_chosen and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == RESTRICT), action)
                    restrict_chosen |= action is not None and action.kind == "select_card"
                if restrict_chosen and not restrict_effect:
                    action = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == RESTRICT), action)
                    restrict_effect |= action is not None and action.kind == "chain"
                if restrict_effect and not target_chosen \
                        and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == opponent_code and a.parameters.get("controller") == 1),
                                  action)
                    target_chosen |= action is not None and action.kind == "select_card"
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "select_position", "pass", "end_phase")),
                    actions[0])
            obs = env.step(action)
            if set_mimic and obs.turn == 1:
                hidden_view = env.engine.probe.observation(1)
                set_monsters = [c for c in hidden_view.field
                                if c.zone == "monster" and c.position == "facedown"]
                assert all(c.code is None for c in set_monsters)
                hidden_checked |= bool(set_monsters)
            if target_chosen and not any(c.controller == 1 and c.zone == "monster"
                                         for c in obs.field):
                assert hidden_checked and set_mimic and opponent_summoned
                assert flipped and draw_seen
                assert meta and tribute_paid and restrict_chosen and restrict_effect
                assert obs.deck_counts[0] == deck_before - 1
                assert any(c.code == DARK_MIMIC_LV1 for c in obs.graveyards[0])
                assert any(c.code == RESTRICT and c.zone == "monster"
                           for c in obs.field)
                assert any(c.code == opponent_code and c.zone == "spell_trap"
                           for c in obs.field)
                assert obs.extra_deck_counts[0] == 0
                assert {f"goat/c{DARK_MIMIC_LV1}.lua",
                        f"goat/c{RESTRICT}.lua"}.issubset(
                            env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Dark Mimic LV1 Flip draw / Metamorphosis line did not resolve")
