"""Book chained to Heavy Storm saves a Premature Burial monster."""

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
BOOK = 14087893
HEAVY = 19613556
MYSTICAL_ELF = 15025844
SECOND_DISCARD = 79182538


def _deck(path, cards):
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_book", [False, True])
def test_book_response_to_heavy_preserves_premature_monster(tmp_path, chain_book):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (GRACEFUL, PREMATURE, BOOK, HEAVY)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card scripts not installed")
    owner = _deck(tmp_path / "premature_book.ydk", (
        GRACEFUL, PREMATURE, BOOK, *VANILLA_DECK[3:]))
    opponent = _deck(tmp_path / "heavy.ydk", (
        HEAVY, *VANILLA_DECK[1:]))

    with GoatEnvironment(owner, opponent, seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, PREMATURE, BOOK} <= {c.code for c in obs.hand}
        assert HEAVY in {c.code for c in env.engine.probe.observation(1).hand}
        graceful = discarded = premature = target_chosen = revived = False
        book_set = heavy_used = responded = book_targeted = checked = False
        for _ in range(85):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate" and
                                   a.parameters.get("code") == GRACEFUL), None)
                    graceful |= action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"] for c in
                                   a.parameters["cards"]} == {
                                       MYSTICAL_ELF, SECOND_DISCARD}), None)
                    discarded |= action is not None
                if discarded and not premature and action is None:
                    action = next((a for a in actions if a.kind == "activate" and
                                   a.parameters.get("code") == PREMATURE), None)
                    premature |= action is not None
                if premature and not target_chosen and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") ==
                                   MYSTICAL_ELF and a.parameters.get("location") == 16), None)
                    target_chosen |= action is not None
                if revived and not book_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap" and
                                   a.parameters.get("code") == BOOK), None)
                    book_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and book_set and not heavy_used:
                action = next((a for a in actions if a.kind == "activate" and
                               a.parameters.get("code") == HEAVY), None)
                heavy_used |= action is not None
            if heavy_used and obs.acting_player == 0 and not responded:
                option = next((a for a in actions if a.kind == "chain" and
                               a.parameters.get("code") == BOOK), None)
                if option is not None:
                    assert [link.card_code for link in obs.chain] == [HEAVY]
                    assert any(c.code == MYSTICAL_ELF and c.controller == 0
                               and c.position == "faceup" for c in obs.field)
                    action = option if chain_book else next(a for a in actions
                                                             if a.kind == "pass")
                    responded = True
            if chain_book and responded and not book_targeted and \
                    actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") ==
                               MYSTICAL_ELF and a.parameters.get("controller") == 0), None)
                book_targeted |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if target_chosen and not revived and any(
                    c.code == MYSTICAL_ELF and c.zone == "monster" for c in obs.field):
                assert obs.life_points == (7200, 8000)
                assert any(c.code == PREMATURE for c in obs.field)
                revived = True
            if responded and not checked and not obs.chain and \
                    HEAVY in {c.code for c in obs.graveyards[1]}:
                assert graceful and discarded and premature and target_chosen
                assert revived and book_set and heavy_used
                assert book_targeted == chain_book
                assert obs.life_points == (7200, 8000)
                assert {PREMATURE, GRACEFUL, BOOK} <= {
                    c.code for c in obs.graveyards[0]}
                assert (MYSTICAL_ELF in {c.code for c in obs.graveyards[0]}) != chain_book
                owner_view = env.engine.probe.observation(0)
                monsters = [c for c in owner_view.field if c.code == MYSTICAL_ELF]
                assert len(monsters) == int(chain_book)
                if chain_book:
                    assert monsters[0].position == "facedown"
                    opponent_view = env.engine.probe.observation(1)
                    hidden = next(c for c in opponent_view.field
                                  if c.zone == "monster" and c.controller == 0)
                    assert hidden.code is None and hidden.position == "facedown"
                    assert (0, "monster", hidden.sequence, MYSTICAL_ELF) in {
                        (c.controller, c.zone, c.sequence, c.code)
                        for c in opponent_view.known_opponent_field_cards}
                loaded = env.engine.probe.loaded_script_sha256.keys()
                assert scripts - {f"official/c{BOOK}.lua"} <= loaded
                if chain_book:
                    assert f"official/c{BOOK}.lua" in loaded
                checked = True
                break
        assert checked, "Premature / Heavy / Book branch did not resolve"

        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(5000):
            if env.is_terminal():
                break
            legal = env.legal_actions()
            obs = env.step(agents[obs.acting_player].select_action(obs, legal))
        assert env.is_terminal(), "Premature / Heavy / Book duel exceeded 5000 decisions"
        trajectory = env.trajectory()
        path = tmp_path / f"premature_heavy_book_{chain_book}.json"
        write_trajectory(path, trajectory)
        assert verify_trajectory(read_trajectory(path),
                                 ExperimentalOcgcoreEngine(root)) == len(trajectory.decisions)
        assert audit_trajectory_visibility(trajectory)["decisions"] == len(
            trajectory.decisions)
