"""The owner searches when a stolen Sangan reaches its Graveyard."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

SANGAN = 504700178
SNATCH_STEAL = 45986603
CANNON_SOLDIER = 11384280
MYSTICAL_ELF = 15025844


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_stolen_sangan_tributed_for_cannon_searches_owners_deck(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{SANGAN}.lua", f"official/c{SNATCH_STEAL}.lua",
                     f"official/c{CANNON_SOLDIER}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    attacker = tmp_path / "snatch_cannon.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        SNATCH_STEAL, CANNON_SOLDIER, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    defender = tmp_path / "sangan.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        SANGAN, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {SNATCH_STEAL, CANNON_SOLDIER}.issubset(c.code for c in obs.hand)
        assert SANGAN in {c.code for c in env.engine.probe.observation(1).hand}
        sangan_summoned = snatched = cannon_summoned = cannon_used = tributed = False
        searched = False
        deck_before = hand_before = None
        for _ in range(80):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1 and not sangan_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == SANGAN), None)
                sangan_summoned |= action is not None
            if obs.turn == 3 and obs.acting_player == 0:
                if not snatched:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == SNATCH_STEAL), None)
                    snatched |= action is not None
                if snatched and not cannon_summoned and action is None:
                    stolen = next((c for c in obs.field if c.code == SANGAN
                                   and c.controller == 0), None)
                    if stolen is not None:
                        action = next((a for a in actions if a.kind == "normal_summon"
                                       and a.parameters.get("code") == CANNON_SOLDIER), None)
                        cannon_summoned |= action is not None
                if cannon_summoned and not cannon_used and action is None:
                    action = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == CANNON_SOLDIER), None)
                    cannon_used |= action is not None
            if snatched and not cannon_summoned and actions[0].kind == "select_card" \
                    and action is None:
                action = next((a for a in actions if a.parameters.get("code") == SANGAN), None)
            if cannon_used and not tributed and actions[0].kind == "select_card" \
                    and action is None:
                action = next((a for a in actions if a.parameters.get("code") == SANGAN
                               and a.parameters.get("controller") == 0), None)
                if action is not None:
                    owner = env.engine.probe.observation(1)
                    deck_before = owner.deck_counts[1]
                    hand_before = len(owner.hand)
                    tributed = True
            if tributed and not searched and obs.acting_player == 1 \
                    and actions[0].kind == "select_card" and action is None:
                assert SANGAN in {c.code for c in obs.graveyards[1]}
                assert obs.life_points == (8000, 7500)
                action = next((a for a in actions if a.parameters.get("code") == MYSTICAL_ELF
                               and a.parameters.get("location") == 1), None)
                searched = action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            attacker_view = env.engine.probe.observation(0)
            owner = env.engine.probe.observation(1)
            if searched and attacker_view.private_reveals:
                assert owner.deck_counts[1] == deck_before - 1
                assert len(owner.hand) == hand_before + 1
                assert MYSTICAL_ELF in {c.code for c in owner.hand}
                assert SANGAN in {c.code for c in owner.graveyards[1]}
                assert not any(c.code == SANGAN for c in attacker_view.graveyards[0])
                assert not owner.private_reveals
                assert [[c.code for c in reveal.cards]
                        for reveal in attacker_view.private_reveals] == [[MYSTICAL_ELF]]
                loaded = env.engine.probe.loaded_script_sha256
                assert f"goat/c{SANGAN}.lua" in loaded
                assert f"official/c{SNATCH_STEAL}.lua" in loaded
                assert f"official/c{CANNON_SOLDIER}.lua" in loaded
                return
    pytest.fail("stolen Sangan did not search its owner's Deck")
