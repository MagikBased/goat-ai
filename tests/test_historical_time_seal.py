"""Flip Control's Mask of Darkness / Time Seal / Tsukuyomi loop."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

TIME_SEAL = 35316708
MASK_OF_DARKNESS = 28933734
TSUKUYOMI = 34853266


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_mask_and_tsukuyomi_recycle_time_seal_for_two_skipped_draws(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (TIME_SEAL, MASK_OF_DARKNESS, TSUKUYOMI):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    deck = tmp_path / "flip_seal.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        *([TIME_SEAL] * 3), *([MASK_OF_DARKNESS] * 3),
        *([TSUKUYOMI] * 3), *VANILLA_DECK[9:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=70,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {TIME_SEAL, MASK_OF_DARKNESS, TSUKUYOMI}.issubset(
            c.code for c in obs.hand)
        mask_set = False
        seal_sets = seal_activations = mask_flips = recoveries = tsuk_summons = 0
        tsuk_targets = 0
        deck_after_t2 = deck_after_t4 = None
        saw_t4_skip = False
        for _ in range(170):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not mask_set:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == MASK_OF_DARKNESS), None)
                    mask_set |= action is not None
                if mask_set and seal_sets == 0 and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == TIME_SEAL), None)
                    seal_sets += action is not None
            if obs.turn in (2, 4) and obs.acting_player == 0 \
                    and seal_activations < obs.turn // 2:
                action = next((a for a in actions if a.kind in ("activate", "chain")
                               and a.parameters.get("code") == TIME_SEAL), None)
                if action is not None:
                    seal_activations += 1
                    if obs.turn == 2:
                        deck_after_t2 = obs.deck_counts[1]
                    else:
                        deck_after_t4 = obs.deck_counts[1]
            if obs.turn in (3, 5) and obs.acting_player == 0:
                wanted_flip = 1 if obs.turn == 3 else 2
                if mask_flips < wanted_flip:
                    action = next((a for a in actions if a.kind == "flip_summon"
                                   and a.parameters.get("code") == MASK_OF_DARKNESS), None)
                    mask_flips += action is not None
                if mask_flips > recoveries and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == TIME_SEAL and a.parameters.get("location") == 16), None)
                    recoveries += action is not None
                if recoveries >= wanted_flip and tsuk_summons < wanted_flip \
                        and action is None:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == TSUKUYOMI), None)
                    tsuk_summons += action is not None
                if tsuk_summons > tsuk_targets and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == MASK_OF_DARKNESS and a.parameters.get("controller") == 0),
                                  None)
                    tsuk_targets += action is not None
                if recoveries >= wanted_flip and seal_sets < wanted_flip + 1 \
                        and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == TIME_SEAL), None)
                    seal_sets += action is not None
            if obs.turn == 4:
                assert deck_after_t2 is not None and obs.deck_counts[1] == deck_after_t2
                saw_t4_skip = True
            if obs.turn == 6:
                assert saw_t4_skip and deck_after_t4 is not None
                assert obs.deck_counts[1] == deck_after_t4
                assert (seal_sets, seal_activations, mask_flips,
                        recoveries, tsuk_summons, tsuk_targets) == (3, 2, 2, 2, 2, 2)
                own_view = env.engine.probe.observation(0)
                assert any(c.code == TIME_SEAL and c.position == "facedown"
                           for c in own_view.field)
                assert any(c.code == TIME_SEAL and c.position == "facedown"
                           and c.controller == 0 for c in obs.field)
                assert {f"official/c{code}.lua" for code in (
                    TIME_SEAL, MASK_OF_DARKNESS, TSUKUYOMI)}.issubset(
                        env.engine.probe.loaded_script_sha256)
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
    pytest.fail("Mask of Darkness did not recycle Time Seal twice")
