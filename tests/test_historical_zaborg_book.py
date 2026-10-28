"""A chain response may set Zaborg without cancelling its Summon trigger."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.decks import read_ydk
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

ZABORG = 51945556
TRIBUTE = 15025844
BOOK = 14087893


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_book", [False, True])
def test_book_on_zaborg_does_not_cancel_its_tribute_summon_effect(tmp_path, chain_book):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (ZABORG, BOOK)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card scripts not installed")
    decks = Path(__file__).resolve().parent.parent / "examples/decks"
    own_cards = list(read_ydk(decks / "cannon_probe.ydk").main)
    own_cards[:2] = [TRIBUTE, ZABORG]
    own = tmp_path / "zaborg.ydk"
    own.write_text("#main\n" + "\n".join(map(str, own_cards)) + "\n#extra\n!side\n")
    opponent = tmp_path / "book.ydk"
    opponent.write_text("#main\n" + "\n".join(map(str, (
        *([BOOK] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(opponent), seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert ZABORG in {card.code for card in obs.hand}
        assert BOOK in {card.code for card in env.engine.probe.observation(1).hand}
        first_summoned = book_set = opponent_set = zaborg_summoned = False
        tributed = target_selected = response_seen = book_targeted = checked = False
        opponent_code = None
        agents = (RandomAgent(18), RandomAgent(19))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"zaborg_book_{chain_book}.json"
                write_trajectory(path, env.trajectory())
                replay = read_trajectory(path)
                assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(
                    replay.decisions)
                assert audit_trajectory_visibility(replay)["decisions"] == len(
                    replay.decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not first_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == TRIBUTE), None)
                first_summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not book_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOOK), None)
                    book_set |= action is not None
                if book_set and not opponent_set and action is None:
                    action = next((a for a in actions if a.kind == "set_monster"), None)
                    if action is not None:
                        opponent_code = action.parameters["code"]
                        opponent_set = True
            if obs.turn == 3 and obs.acting_player == 0 and not zaborg_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == ZABORG), None)
                zaborg_summoned |= action is not None
            if zaborg_summoned and not tributed and action is None:
                action = next((a for a in actions if a.kind == "tribute"
                               and a.parameters.get("code") == TRIBUTE), None)
                tributed |= action is not None
            if tributed and not target_selected and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 4), None)
                assert action is not None and "code" not in action.parameters
                target_selected = True
            if target_selected and not response_seen and obs.acting_player == 1:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK), None)
                if option is not None:
                    assert [link.card_code for link in obs.chain] == [ZABORG]
                    action = option if chain_book else next(
                        a for a in actions if a.kind == "pass")
                    response_seen = True
            if chain_book and response_seen and not book_targeted and action is None \
                    and obs.acting_player == 1 and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 0
                               and a.parameters.get("location") == 4
                               and a.parameters.get("code") == ZABORG), None)
                book_targeted |= action is not None
            if action is None and not checked:
                action = next((a for a in actions if a.kind in ("place", "pass", "end_phase")),
                              actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if response_seen and not checked and not obs.chain \
                    and opponent_code in {c.code for c in obs.graveyards[1]}:
                own_view = env.engine.probe.observation(0)
                opponent_view = env.engine.probe.observation(1)
                assert any(c.code == ZABORG and c.position == (
                    "facedown" if chain_book else "faceup") for c in own_view.field)
                assert any(c.controller == 0 and c.code == (
                    None if chain_book else ZABORG) for c in opponent_view.field)
                assert (BOOK in {c.code for c in own_view.graveyards[1]}) == chain_book
                assert TRIBUTE in {c.code for c in own_view.graveyards[0]}
                loaded = env.engine.probe.loaded_script_sha256.keys()
                assert f"official/c{ZABORG}.lua" in loaded
                if chain_book:
                    assert scripts <= loaded
                assert book_targeted == chain_book
                checked = True
    pytest.fail("Zaborg / Book duel did not finish")
