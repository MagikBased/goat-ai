"""Source-backed Solemn Judgment summon-negation regression."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.decks import read_ydk
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

CANNON_SOLDIER = 11384280
SOLEMN_JUDGMENT = 41420027
SANGAN = 504700178
BLS = 504700118
GRACEFUL = 79571449
LIGHT = 15025844
DARK = 7359741
PREMATURE_BURIAL = 70828912


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_solemn_negates_normal_summon_before_ignition_priority(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / "scripts/official/c41420027.lua").is_file():
        pytest.skip("full card script checkout not installed")
    decks = Path(__file__).resolve().parent.parent / "examples/decks"
    opponent = list(read_ydk(decks / "book_three_probe.ydk").main)
    opponent[0] = SOLEMN_JUDGMENT
    opponent_path = tmp_path / "solemn.ydk"
    opponent_path.write_text("#main\n" + "\n".join(map(str, opponent)) + "\n")
    with GoatEnvironment(str(decks / "cannon_probe.ydk"), str(opponent_path),
                         seed=52, engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        trap_set = summon_attempted = solemn_chained = False
        for _ in range(40):
            choices = env.legal_actions()
            if solemn_chained and observation.turn == 3 and (
                observation.acting_player == 0
                and any(choice.kind == "end_phase" for choice in choices)
            ):
                assert trap_set and summon_attempted
                assert observation.life_points == (8000, 4000)
                assert not any(card.code == CANNON_SOLDIER for card in observation.field)
                assert any(card.code == CANNON_SOLDIER
                           for card in observation.graveyards[0])
                assert any(card.code == SOLEMN_JUDGMENT
                           for card in observation.graveyards[1])
                assert not any(choice.kind == "normal_summon" for choice in choices)
                assert not any(choice.kind == "chain"
                               and choice.parameters.get("code") == CANNON_SOLDIER
                               for choice in choices)
                return
            action = None
            if observation.acting_player == 1 and observation.turn == 2 and not trap_set:
                action = next((choice for choice in choices
                               if choice.kind == "set_spell_trap"
                               and choice.parameters.get("code") == SOLEMN_JUDGMENT), None)
                trap_set |= action is not None
            if observation.acting_player == 0 and observation.turn == 3 and not summon_attempted:
                action = next((choice for choice in choices
                               if choice.kind == "normal_summon"
                               and choice.parameters.get("code") == CANNON_SOLDIER), None)
                summon_attempted |= action is not None
            if observation.acting_player == 1 and observation.turn == 3 and (
                summon_attempted and not solemn_chained
            ):
                action = next((choice for choice in choices if choice.kind == "chain"
                               and choice.parameters.get("code") == SOLEMN_JUDGMENT), None)
                solemn_chained |= action is not None
            if action is None:
                action = next((choice for choice in choices
                               if choice.kind == "end_phase"), None)
            if action is None:
                action = next((choice for choice in choices if choice.kind == "pass"),
                              choices[0])
            observation = env.step(action)
        pytest.fail("Solemn summon-negation branch did not resolve within 40 decisions")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_solemn_negated_sangan_summon_does_not_search(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"scripts/goat/c{SANGAN}.lua",
                     f"scripts/official/c{SOLEMN_JUDGMENT}.lua"):
        if not (root / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    attacker = tmp_path / "sangan.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        SANGAN, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    defender = tmp_path / "solemn.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        *([SOLEMN_JUDGMENT] * 3), *VANILLA_DECK[3:])))
                        + "\n#extra\n!side\n")
    with GoatEnvironment(str(attacker), str(defender), seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert SANGAN in {c.code for c in obs.hand}
        assert SOLEMN_JUDGMENT in {c.code for c in env.engine.probe.observation(1).hand}
        set_trap = summon_attempted = solemn_chained = False
        deck_before = hand_before = None
        for _ in range(45):
            actions = env.legal_actions()
            if solemn_chained and obs.acting_player == 0 and obs.phase == "main1" \
                    and SOLEMN_JUDGMENT in {c.code for c in obs.graveyards[1]}:
                assert obs.life_points == (8000, 4000)
                assert SANGAN in {c.code for c in obs.graveyards[0]}
                assert not any(c.code == SANGAN for c in obs.field)
                assert obs.deck_counts[0] == deck_before
                assert len(obs.hand) == hand_before - 1
                assert not obs.private_reveals
                assert not env.engine.probe.observation(1).private_reveals
                assert not any(a.kind == "select_card" and a.parameters.get("location")
                               == 1 for a in actions)
                assert not any(link.card_code == SANGAN for link in obs.chain)
                if any(a.kind == "end_phase" for a in actions):
                    return
            action = None
            if obs.turn == 2 and obs.acting_player == 1 and not set_trap:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SOLEMN_JUDGMENT), None)
                set_trap |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not summon_attempted:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == SANGAN), None)
                if action is not None:
                    deck_before = obs.deck_counts[0]
                    hand_before = len(obs.hand)
                    summon_attempted = True
            if summon_attempted and obs.acting_player == 1 and not solemn_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SOLEMN_JUDGMENT), action)
                solemn_chained |= action is not None and action.kind == "chain"
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "pass", "end_phase")), actions[0])
            obs = env.step(action)
    pytest.fail("Solemn did not negate Sangan's Summon without a search")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_solemn_negates_bls_inherent_special_summon_after_cost(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"scripts/goat/c{BLS}.lua",
                     f"scripts/official/c{GRACEFUL}.lua",
                     f"scripts/official/c{SOLEMN_JUDGMENT}.lua",
                     f"scripts/official/c{PREMATURE_BURIAL}.lua"):
        if not (root / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    lights = (LIGHT, 62651957)
    darks = (49881766, DARK)
    filler = [code for code in VANILLA_DECK if code not in (*lights, *darks)]
    bls_cards = [GRACEFUL, BLS,
                 *(code for code in lights for _ in range(3)),
                 *(code for code in darks for _ in range(3)), *filler[:26]]
    bls_cards[17] = PREMATURE_BURIAL
    attacker = tmp_path / "bls.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, bls_cards))
                        + "\n#extra\n!side\n")
    defender = tmp_path / "solemn.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        *([SOLEMN_JUDGMENT] * 3), *VANILLA_DECK[3:])))
                        + "\n#extra\n!side\n")
    with GoatEnvironment(str(attacker), str(defender), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {BLS, GRACEFUL, LIGHT, DARK, PREMATURE_BURIAL}.issubset(
            c.code for c in obs.hand)
        assert SOLEMN_JUDGMENT in {
            c.code for c in env.engine.probe.observation(1).hand}
        graceful_used = discarded = solemn_set = summon_attempted = solemn_used = False
        costs = []
        for _ in range(75):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not graceful_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    graceful_used |= action is not None
                elif not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"] for c in
                                   a.parameters["cards"]} == {LIGHT, DARK}), None)
                    discarded |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not solemn_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SOLEMN_JUDGMENT), None)
                solemn_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and discarded \
                    and not summon_attempted:
                action = next((a for a in actions if a.kind == "special_summon"
                               and a.parameters.get("code") == BLS), None)
                summon_attempted |= action is not None
            if summon_attempted and len(costs) < 2 \
                    and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               in ({LIGHT, DARK} - set(costs))
                               and a.parameters.get("location") == 16), action)
                if action is not None and action.kind == "select_card":
                    costs.append(action.parameters["code"])
            if summon_attempted and len(costs) == 2 and obs.acting_player == 1 \
                    and not solemn_used:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SOLEMN_JUDGMENT), None)
                if option is not None:
                    assert {c.code for c in obs.banished[0]} == {LIGHT, DARK}
                    assert any(c.code == BLS for c in obs.field)
                    action = option
                    solemn_used = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if solemn_used and obs.acting_player == 0 and obs.phase == "main1" \
                    and SOLEMN_JUDGMENT in {c.code for c in obs.graveyards[1]}:
                assert set(costs) == {LIGHT, DARK}
                assert {c.code for c in obs.banished[0]} == {LIGHT, DARK}
                assert BLS in {c.code for c in obs.graveyards[0]}
                assert not any(c.code == BLS for c in obs.field)
                assert obs.life_points == (8000, 4000)
                assert not any(a.kind == "special_summon" and a.parameters.get("code")
                               == BLS for a in env.legal_actions())
                assert PREMATURE_BURIAL in {c.code for c in obs.hand}
                assert {c.code for c in obs.graveyards[0]} == {GRACEFUL, BLS}
                assert not any(a.kind == "activate" and a.parameters.get("code")
                               == PREMATURE_BURIAL for a in env.legal_actions())
                loaded = env.engine.probe.loaded_script_sha256
                assert {f"goat/c{BLS}.lua",
                        f"official/c{SOLEMN_JUDGMENT}.lua"}.issubset(loaded)
                return
    pytest.fail("Solemn did not negate BLS after its Graveyard cost")
