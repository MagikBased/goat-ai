"""Book of Moon can set Restrict or its target before equip resolves."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

SCAPEGOAT = 504700123
METAMORPHOSIS = 46411259
RESTRICT = 504700102
BOOK = 14087893
SHEEP_CODES = {73915052, 73915053, 73915054, 73915055}


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("book_case", ["no_book", "book_restrict", "book_target"])
def test_book_chained_to_restrict_equip_effect(tmp_path, book_case):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{SCAPEGOAT}.lua", f"official/c{METAMORPHOSIS}.lua",
                     f"goat/c{RESTRICT}.lua", f"official/c{BOOK}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    attacker = tmp_path / "restrict.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        *((SCAPEGOAT, METAMORPHOSIS) * 3), *VANILLA_DECK[6:])))
        + f"\n#extra\n{RESTRICT}\n!side\n")
    defender = tmp_path / "book.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        BOOK, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert BOOK in {c.code for c in env.engine.probe.observation(1).hand}
        goat = meta = token = fusion = restrict = target = False
        summoned = book_set = chained_book = book_target = False
        target_code = None
        for _ in range(95):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not goat:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                goat |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        target_code = action.parameters["code"]
                        summoned = True
                if summoned and not book_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOOK), None)
                    book_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not meta:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == METAMORPHOSIS), action)
                meta |= action is not None and action.kind == "activate"
            if meta and not token and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               in SHEEP_CODES), action)
                token |= action is not None and action.kind == "select_card"
            if token and not fusion and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == RESTRICT), action)
                fusion |= action is not None and action.kind == "select_card"
            if fusion and not restrict:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == RESTRICT), action)
                restrict |= action is not None and action.kind == "chain"
            if restrict and not target and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == target_code and a.parameters.get("controller") == 1),
                              action)
                target |= action is not None and action.kind == "select_card"
            if book_case != "no_book" and target and obs.acting_player == 1 \
                    and not chained_book:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK), action)
                if action is not None and action.kind == "chain":
                    assert obs.chain[0].card_code == RESTRICT
                    chained_book = True
            if chained_book and not book_target and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == (RESTRICT if book_case == "book_restrict" else target_code)
                               and a.parameters.get("controller") == (
                                   0 if book_case == "book_restrict" else 1)),
                              action)
                book_target |= action is not None and action.kind == "select_card"
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if target and obs.turn == 3 and obs.phase == "main1" \
                    and obs.acting_player == 0 and not obs.chain:
                own = env.engine.probe.observation(0)
                other = env.engine.probe.observation(1)
                own_restrict = next(c for c in own.field if c.code == RESTRICT)
                assert sum(c.code in SHEEP_CODES for c in own.field) == 3
                assert METAMORPHOSIS in {c.code for c in own.graveyards[0]}
                assert own.extra_deck_counts[0] == 0
                if book_case == "book_restrict":
                    assert chained_book and book_target
                    assert own_restrict.position == "facedown"
                    assert BOOK in {c.code for c in own.graveyards[1]}
                    assert target_code in {c.code for c in own.field
                                           if c.zone == "monster" and c.controller == 1}
                    assert target_code not in {c.code for c in own.graveyards[1]}
                    assert not any(c.zone == "spell_trap" and c.code == target_code
                                   for c in own.field)
                    hidden = next(c for c in other.field if c.zone == "monster"
                                  and c.controller == 0 and c.sequence == own_restrict.sequence)
                    assert hidden.code is None and hidden.position == "facedown"
                    assert (0, "monster", hidden.sequence, RESTRICT) in {
                        (c.controller, c.zone, c.sequence, c.code)
                        for c in other.known_opponent_field_cards}
                else:
                    assert chained_book == (book_case == "book_target")
                    assert own_restrict.position == "faceup"
                    assert not any(c.code == target_code and c.zone == "monster"
                                   for c in own.field)
                    equipped = next(c for c in own.field if c.code == target_code
                                    and c.zone == "spell_trap" and c.controller == 0)
                    if book_case == "book_target":
                        assert book_target
                        assert BOOK in {c.code for c in own.graveyards[1]}
                        assert equipped.position == "facedown"
                        assert own_restrict.attack == own_restrict.defense == 0
                        hidden = next(c for c in other.field if c.zone == "spell_trap"
                                      and c.controller == 0
                                      and c.sequence == equipped.sequence)
                        assert hidden.code is None and hidden.position == "facedown"
                        assert (0, "spell_trap", hidden.sequence, target_code) in {
                            (c.controller, c.zone, c.sequence, c.code)
                            for c in other.known_opponent_field_cards}
                    else:
                        assert BOOK in {c.code for c in other.field}
                assert own.life_points == (8000, 8000)
                assert {f"goat/c{SCAPEGOAT}.lua", f"official/c{METAMORPHOSIS}.lua",
                        f"goat/c{RESTRICT}.lua"} \
                    <= env.engine.probe.loaded_script_sha256.keys()
                if book_case != "no_book":
                    assert f"official/c{BOOK}.lua" in \
                        env.engine.probe.loaded_script_sha256
                return
    pytest.fail("Restrict / Book chain did not resolve within 95 decisions")
