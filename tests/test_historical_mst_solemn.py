"""Solemn negates Mystical Space Typhoon and preserves its hidden target."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

MST = 5318639
SOLEMN = 41420027
BOOK = 14087893


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("negate", [False, True])
def test_solemn_response_to_mst_preserves_set_book(tmp_path, negate):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (MST, SOLEMN, BOOK)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required official card script not installed")
    attacker = tmp_path / "mst.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        MST, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    defender_cards = list(VANILLA_DECK)
    defender_cards[0] = SOLEMN
    defender_cards[6] = BOOK
    defender = tmp_path / "solemn_book.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, defender_cards))
                        + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert MST in {c.code for c in obs.hand}
        assert {SOLEMN, BOOK} <= {
            c.code for c in env.engine.probe.observation(1).hand}
        solemn_set = book_set = mst_used = book_targeted = solemn_chained = False
        for _ in range(75):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1:
                if not solemn_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == SOLEMN), None)
                    solemn_set = action is not None
                if solemn_set and not book_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOOK), None)
                    book_set = action is not None
            if obs.turn == 3 and obs.acting_player == 0 and book_set:
                if not mst_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == MST), None)
                    mst_used = action is not None
                if mst_used and not book_targeted \
                        and actions[0].kind == "select_card":
                    targets = [a for a in actions if a.kind == "select_card"
                               and a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 8]
                    assert len(targets) == 2
                    assert all("code" not in a.parameters for a in targets)
                    owner = env.engine.probe.observation(1)
                    book = next(c for c in owner.field if c.code == BOOK
                                and c.controller == 1 and c.zone == "spell_trap")
                    action = next(a for a in targets if a.parameters.get("sequence")
                                  == book.sequence)
                    book_targeted = True
            if negate and book_targeted and obs.acting_player == 1 \
                    and not solemn_chained:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SOLEMN), None)
                if option is not None:
                    assert [link.card_code for link in obs.chain] == [MST]
                    action = option
                    solemn_chained = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if book_targeted and MST in {c.code for c in obs.graveyards[0]} \
                    and not obs.chain and obs.turn == 3:
                attacker_view = env.engine.probe.observation(0)
                owner = env.engine.probe.observation(1)
                assert not attacker_view.private_reveals
                assert not attacker_view.known_opponent_field_cards
                if negate:
                    assert solemn_chained and obs.life_points == (8000, 4000)
                    assert SOLEMN in {c.code for c in obs.graveyards[1]}
                    assert BOOK not in {c.code for c in obs.graveyards[1]}
                    assert any(c.code == BOOK and c.position == "facedown"
                               for c in owner.field)
                    assert any(c.controller == 1 and c.zone == "spell_trap"
                               and c.code is None for c in attacker_view.field)
                else:
                    assert not solemn_chained and obs.life_points == (8000, 8000)
                    assert BOOK in {c.code for c in obs.graveyards[1]}
                    assert SOLEMN not in {c.code for c in obs.graveyards[1]}
                    assert not any(c.code == BOOK for c in owner.field)
                    assert any(c.code == SOLEMN and c.position == "facedown"
                               for c in owner.field)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                return
    pytest.fail("MST / Solemn response did not resolve")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_mst_target_choices_ignore_swapped_hidden_backrow_identities(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{MST}.lua").is_file():
        pytest.skip("MST script not installed")
    attacker = tmp_path / "mst.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        MST, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    def reach_choice(first, second):
        cards = list(VANILLA_DECK)
        cards[0], cards[6] = first, second
        defender = tmp_path / f"defender_{first}.ydk"
        defender.write_text("#main\n" + "\n".join(map(str, cards))
                            + "\n#extra\n!side\n")
        with GoatEnvironment(str(attacker), str(defender), seed=52,
                             engine=ExperimentalOcgcoreEngine(root)) as env:
            obs = env.reset()
            assert {SOLEMN, BOOK} <= {
                c.code for c in env.engine.probe.observation(1).hand}
            first_set = second_set = activated = False
            for _ in range(75):
                actions = env.legal_actions()
                action = None
                if obs.turn == 2 and obs.acting_player == 1:
                    if not first_set:
                        action = next((a for a in actions if a.kind == "set_spell_trap"
                                       and a.parameters.get("code") == first), None)
                        first_set = action is not None
                    elif not second_set:
                        action = next((a for a in actions if a.kind == "set_spell_trap"
                                       and a.parameters.get("code") == second), None)
                        second_set = action is not None
                if obs.turn == 3 and obs.acting_player == 0 \
                        and second_set and not activated:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == MST), None)
                    activated = action is not None
                if activated and actions[0].kind == "select_card":
                    assert obs.viewer == obs.acting_player == 0
                    assert len(actions) == 2
                    assert {a.parameters.get("sequence") for a in actions} == {0, 1}
                    assert all(a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 8
                               and "code" not in a.parameters for a in actions)
                    assert len([c for c in obs.field if c.controller == 1
                                and c.zone == "spell_trap" and c.position == "facedown"
                                and c.code is None]) == 2
                    native_slots = env.engine.probe._query_location(1, 8)
                    assert native_slots[0].code == first
                    assert native_slots[1].code == second
                    return obs, actions
                if action is None:
                    action = next((a for a in actions if a.kind in (
                        "pass", "end_phase")), actions[0])
                obs = env.step(action)
        pytest.fail("MST did not reach two hidden backrow choices")

    first_observation, first_actions = reach_choice(SOLEMN, BOOK)
    second_observation, second_actions = reach_choice(BOOK, SOLEMN)
    assert first_observation == second_observation
    assert first_actions == second_actions
