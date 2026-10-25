"""Chaos Sorcerer into Ryu Senshi versus common Spell and Trap cards."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

SORCERER = 9596126
GRACEFUL = 79571449
METAMORPHOSIS = 46411259
RYU_SENSHI = 49868263
TORRENTIAL = 53582587
BOOK_OF_MOON = 14087893
LIGHT = 62651957
DARK = 49881766


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("interaction", [TORRENTIAL, BOOK_OF_MOON])
def test_ryu_senshi_negates_targeted_book_or_torrential(tmp_path, interaction):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (SORCERER, GRACEFUL, METAMORPHOSIS, RYU_SENSHI, interaction):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    lights = (15025844, LIGHT)
    darks = (DARK, 7359741)
    filler = [code for code in VANILLA_DECK if code not in (*lights, *darks)]
    own_cards = (GRACEFUL, METAMORPHOSIS, *(SORCERER,) * 3,
                 *(code for code in lights for _ in range(3)),
                 *(code for code in darks for _ in range(3)), *filler[:23])
    assert len(own_cards) == 40
    own = tmp_path / "ryu_senshi.ydk"
    own.write_text("#main\n" + "\n".join(map(str, own_cards))
                   + f"\n#extra\n{RYU_SENSHI}\n!side\n")
    other = tmp_path / "opponent.ydk"
    other.write_text("#main\n" + "\n".join(map(str, (
        interaction, *VANILLA_DECK[1:])))
                     + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(other), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, METAMORPHOSIS, SORCERER, LIGHT, DARK}.issubset(
            {card.code for card in obs.hand})
        assert interaction in {card.code for card in env.engine.probe.observation(1).hand}
        graceful = discarded = summoned = trap_set = meta = False
        sorcerer_costs = []
        meta_paid = fusion_chosen = interaction_used = ryu_chained = False
        book_targeted = False
        for _ in range(95):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    graceful |= action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"] for c in
                                   a.parameters["cards"]} == {LIGHT, DARK}), None)
                    discarded |= action is not None
                if discarded and not summoned and action is None:
                    action = next((a for a in actions if a.kind == "special_summon"
                                   and a.parameters.get("code") == SORCERER), None)
                    summoned |= action is not None
            if summoned and len(sorcerer_costs) < 2 and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               in ({LIGHT, DARK} - set(sorcerer_costs))), action)
                if action is not None and action.kind == "select_card":
                    sorcerer_costs.append(action.parameters["code"])
            if (interaction == TORRENTIAL and obs.turn == 2
                    and obs.acting_player == 1 and not trap_set):
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == TORRENTIAL), None)
                trap_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0:
                if not meta:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == METAMORPHOSIS), None)
                    meta |= action is not None
                if meta and not meta_paid and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == SORCERER and a.parameters.get("location") == 4), action)
                    meta_paid |= action is not None and action.kind == "select_card"
                if meta_paid and not fusion_chosen and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == RYU_SENSHI), action)
                    fusion_chosen |= action is not None and action.kind == "select_card"
            if (fusion_chosen and interaction == TORRENTIAL
                    and obs.acting_player == 1 and not interaction_used):
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == TORRENTIAL), action)
                interaction_used |= action is not None and action.kind == "chain"
            if (fusion_chosen and interaction == BOOK_OF_MOON
                    and obs.turn == 4 and obs.acting_player == 1
                    and not interaction_used):
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == BOOK_OF_MOON), action)
                interaction_used |= action is not None and action.kind == "activate"
            if (interaction == BOOK_OF_MOON and interaction_used
                    and not book_targeted and actions[0].kind == "select_card"):
                action = next((a for a in actions if a.parameters.get("code")
                               == RYU_SENSHI), action)
                book_targeted |= action is not None and action.kind == "select_card"
            if interaction_used and obs.acting_player == 0 and not ryu_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == RYU_SENSHI), action)
                if interaction == BOOK_OF_MOON:
                    assert action is None or action.kind != "chain"
                ryu_chained |= action is not None and action.kind == "chain"
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "select_position", "pass", "end_phase")),
                    actions[0])
            obs = env.step(action)
            if interaction_used and interaction in {c.code for c in obs.graveyards[1]} \
                    and not obs.chain:
                assert {LIGHT, DARK} == set(sorcerer_costs)
                assert {c.code for c in obs.banished[0]} == {LIGHT, DARK}
                assert any(c.code == SORCERER for c in obs.graveyards[0])
                assert any(c.code == RYU_SENSHI and c.position == "faceup"
                           for c in obs.field)
                if interaction == TORRENTIAL:
                    assert ryu_chained
                    assert obs.life_points == (7000, 8000)
                else:
                    assert book_targeted and not ryu_chained
                    assert obs.life_points == (8000, 8000)
                assert f"official/c{RYU_SENSHI}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail(f"Ryu Senshi did not negate interaction {interaction}")
