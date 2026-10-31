"""Narrow 2010 MR1 Dark Armed Dragon summon and Graveyard-cost probe."""

import os
import random
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.mr1_synchro_probe import (
    CARD_DESTRUCTION, DARK_ARMED_DRAGON, DEKOICHI, GRAVEKEEPERS_SPY,
    SANGAN, Mr1SynchroProbeEngine,
)
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SEED = 52
DARK_MONSTERS = (SANGAN, DEKOICHI, GRAVEKEEPERS_SPY)
MYSTICAL_ELF = 15025844


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("dark_count", (2, 3, 4),
                         ids=("two_dark", "three_dark", "four_dark"))
def test_mr1_dark_armed_dragon_requires_three_dark_and_pays_gy_cost(
        tmp_path, dark_count):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in
               (CARD_DESTRUCTION, DARK_ARMED_DRAGON, SANGAN, DEKOICHI,
                *((GRAVEKEEPERS_SPY,) if dark_count >= 3 else ()))}
    if any(not (root / "scripts" / name).is_file() for name in scripts):
        pytest.skip("required official scripts not installed")

    # Place the needed cards at known shuffled positions. MR1 player 0 opens
    # six cards; Card Destruction then redraws the five remaining hand cards.
    permutation = list(range(40))
    random.Random(SEED * 2).shuffle(permutation)
    main = list(VANILLA_DECK)
    discarded_monsters = ((SANGAN, DEKOICHI, MYSTICAL_ELF) if dark_count == 2
                          else (SANGAN, DEKOICHI, GRAVEKEEPERS_SPY)
                          + ((DEKOICHI,) if dark_count == 4 else ()))
    shuffled_slots = (34, 35, 36, 37) + ((38,) if dark_count == 4 else ()) + (29,)
    for shuffled_slot, code in zip(shuffled_slots,
                                   (CARD_DESTRUCTION, *discarded_monsters,
                                    DARK_ARMED_DRAGON), strict=True):
        main[permutation[shuffled_slot]] = code
    own_deck = tmp_path / "dark_armed.ydk"
    own_deck.write_text("#main\n" + "\n".join(map(str, main)) + "\n#extra\n!side\n")
    opponent = Path("examples/decks/vanilla_reverse.ydk")

    with GoatEnvironment(str(own_deck), str(opponent), seed=SEED,
                         engine=Mr1SynchroProbeEngine(root)) as env:
        obs = env.reset()
        assert Counter((CARD_DESTRUCTION, *discarded_monsters)) <= Counter(
            c.code for c in obs.hand)
        assert DARK_ARMED_DRAGON not in {c.code for c in obs.hand}
        discarded = opposing_summon = dad_summon = effect_used = False
        cost_paid = target_selected = checked = False
        agents = (RandomAgent(SEED), RandomAgent(SEED + 1))
        for _ in range(3000):
            if env.is_terminal():
                break
            actions = env.legal_actions()
            action = None
            if not checked:
                if obs.turn == 1 and obs.acting_player == 0 and not discarded:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == CARD_DESTRUCTION), None)
                    discarded = action is not None
                if (discarded and obs.turn == 1 and not obs.chain and
                        CARD_DESTRUCTION in {c.code for c in obs.graveyards[0]}):
                    own_view = env.engine.probe.observation(0)
                    assert DARK_ARMED_DRAGON in {c.code for c in own_view.hand}
                    assert Counter(discarded_monsters) <= Counter(
                        c.code for c in obs.graveyards[0])
                if obs.turn == 2 and obs.acting_player == 1 and not opposing_summon:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    opposing_summon = action is not None
                if obs.turn >= 3 and obs.acting_player == 0 and opposing_summon:
                    if dark_count != 3 and obs.phase == "main1":
                        assert not any(a.kind == "special_summon" and
                                       a.parameters.get("code") == DARK_ARMED_DRAGON
                                       for a in actions)
                        checked = True
                    if dark_count == 3 and not dad_summon:
                        action = next((a for a in actions if a.kind == "special_summon"
                                       and a.parameters.get("code") == DARK_ARMED_DRAGON), None)
                        dad_summon = action is not None
                    if dark_count == 3 and dad_summon and not effect_used and action is None:
                        action = next((a for a in actions if a.kind == "activate"
                                       and a.parameters.get("code") == DARK_ARMED_DRAGON), None)
                        effect_used = action is not None
                if effect_used and not cost_paid and action is None \
                        and actions[0].kind == "select_card":
                    # DAD itself is a face-up DARK monster on the field. The
                    # script scans that zone for Spirit Elimination, but with
                    # no such card active only Graveyard costs are legal.
                    assert all(a.parameters.get("location") == 16 for a in actions)
                    action = next((a for a in actions if a.parameters.get("code") == SANGAN
                                   and a.parameters.get("location") == 16), None)
                    cost_paid = action is not None
                if cost_paid and not target_selected and action is None \
                        and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("controller") == 1
                                   and a.parameters.get("location") == 4), None)
                    target_selected = action is not None
                if target_selected and not obs.chain and SANGAN in {
                        c.code for c in obs.banished[0]}:
                    assert not any(c.controller == 1 and c.zone == "monster"
                                   for c in obs.field)
                    assert obs.life_points == (8000, 8000)
                    checked = True
            if action is None:
                action = (next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
                          if not checked else
                          agents[obs.acting_player].select_action(obs, actions))
            obs = env.step(action)
        assert checked and env.is_terminal(), (
            f"DAD line did not finish: {discarded=} {opposing_summon=} "
            f"{dad_summon=} {effect_used=} {cost_paid=} {target_selected=} "
            f"{obs.turn=} {obs.phase=}")
        assert scripts <= env.engine.probe.loaded_script_sha256.keys()
        path = tmp_path / f"dark_armed_mr1_{dark_count}.json"
        write_trajectory(path, env.trajectory())
    replay = read_trajectory(path)
    assert audit_trajectory_visibility(replay)["decisions"] == len(replay.decisions)
    assert verify_trajectory(replay, Mr1SynchroProbeEngine(root)) == len(replay.decisions)
