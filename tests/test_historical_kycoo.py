"""Kycoo's Chaos lock and post-damage Graveyard banish choice."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

KYCOO = 88240808
SORCERER = 9596126
GRACEFUL = 79571449
BOOK = 14087893
SNATCH = 45986603
NOBLEMAN = 504700116  # GOAT variant
LIGHT = 15025844  # Mystical Elf
DARK = 7359741  # Mechanicalchaser
OTHER_LIGHT = 62651957  # X-Head Cannon
GEMINI_ELF = 69140098
GIANT_SOLDIER = 13039848


def _deck(path, cards):
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


def _kycoo_deck(tmp_path):
    return _deck(tmp_path / "kycoo.ydk", (*([KYCOO] * 3), *VANILLA_DECK[3:]))


def _chaos_deck(tmp_path, *, book=False, snatch=False):
    lights = (LIGHT, OTHER_LIGHT)
    darks = (49881766, DARK)
    filler = [code for code in VANILLA_DECK if code not in (*lights, *darks)]
    if book:
        filler = [BOOK if code == 69140098 else code for code in filler]
    if snatch:
        filler[filler.index(GEMINI_ELF)] = SNATCH
    cards = (GRACEFUL, *([SORCERER] * 3),
             *(code for code in lights for _ in range(3)),
             *(code for code in darks for _ in range(3)), *filler[:24])
    assert len(cards) == 40
    return _deck(tmp_path / "chaos.ydk", cards)


def _require_scripts(root, *codes):
    for code in codes:
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_kycoo_blocks_chaos_graveyard_cost_until_book_sets_it(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    _require_scripts(root, KYCOO, SORCERER, GRACEFUL, BOOK)
    with GoatEnvironment(_chaos_deck(tmp_path, book=True), _kycoo_deck(tmp_path),
                         seed=18, engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        graceful = discarded = kycoo = book = targeted = summon_committed = False
        lock_checked = False
        costs = set()
        for _ in range(55):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not graceful:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == GRACEFUL), None)
                graceful |= action is not None
            if graceful and not discarded and actions[0].kind == "select_cards":
                action = next((a for a in actions if {c["code"] for c in a.parameters["cards"]}
                               == {LIGHT, DARK}), None)
                assert action is not None
                discarded = True
            if observation.turn == 2 and observation.acting_player == 1 and not kycoo:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == KYCOO), None)
                kycoo |= action is not None
            if (observation.turn == 3 and observation.acting_player == 0
                    and observation.phase == "main1" and not lock_checked):
                assert discarded and kycoo
                assert {LIGHT, DARK}.issubset({c.code for c in observation.graveyards[0]})
                assert any(c.code == KYCOO and c.position == "faceup"
                           for c in observation.field)
                assert any(c.code == SORCERER for c in observation.hand)
                assert not any(a.kind == "special_summon"
                               and a.parameters.get("code") == SORCERER for a in actions)
                lock_checked = True
            if lock_checked and not book and observation.acting_player == 0:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == BOOK), action)
                book |= action is not None and action.kind == "activate"
            if book and not targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == KYCOO
                               and a.parameters.get("controller") == 1), action)
                targeted |= action is not None and action.kind == "select_card"
            if targeted and not summon_committed and observation.turn == 3 \
                    and observation.acting_player == 0:
                summon = next((a for a in actions if a.kind == "special_summon"
                               and a.parameters.get("code") == SORCERER), None)
                if summon is not None:
                    assert any(c.code is None and c.position == "facedown"
                               and c.controller == 1 for c in observation.field)
                    action = summon
                    summon_committed = True
            if summon_committed and costs != {LIGHT, DARK} \
                    and actions[0].kind == "select_card":
                choice = next((a for a in actions if a.parameters.get("code")
                               in {LIGHT, DARK} - costs
                               and a.parameters.get("location") == 16), None)
                if choice is not None:
                    action = choice
                    costs.add(choice.parameters["code"])
            if summon_committed and {c.code for c in observation.banished[0]} \
                    == {LIGHT, DARK} and any(c.code == SORCERER for c in observation.field):
                assert costs == {LIGHT, DARK}
                assert any(c.code is None and c.position == "facedown"
                           and c.controller == 1 for c in observation.field)
                assert f"official/c{KYCOO}.lua" in env.engine.probe.loaded_script_sha256
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
    pytest.fail("Kycoo's Chaos lock did not release into a completed Sorcerer summon")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_snatch_steal_reverses_kycoo_chaos_lock(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    _require_scripts(root, KYCOO, SORCERER, GRACEFUL, SNATCH)
    with GoatEnvironment(_chaos_deck(tmp_path, snatch=True), _kycoo_deck(tmp_path),
                         seed=18, engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert {GRACEFUL, SNATCH, SORCERER}.issubset(c.code for c in observation.hand)
        graceful = discarded = kycoo = locked = snatched = targeted = summoned = checked = False
        costs = set()
        agents = (RandomAgent(18), RandomAgent(19))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / "kycoo_snatch.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not graceful:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == GRACEFUL), None)
                graceful |= action is not None
            if graceful and not discarded and actions[0].kind == "select_cards":
                action = next((a for a in actions if {c["code"] for c in a.parameters["cards"]}
                               == {LIGHT, DARK}), None)
                assert action is not None
                discarded = True
            if observation.turn == 2 and observation.acting_player == 1 and not kycoo:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == KYCOO), None)
                kycoo |= action is not None
            if observation.turn == 3 and observation.acting_player == 0 \
                    and observation.phase == "main1" and not locked:
                assert discarded and kycoo
                assert {LIGHT, DARK}.issubset(c.code for c in observation.graveyards[0])
                assert not any(a.kind == "special_summon"
                               and a.parameters.get("code") == SORCERER for a in actions)
                locked = True
            if locked and not snatched and observation.acting_player == 0:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SNATCH), action)
                snatched |= action is not None and action.kind == "activate"
            if snatched and not targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == KYCOO
                               and a.parameters.get("controller") == 1), action)
                targeted |= action is not None and action.kind == "select_card"
            if targeted and not summoned and observation.acting_player == 0:
                stolen = next((c for c in observation.field if c.code == KYCOO
                               and c.controller == 0), None)
                if stolen is not None:
                    assert any(c.code == SNATCH for c in observation.field)
                    summon = next((a for a in actions if a.kind == "special_summon"
                                   and a.parameters.get("code") == SORCERER), None)
                    if summon is not None:
                        action = summon
                        summoned = True
            if summoned and costs != {LIGHT, DARK} and actions[0].kind == "select_card":
                choice = next((a for a in actions if a.parameters.get("code")
                               in {LIGHT, DARK} - costs
                               and a.parameters.get("location") == 16), None)
                if choice is not None:
                    action = choice
                    costs.add(choice.parameters["code"])
            if action is None and not summoned:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[observation.acting_player].select_action(
                    observation, actions)
            observation = env.step(action)
            if summoned and costs == {LIGHT, DARK} and not checked and any(
                    c.code == SORCERER and c.controller == 0 for c in observation.field):
                assert any(c.code == KYCOO and c.controller == 0
                           for c in observation.field)
                assert {LIGHT, DARK}.issubset(c.code for c in observation.banished[0])
                assert {f"official/c{code}.lua" for code in (KYCOO, SNATCH)} <= (
                    env.engine.probe.loaded_script_sha256.keys())
                checked = True
    pytest.fail("Snatch Steal did not reverse Kycoo's Chaos lock")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_kycoo_direct_damage_offers_one_or_two_graveyard_monsters_to_banish(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    _require_scripts(root, KYCOO, GRACEFUL)
    with GoatEnvironment(_kycoo_deck(tmp_path), _chaos_deck(tmp_path), seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        summoned = graceful = discarded = battle = attacked = selected = False
        for _ in range(55):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == KYCOO), None)
                summoned |= action is not None
            if observation.turn == 2 and observation.acting_player == 1 and not graceful:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == GRACEFUL), None)
                graceful |= action is not None
            if graceful and not discarded and actions[0].kind == "select_cards":
                action = next((a for a in actions if {c["code"] for c in a.parameters["cards"]}
                               == {OTHER_LIGHT, DARK}), None)
                assert action is not None
                discarded = True
            if (discarded and observation.turn == 3 and observation.acting_player == 0
                    and observation.phase == "main1" and not battle):
                assert {OTHER_LIGHT, DARK}.issubset(
                    {c.code for c in observation.graveyards[1]})
                action = next((a for a in actions if a.kind == "battle_phase"), None)
                battle |= action is not None
            if (battle and observation.turn == 3 and observation.acting_player == 0
                    and observation.phase == "battle_start" and not attacked):
                action = next((a for a in actions if a.kind == "attack"
                               and a.parameters.get("code") == KYCOO), None)
                attacked |= action is not None
            if attacked and any(a.kind == "yes" for a in actions):
                assert observation.life_points == (8000, 6200)
                action = next(a for a in actions if a.kind == "yes")
            if attacked and not selected and observation.turn == 3 \
                    and actions[0].kind in ("select_card", "select_cards"):
                assert observation.acting_player == observation.viewer == 0
                assert observation.life_points == (8000, 6200)
                choices = [a for a in actions if a.kind == "select_cards"]
                assert len(choices) == 1
                selected = choices[0].parameters["cards"]
                assert {c["code"] for c in selected} == {OTHER_LIGHT, DARK}
                assert all(c["controller"] == 1 and c["location"] == 16 for c in selected)
                assert {a.parameters["code"] for a in actions if a.kind == "select_card"} \
                    == {OTHER_LIGHT, DARK}
                action = choices[0]
                selected = True
            if selected and {c.code for c in observation.banished[1]} \
                    == {OTHER_LIGHT, DARK}:
                assert {c.code for c in observation.banished[1]} == {OTHER_LIGHT, DARK}
                assert {c.code for c in observation.graveyards[1]} == {GRACEFUL}
                assert f"official/c{KYCOO}.lua" in env.engine.probe.loaded_script_sha256
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
    pytest.fail("Kycoo did not offer its two-monster battle-damage choice")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_kycoo_cannot_target_monster_destroyed_by_its_battle(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    _require_scripts(root, KYCOO, GRACEFUL)
    with GoatEnvironment(_kycoo_deck(tmp_path), _chaos_deck(tmp_path), seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert {GRACEFUL, OTHER_LIGHT, GEMINI_ELF, GIANT_SOLDIER}.issubset(
            c.code for c in env.engine.probe.observation(1).hand)
        summoned = graceful = discarded = soldier_summoned = False
        battle = attacked = target_chosen = trigger_accepted = banish_chosen = False
        for _ in range(70):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 \
                    and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == KYCOO), None)
                summoned |= action is not None
            if observation.turn == 2 and observation.acting_player == 1:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    graceful |= action is not None
                if graceful and not discarded:
                    action = next((a for a in actions if a.kind == "select_cards"
                                   and {c["code"] for c in a.parameters["cards"]}
                                   == {OTHER_LIGHT, GEMINI_ELF}), action)
                    discarded |= action is not None and action.kind == "select_cards"
                if discarded and not soldier_summoned and action is None:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == GIANT_SOLDIER), None)
                    soldier_summoned |= action is not None
            if observation.turn == 3 and observation.acting_player == 0:
                if observation.phase == "main1" and not battle:
                    assert soldier_summoned
                    assert {OTHER_LIGHT, GEMINI_ELF}.issubset(
                        c.code for c in observation.graveyards[1])
                    action = next((a for a in actions if a.kind == "battle_phase"), None)
                    battle |= action is not None
                if observation.phase == "battle_start" and not attacked:
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == KYCOO), None)
                    attacked |= action is not None
                if attacked and not target_chosen and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == GIANT_SOLDIER and
                                   a.parameters.get("controller") == 1), None)
                    target_chosen |= action is not None
                if target_chosen and not trigger_accepted and any(
                        a.kind == "yes" and a.parameters.get("code") == KYCOO
                        for a in actions):
                    assert observation.life_points == (8000, 7500)
                    action = next(a for a in actions if a.kind == "yes"
                                  and a.parameters.get("code") == KYCOO)
                    trigger_accepted = True
                if trigger_accepted and not banish_chosen \
                        and actions[0].kind in ("select_card", "select_cards"):
                    assert observation.phase == "damage_step"
                    assert GIANT_SOLDIER not in {c.code
                                                 for c in observation.graveyards[1]}
                    assert {a.parameters["code"] for a in actions
                            if a.kind == "select_card"} == {OTHER_LIGHT, GEMINI_ELF}
                    action = next((a for a in actions if a.kind == "select_cards"
                                   and {c["code"] for c in a.parameters["cards"]}
                                   == {OTHER_LIGHT, GEMINI_ELF}), None)
                    banish_chosen |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_cards", "select_card", "place", "pass", "end_phase")),
                    actions[0])
            observation = env.step(action)
            if banish_chosen and observation.phase == "battle_step" \
                    and not observation.chain:
                assert {c.code for c in observation.banished[1]} == {
                    OTHER_LIGHT, GEMINI_ELF}
                assert {c.code for c in observation.graveyards[1]} == {
                    GRACEFUL, GIANT_SOLDIER}
                assert observation.life_points == (8000, 7500)
                assert f"official/c{KYCOO}.lua" in env.engine.probe.loaded_script_sha256
                return
    pytest.fail("Kycoo's battle target exclusion did not finish")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_kycoo_does_not_block_nobleman_banishing_a_field_monster(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    _require_scripts(root, KYCOO)
    if not (root / f"scripts/goat/c{NOBLEMAN}.lua").is_file():
        pytest.skip("GOAT Nobleman script not installed")
    nobleman_deck = _deck(tmp_path / "nobleman.ydk", (NOBLEMAN, *VANILLA_DECK[1:]))
    with GoatEnvironment(nobleman_deck, _kycoo_deck(tmp_path), seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        monster_set = kycoo_summoned = nobleman_activated = target_selected = False
        set_code = None
        for _ in range(45):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 \
                    and not monster_set:
                action = next((a for a in actions if a.kind == "set_monster"), None)
                if action is not None:
                    set_code = action.parameters["code"]
                    monster_set = True
            if observation.turn == 2 and observation.acting_player == 1 \
                    and not kycoo_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == KYCOO), None)
                kycoo_summoned |= action is not None
            if observation.turn == 3 and observation.acting_player == 0 \
                    and observation.phase == "main1" and not nobleman_activated:
                assert monster_set and kycoo_summoned
                assert any(c.code == KYCOO and c.position == "faceup"
                           for c in observation.field)
                opposing_view = env.engine.probe.observation(1)
                assert any(c.code is None and c.controller == 0
                           and c.position == "facedown" for c in opposing_view.field)
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == NOBLEMAN), None)
                assert action is not None
                nobleman_activated = True
            if nobleman_activated and not target_selected \
                    and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 0
                               and a.parameters.get("code") == set_code), None)
                assert action is not None
                target_selected = True
            if target_selected and any(c.code == set_code for c in observation.banished[0]):
                assert not any(c.code == set_code for c in observation.graveyards[0])
                assert any(c.code == KYCOO and c.position == "faceup"
                           for c in observation.field)
                assert f"goat/c{NOBLEMAN}.lua" in env.engine.probe.loaded_script_sha256
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
    pytest.fail("Nobleman did not banish a field monster while opposing Kycoo was active")
