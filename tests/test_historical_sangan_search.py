"""Sangan shows either its chosen monster or an empty-search Deck to its opponent."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

SANGAN = 504700178
BOOK_OF_MOON = 14087893
POT_OF_GREED = 55144522
HEAVY_STORM = 19613556
LOW_ATTACK_NORMALS = {15025844, 13039848}
MYSTICAL_ELF = 15025844
NOBLEMAN = 504700116


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("has_target", [False, True])
def test_sangan_search_reveals_only_to_opponent(tmp_path, has_target):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/goat/c{SANGAN}.lua").is_file():
        pytest.skip("GOAT Sangan script not installed")
    cards = (SANGAN, *(c for c in VANILLA_DECK if c not in LOW_ATTACK_NORMALS),
             BOOK_OF_MOON, BOOK_OF_MOON, BOOK_OF_MOON, POT_OF_GREED,
             MYSTICAL_ELF if has_target else HEAVY_STORM)
    assert len(cards) == 40
    defender = tmp_path / "sangan_search.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, cards))
                        + "\n#extra\n!side\n")
    with GoatEnvironment(str(defender), "examples/decks/vanilla_probe.ydk", seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        sangan_set = opponent_summoned = attacked = selected = False
        deck_before_attack = None
        assert not env.engine.probe.observation(1).private_reveals
        for _ in range(60):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not sangan_set:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == SANGAN), None)
                sangan_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not opponent_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") not in LOW_ATTACK_NORMALS),
                                  None)
                    opponent_summoned |= action is not None
                if opponent_summoned and not attacked and action is None:
                    action = next((a for a in actions if a.kind in (
                        "battle_phase", "attack")), None)
                    attacked |= action is not None and action.kind == "attack"
                    if attacked:
                        deck_before_attack = obs.deck_counts[0]
            if attacked and actions[0].kind == "select_card" and action is None:
                if obs.acting_player == 0 and has_target:
                    assert {a.parameters.get("code") for a in actions} == {MYSTICAL_ELF}
                    assert all(a.parameters.get("location") == 1
                               and "sequence" not in a.parameters for a in actions)
                    action = actions[0]
                    selected = True
                else:
                    action = next((a for a in actions if a.kind == "select_card"
                                   and a.parameters.get("controller") == 0), None)
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            owner = env.engine.probe.observation(0)
            opponent = env.engine.probe.observation(1)
            if opponent.private_reveals:
                assert attacked and sangan_set
                assert SANGAN in {c.code for c in owner.graveyards[0]}
                assert not owner.private_reveals
                assert len(opponent.private_reveals) == 1
                reveal = opponent.private_reveals[0]
                assert reveal.recipient == 1 and reveal.turn == 2
                assert all(c.controller == 0 and c.location == (2 if has_target else 1)
                           for c in reveal.cards)
                if has_target:
                    assert selected
                    assert [c.code for c in reveal.cards] == [MYSTICAL_ELF]
                    assert MYSTICAL_ELF in {c.code for c in owner.hand}
                    assert owner.deck_counts[0] == deck_before_attack - 1
                else:
                    assert len(reveal.cards) == owner.deck_counts[0]
                    assert Counter(c.code for c in reveal.cards) == Counter(
                        c.code for c in env.engine.probe._query_location(0, 1))
                    assert owner.deck_counts[0] == deck_before_attack == 34
                assert f"goat/c{SANGAN}.lua" in env.engine.probe.loaded_script_sha256
                return
    pytest.fail("Sangan search did not reveal the correct information to the opponent")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_nobleman_banishes_set_sangan_without_search(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{SANGAN}.lua", f"goat/c{NOBLEMAN}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    defender = tmp_path / "sangan.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        SANGAN, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    with GoatEnvironment("examples/decks/nobleman_probe.ydk", str(defender), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert NOBLEMAN in {c.code for c in obs.hand}
        assert SANGAN in {c.code for c in env.engine.probe.observation(1).hand}
        set_sangan = nobleman_used = target_selected = False
        deck_before = hand_before = None
        for _ in range(55):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1 and not set_sangan:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == SANGAN), None)
                set_sangan |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not nobleman_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == NOBLEMAN), None)
                nobleman_used |= action is not None
                if nobleman_used:
                    defender_view = env.engine.probe.observation(1)
                    deck_before = defender_view.deck_counts[1]
                    hand_before = len(defender_view.hand)
            if nobleman_used and not target_selected and actions[0].kind == "select_card":
                assert any(c.controller == 1 and c.position == "facedown"
                           and c.code is None for c in obs.field)
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("controller") == 1
                               and "code" not in a.parameters), None)
                target_selected = action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if target_selected and SANGAN in {c.code for c in obs.banished[1]}:
                owner = env.engine.probe.observation(1)
                assert SANGAN not in {c.code for c in owner.graveyards[1]}
                assert owner.deck_counts[1] == deck_before
                assert len(owner.hand) == hand_before
                assert any(c.code == MYSTICAL_ELF for c in
                           env.engine.probe._query_location(1, 1))
                assert not any(link.card_code == SANGAN for link in owner.chain)
                assert not owner.private_reveals
                assert not obs.private_reveals
                assert f"goat/c{NOBLEMAN}.lua" in env.engine.probe.loaded_script_sha256
                return
    pytest.fail("Nobleman did not banish Sangan without its Deck search")
