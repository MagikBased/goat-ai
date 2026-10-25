"""Chaos Control's Thunder Dragon into Level 5 Dark Balter line."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

THUNDER_DRAGON = 504700054
METAMORPHOSIS = 46411259
DARK_BALTER = 80071763
RYU_SENSHI = 49868263
RESTRICT = 504700102


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_thunder_dragon_metamorphosis_can_choose_only_level_five_fusion(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{THUNDER_DRAGON}.lua",
                     f"official/c{METAMORPHOSIS}.lua",
                     f"official/c{DARK_BALTER}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    deck = tmp_path / "thunder_meta.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        *([THUNDER_DRAGON] * 3), *([METAMORPHOSIS] * 3),
        *VANILLA_DECK[6:]))) + f"\n#extra\n{DARK_BALTER}\n{RYU_SENSHI}"
        + f"\n{RESTRICT}\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {THUNDER_DRAGON, METAMORPHOSIS}.issubset(c.code for c in obs.hand)
        thunder_used = selected_thunder = searched = filler_summoned = False
        thunder_summoned = False
        filler_tributed = meta_used = thunder_tributed = balter_chosen = False
        filler_code = None
        for _ in range(85):
            actions = env.legal_actions()
            if selected_thunder and not searched and not obs.chain \
                    and sum(c.code == THUNDER_DRAGON for c in obs.hand) == 2 \
                    and THUNDER_DRAGON in {c.code for c in obs.graveyards[0]}:
                searched = True
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not thunder_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == THUNDER_DRAGON), None)
                    thunder_used |= action is not None
                if thunder_used and not selected_thunder \
                        and actions[0].kind == "cancel":
                    action = next((a for a in actions if a.kind == "select_card"
                                   and a.parameters.get("code") == THUNDER_DRAGON
                                   and a.parameters.get("location") == 1), None)
                    selected_thunder |= action is not None
                if searched and not filler_summoned and action is None:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") != THUNDER_DRAGON), None)
                    if action is not None:
                        filler_code = action.parameters["code"]
                        filler_summoned = True
            if obs.turn == 3 and obs.acting_player == 0 and filler_summoned:
                if not thunder_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == THUNDER_DRAGON), None)
                    thunder_summoned |= action is not None
                if thunder_summoned and not filler_tributed and actions[0].kind == "tribute":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == filler_code), None)
                    filler_tributed |= action is not None
                if filler_tributed and not meta_used and action is None:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == METAMORPHOSIS), None)
                    meta_used |= action is not None
                if meta_used and not thunder_tributed and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == THUNDER_DRAGON and a.parameters.get("location") == 4),
                                  None)
                    thunder_tributed |= action is not None
                if thunder_tributed and not balter_chosen and action is None \
                        and actions[0].kind == "select_card":
                    assert {a.parameters.get("code") for a in actions} == {DARK_BALTER}
                    action = next((a for a in actions if a.parameters.get("code")
                                   == DARK_BALTER), None)
                    balter_chosen |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_position", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if balter_chosen and any(c.code == DARK_BALTER for c in obs.field):
                assert (thunder_used and searched and filler_summoned
                        and thunder_summoned and filler_tributed and meta_used
                        and thunder_tributed)
                assert {THUNDER_DRAGON, METAMORPHOSIS, filler_code}.issubset(
                    {c.code for c in obs.graveyards[0]})
                assert not any(c.code == THUNDER_DRAGON for c in obs.field)
                assert {c.code for c in obs.own_extra_deck} == {RYU_SENSHI, RESTRICT}
                assert obs.life_points == (8000, 8000)
                assert {f"goat/c{THUNDER_DRAGON}.lua",
                        f"official/c{METAMORPHOSIS}.lua"}.issubset(
                            env.engine.probe.loaded_script_sha256)
                return
    progress = (thunder_used, searched, filler_summoned, thunder_summoned,
                filler_tributed, meta_used, thunder_tributed, balter_chosen)
    pytest.fail(f"Thunder Dragon / Metamorphosis did not summon Dark Balter: "
                f"{progress} at turn {obs.turn} {obs.phase}")
