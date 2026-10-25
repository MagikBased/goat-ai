"""Two Books resolve against the same or different face-up monsters."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.observations import TargetSlotView

BOOK = 14087893


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("different_targets", [False, True])
def test_book_chained_to_book_resolves_by_target(tmp_path, different_targets):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    script = f"official/c{BOOK}.lua"
    if not (root / "scripts" / script).is_file():
        pytest.skip("Book of Moon script not installed")
    deck = tmp_path / "book.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        BOOK, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), str(deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert BOOK in {c.code for c in obs.hand}
        assert BOOK in {c.code for c in env.engine.probe.observation(1).hand}
        summoned = book_set = opponent_summoned = False
        first_book = first_target = second_book = False
        second_target = two_link_seen = False
        monster_code = opponent_monster_code = None
        for _ in range(90):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    summoned = True
                    monster_code = action.parameters["code"]
            if obs.turn == 2 and obs.acting_player == 1 and not book_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == BOOK), None)
                book_set |= action is not None
            if different_targets and obs.turn == 2 and obs.acting_player == 1 \
                    and book_set and not opponent_summoned and action is None:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    opponent_summoned = True
                    opponent_monster_code = action.parameters["code"]
            if obs.turn == 3 and obs.acting_player == 0 and book_set \
                    and (not different_targets or opponent_summoned) \
                    and not first_book:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == BOOK), None)
                first_book |= action is not None
            if first_book and not first_target and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 0
                               and a.parameters.get("code") == monster_code), None)
                first_target |= action is not None
            if first_target and obs.acting_player == 1 and not second_book:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK), None)
                if option is not None:
                    assert [link.card_code for link in obs.chain] == [BOOK]
                    action = option
                    second_book = True
            if second_book and not second_target and actions[0].kind == "select_card":
                target_controller = 1 if different_targets else 0
                target_code = opponent_monster_code if different_targets else monster_code
                action = next((a for a in actions if
                               a.parameters.get("controller") == target_controller
                               and a.parameters.get("code") == target_code), None)
                second_target |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if second_target and len(obs.chain) == 2:
                assert [link.card_code for link in obs.chain] == [BOOK, BOOK]
                own_monster = next(c for c in obs.field if c.controller == 0
                                   and c.zone == "monster")
                first_slot = (TargetSlotView(0, "monster", own_monster.sequence),)
                second_slot = first_slot
                if different_targets:
                    opponent_monster = next(c for c in obs.field if c.controller == 1
                                            and c.zone == "monster")
                    second_slot = (TargetSlotView(1, "monster",
                                                  opponent_monster.sequence),)
                assert obs.chain[0].targets == first_slot
                assert obs.chain[1].targets == second_slot
                two_link_seen = True
            if second_target and not obs.chain and BOOK in {
                    c.code for c in obs.graveyards[0]} and BOOK in {
                    c.code for c in obs.graveyards[1]}:
                own = env.engine.probe.observation(0)
                opponent = env.engine.probe.observation(1)
                assert two_link_seen
                assert obs.life_points == (8000, 8000)
                assert any(c.controller == 0 and c.code == monster_code
                           and c.position == "facedown" for c in own.field)
                assert any(c.controller == 0 and c.code is None
                           and c.position == "facedown" for c in opponent.field)
                assert any(c.code == monster_code
                           for c in opponent.known_opponent_field_cards)
                if different_targets:
                    assert any(c.controller == 1 and c.code == opponent_monster_code
                               and c.position == "facedown" for c in opponent.field)
                    assert any(c.controller == 1 and c.code is None
                               and c.position == "facedown" for c in own.field)
                    assert any(c.code == opponent_monster_code
                               for c in own.known_opponent_field_cards)
                assert env.engine.probe.loaded_script_sha256[script]
                return
    pytest.fail("Book/Book response did not resolve within 90 decisions")
