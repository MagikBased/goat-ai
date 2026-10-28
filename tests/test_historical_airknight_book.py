"""Book stops Airknight's attack before damage and its battle-damage draw."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

GRACEFUL = 79571449
PREMATURE = 70828912
AIRKNIGHT = 18036057
BOOK = 14087893
SECOND_DISCARD = 79182538


def _deck(path, cards):
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("use_book", [False, True])
def test_book_on_attacking_airknight_ends_attack_without_draw(tmp_path, use_book):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in
               (GRACEFUL, PREMATURE, AIRKNIGHT, BOOK)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required pinned scripts not installed")
    own = _deck(tmp_path / "airknight.ydk", (
        GRACEFUL, PREMATURE, AIRKNIGHT, *VANILLA_DECK[3:]))
    other = _deck(tmp_path / "book.ydk", (BOOK, *VANILLA_DECK[1:]))

    with GoatEnvironment(own, other, seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, PREMATURE, AIRKNIGHT} <= {c.code for c in obs.hand}
        assert BOOK in {c.code for c in env.engine.probe.observation(1).hand}
        graceful = discarded = premature = book_set = attacked = responded = False
        book_activated = target_selected = checked = main2_checked = False
        before_deck = before_hand = None
        for _ in range(125):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate" and
                                   a.parameters.get("code") == GRACEFUL), None)
                    graceful |= action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {
                        c["code"] for c in a.parameters["cards"]} ==
                        {AIRKNIGHT, SECOND_DISCARD}), None)
                    discarded |= action is not None
                if discarded and not premature and action is None:
                    action = next((a for a in actions if a.kind == "activate" and
                                   a.parameters.get("code") == PREMATURE), None)
                    premature |= action is not None
                if premature and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") ==
                                   AIRKNIGHT and a.parameters.get("location") == 16), action)
            if obs.turn == 2 and obs.acting_player == 1 and not book_set:
                action = next((a for a in actions if a.kind == "set_spell_trap" and
                               a.parameters.get("code") == BOOK), None)
                book_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0:
                if obs.phase == "main1":
                    action = next((a for a in actions if a.kind == "battle_phase"), action)
                if obs.phase == "battle_start" and not attacked:
                    action = next((a for a in actions if a.kind == "attack" and
                                   a.parameters.get("code") == AIRKNIGHT), action)
                    if action is not None and action.kind == "attack":
                        before_deck = obs.deck_counts[0]
                        before_hand = len(obs.hand)
                        attacked = True
            if attacked and obs.acting_player == 1 and not responded:
                book = next((a for a in actions if a.kind == "chain" and
                             a.parameters.get("code") == BOOK), None)
                if book is not None:
                    assert obs.phase == "battle_step"
                    action = book if use_book else next(a for a in actions if a.kind == "pass")
                    responded = True
                    book_activated = use_book
            if book_activated and not target_selected and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == AIRKNIGHT
                               and a.parameters.get("controller") == 0), None)
                target_selected |= action is not None
            if use_book and checked and obs.turn == 3 and obs.acting_player == 0 \
                    and obs.phase == "main2":
                assert not any(a.kind == "flip_summon" and
                               a.parameters.get("code") == AIRKNIGHT for a in actions)
                main2_checked = True
                break
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase", "main2")), actions[0])
            obs = env.step(action)
            owner = env.engine.probe.observation(0)
            if use_book and target_selected and not checked and obs.chain == () \
                    and BOOK in {c.code for c in owner.graveyards[1]}:
                assert owner.life_points == (7200, 8000)
                assert owner.deck_counts[0] == before_deck
                assert len(owner.hand) == before_hand
                assert any(c.code == AIRKNIGHT and c.position == "facedown"
                           for c in owner.field)
                assert all(a.kind != "attack" for a in env.legal_actions())
                checked = True
            if not use_book and responded and owner.life_points == (7200, 6100) \
                    and owner.deck_counts[0] == before_deck - 1:
                assert len(owner.hand) == before_hand + 1
                assert any(c.code == AIRKNIGHT and c.position == "faceup"
                           for c in owner.field)
                checked = True
                break
        assert checked, "Airknight attack did not reach the Book/pass outcome"
        assert not use_book or main2_checked
        required = scripts if use_book else scripts - {f"official/c{BOOK}.lua"}
        assert required <= env.engine.probe.loaded_script_sha256.keys()
        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(5000):
            if env.is_terminal():
                break
            legal = env.legal_actions()
            obs = env.step(agents[obs.acting_player].select_action(obs, legal))
        assert env.is_terminal()
        trajectory = env.trajectory()
        path = tmp_path / f"airknight_book_{use_book}.json"
        write_trajectory(path, trajectory)
        assert verify_trajectory(read_trajectory(path),
                                 ExperimentalOcgcoreEngine(root)) == len(trajectory.decisions)
        assert audit_trajectory_visibility(trajectory)["decisions"] == len(
            trajectory.decisions)
