"""Dark Balter negates a Normal Spell but cannot answer a Quick-Play Spell."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

THUNDER_DRAGON = 504700054
METAMORPHOSIS = 46411259
DARK_BALTER = 80071763
POT_OF_GREED = 55144522
BOOK_OF_MOON = 14087893
DEKOICHI = 87621407


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("spell", [POT_OF_GREED, BOOK_OF_MOON])
def test_dark_balter_only_negates_normal_spell_effect(tmp_path, spell):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{THUNDER_DRAGON}.lua",
                     f"official/c{METAMORPHOSIS}.lua",
                     f"official/c{DARK_BALTER}.lua",
                     f"official/c{spell}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    own = tmp_path / "balter.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        *([THUNDER_DRAGON] * 3), *([METAMORPHOSIS] * 3),
        *VANILLA_DECK[6:]))) + f"\n#extra\n{DARK_BALTER}\n!side\n")
    other = tmp_path / "spells.ydk"
    other.write_text("#main\n" + "\n".join(map(str, (
        POT_OF_GREED, *([BOOK_OF_MOON] * 3), *VANILLA_DECK[4:])))
                     + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(other), seed=72,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {THUNDER_DRAGON, METAMORPHOSIS}.issubset(c.code for c in obs.hand)
        assert {POT_OF_GREED, BOOK_OF_MOON}.issubset(
            c.code for c in env.engine.probe.observation(1).hand)
        filler_summoned = thunder_summoned = filler_tributed = False
        meta_used = thunder_tributed = balter_chosen = balter_ready = False
        spell_used = book_targeted = balter_chained = False
        filler_code = before_deck = None
        for _ in range(90):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not filler_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") != THUNDER_DRAGON), None)
                if action is not None:
                    filler_code = action.parameters["code"]
                    filler_summoned = True
            if obs.turn == 3 and obs.acting_player == 0:
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
                    action = next((a for a in actions if a.parameters.get("code")
                                   == DARK_BALTER), None)
                    balter_chosen |= action is not None
            if balter_chosen and any(c.code == DARK_BALTER for c in obs.field):
                balter_ready = True
            if balter_ready and obs.turn == 4 and obs.acting_player == 1 \
                    and not spell_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == spell), None)
                if action is not None:
                    before_deck = obs.deck_counts[1]
                    spell_used = True
            if spell_used and spell == BOOK_OF_MOON and not book_targeted \
                    and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == DARK_BALTER), None)
                book_targeted |= action is not None
            if spell_used and obs.acting_player == 0 and not balter_chained:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == DARK_BALTER), None)
                if spell == POT_OF_GREED and option is not None:
                    assert obs.chain[0].card_code == POT_OF_GREED
                    action = option
                    balter_chained = True
                elif spell == BOOK_OF_MOON:
                    assert option is None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_position", "select_card", "place", "pass", "end_phase")),
                              actions[0])
            obs = env.step(action)
            if spell_used and spell in {c.code for c in obs.graveyards[1]} \
                    and not obs.chain:
                assert balter_ready and before_deck is not None
                if spell == POT_OF_GREED:
                    assert balter_chained
                    assert obs.life_points == (7000, 8000)
                    assert obs.deck_counts[1] == before_deck
                    assert any(c.code == DARK_BALTER and c.position == "faceup"
                               for c in obs.field)
                else:
                    assert book_targeted and not balter_chained
                    assert obs.life_points == (8000, 8000)
                    assert obs.deck_counts[1] == before_deck
                    assert any(c.controller == 0 and c.zone == "monster"
                               and c.position == "facedown" and c.code is None
                               for c in obs.field)
                assert f"official/c{DARK_BALTER}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail(f"Dark Balter did not resolve against spell {spell}")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_dark_balter_battle_destruction_negates_dekoichi_flip_draw(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{THUNDER_DRAGON}.lua",
                     f"official/c{METAMORPHOSIS}.lua",
                     f"official/c{DARK_BALTER}.lua",
                     f"official/c{DEKOICHI}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    own = tmp_path / "balter.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        *([THUNDER_DRAGON] * 3), *([METAMORPHOSIS] * 3),
        *VANILLA_DECK[6:]))) + f"\n#extra\n{DARK_BALTER}\n!side\n")
    other = tmp_path / "dekoichi.ydk"
    other.write_text("#main\n" + "\n".join(map(str, (
        *([DEKOICHI] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(other), seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {THUNDER_DRAGON, METAMORPHOSIS}.issubset(c.code for c in obs.hand)
        assert DEKOICHI in {c.code for c in env.engine.probe.observation(1).hand}
        filler_summoned = deko_set = thunder_summoned = filler_tributed = False
        meta_used = thunder_tributed = balter_chosen = battle = attacked = False
        target_selected = False
        filler_code = before_deck = None
        for _ in range(100):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not filler_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") != THUNDER_DRAGON), None)
                if action is not None:
                    filler_code = action.parameters["code"]
                    filler_summoned = True
            if obs.turn == 2 and obs.acting_player == 1 and not deko_set:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == DEKOICHI), None)
                deko_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and deko_set:
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
                    action = next((a for a in actions if a.parameters.get("code")
                                   == DARK_BALTER), None)
                    balter_chosen |= action is not None
                if balter_chosen and not battle and action is None:
                    action = next((a for a in actions if a.kind == "battle_phase"), None)
                    battle |= action is not None
                if battle and obs.phase == "battle_start" and not attacked:
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == DARK_BALTER), None)
                    if action is not None:
                        assert any(c.controller == 1 and c.zone == "monster"
                                   and c.position == "facedown" and c.code is None
                                   for c in obs.field)
                        before_deck = obs.deck_counts[1]
                        attacked = True
                if attacked and not target_selected and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("controller")
                                   == 1 and a.parameters.get("location") == 4), None)
                    target_selected |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_position", "select_card", "place", "pass", "main2",
                    "end_phase")), actions[0])
            obs = env.step(action)
            if target_selected and DEKOICHI in {c.code for c in obs.graveyards[1]}:
                assert before_deck is not None
                assert obs.deck_counts[1] == before_deck
                assert obs.life_points == (8000, 8000)
                assert any(c.code == DARK_BALTER and c.position == "faceup"
                           for c in obs.field)
                assert not any(c.code == DEKOICHI for pile in obs.banished
                               for c in pile)
                assert {f"official/c{DARK_BALTER}.lua",
                        f"official/c{DEKOICHI}.lua"}.issubset(
                            env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Dark Balter did not negate Dekoichi after battle destruction")
