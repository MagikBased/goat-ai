"""Book on Tsukuyomi does not stop its pending Dekoichi reset."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

DEKOICHI = 87621407
TSUKUYOMI = 34853266
BOOK = 14087893


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("book_target", [TSUKUYOMI, DEKOICHI])
def test_book_response_to_tsukuyomi_trigger(tmp_path, book_target):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (DEKOICHI, TSUKUYOMI, BOOK)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required official card script not installed")
    flipper = tmp_path / "flipper.ydk"
    flipper.write_text("#main\n" + "\n".join(map(str, (
        *([DEKOICHI] * 3), *([TSUKUYOMI] * 3), *VANILLA_DECK[6:])))
        + "\n#extra\n!side\n")
    responder = tmp_path / "book.ydk"
    responder.write_text("#main\n" + "\n".join(map(str, (
        *([BOOK] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(flipper), str(responder), seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {DEKOICHI, TSUKUYOMI} <= {c.code for c in obs.hand}
        assert BOOK in {c.code for c in env.engine.probe.observation(1).hand}
        dekoichi_set = flipped = book_set = tsuk_summoned = tsuk_targeted = False
        book_chained = book_targeted = resolved = False
        deck_before = None
        for _ in range(100):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not dekoichi_set:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == DEKOICHI), None)
                dekoichi_set = action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not book_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == BOOK), None)
                book_set = action is not None
            if obs.turn == 3 and obs.acting_player == 0:
                if not flipped:
                    action = next((a for a in actions if a.kind == "flip_summon"
                                   and a.parameters.get("code") == DEKOICHI), None)
                    if action is not None:
                        flipped = True
                        deck_before = obs.deck_counts[0]
                if flipped and not tsuk_summoned and action is None \
                        and obs.deck_counts[0] == deck_before - 1:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == TSUKUYOMI), None)
                    tsuk_summoned = action is not None
                if tsuk_summoned and not tsuk_targeted \
                        and actions[0].kind == "select_card":
                    assert [link.card_code for link in obs.chain] == [TSUKUYOMI]
                    action = next((a for a in actions if a.parameters.get("code") == DEKOICHI
                                   and a.parameters.get("controller") == 0), None)
                    tsuk_targeted = action is not None
            if tsuk_targeted and obs.acting_player == 1 and not book_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK), None)
                book_chained = action is not None
            if book_chained and not book_targeted \
                    and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == book_target
                               and a.parameters.get("controller") == 0), None)
                book_targeted = action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if book_targeted and not resolved \
                    and BOOK in {c.code for c in obs.graveyards[1]} \
                    and not obs.chain and obs.turn == 3:
                own = env.engine.probe.observation(0)
                expected = ({(DEKOICHI, "facedown"), (TSUKUYOMI, "facedown")}
                            if book_target == TSUKUYOMI else
                            {(DEKOICHI, "facedown"), (TSUKUYOMI, "faceup")})
                assert {(c.code, c.position) for c in own.field
                        if c.controller == 0 and c.zone == "monster"} == expected
                other = env.engine.probe.observation(1)
                opposing_field = [c for c in other.field if c.controller == 0
                                  and c.zone == "monster"]
                assert len(opposing_field) == 2
                assert sum(c.position == "facedown" and c.code is None
                           for c in opposing_field) == (
                               2 if book_target == TSUKUYOMI else 1)
                if book_target == DEKOICHI:
                    assert any(c.code == TSUKUYOMI and c.position == "faceup"
                               for c in opposing_field)
                assert {c.code for c in other.known_opponent_field_cards} == (
                    {DEKOICHI, TSUKUYOMI} if book_target == TSUKUYOMI
                    else {DEKOICHI})
                assert not other.known_opponent_hand_cards
                assert not any(a.kind == "flip_summon"
                               and a.parameters.get("code") in (DEKOICHI, TSUKUYOMI)
                               for a in env.legal_actions())
                assert own.deck_counts[0] == deck_before - 1
                resolved = True
            if resolved and obs.turn == 4:
                own = env.engine.probe.observation(0)
                if book_target == TSUKUYOMI:
                    assert any(c.code == TSUKUYOMI and c.position == "facedown"
                               for c in own.field)
                    assert TSUKUYOMI not in {c.code for c in own.hand}
                    other = env.engine.probe.observation(1)
                    assert {c.code for c in other.known_opponent_field_cards} == {
                        DEKOICHI, TSUKUYOMI}
                    assert TSUKUYOMI not in other.known_opponent_hand_cards
                else:
                    assert TSUKUYOMI in {c.code for c in own.hand}
                    assert not any(c.code == TSUKUYOMI for c in own.field)
                    other = env.engine.probe.observation(1)
                    assert {c.code for c in other.known_opponent_field_cards} == {
                        DEKOICHI}
                    assert TSUKUYOMI in other.known_opponent_hand_cards
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                agents = (RandomAgent(15), RandomAgent(16))
                for _ in range(5000):
                    action = agents[obs.acting_player].select_action(
                        obs, env.legal_actions())
                    obs = env.step(action)
                    if env.is_terminal():
                        path = tmp_path / f"tsukuyomi_book_{book_target}.json"
                        write_trajectory(path, env.trajectory())
                        assert verify_trajectory(read_trajectory(path),
                                                 ExperimentalOcgcoreEngine(root)) == len(
                                                     env.trajectory().decisions)
                        return
                pytest.fail("Tsukuyomi / Book duel did not finish")
    pytest.fail("Tsukuyomi / Book response did not resolve")
