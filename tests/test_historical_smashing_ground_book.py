"""Smashing Ground uses face-up DEF at resolution and does not target.

Sources: https://www.db.yugioh-card.com/yugiohdb/card_search.action?cid=5905&ope=2&request_locale=en
and the Smashing Ground/Riryoku Field ruling at https://www.goatformat.com/rulings6.html.
"""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SMASHING_GROUND = 97169186
BOOK_OF_MOON = 14087893
GEMINI_ELF = 69140098  # 900 DEF
MYSTICAL_ELF = 15025844  # 2000 DEF
THIRTEENTH_GRAVE = 32864  # 900 DEF


def _decks(tmp_path, *, tie=False):
    attacker = list(VANILLA_DECK)
    attacker[0] = SMASHING_GROUND
    defender = list(VANILLA_DECK)
    defender[0], defender[6] = defender[6], defender[0]
    defender[1], defender[6] = defender[6], defender[1]
    defender[4] = BOOK_OF_MOON
    if tie:
        defender = [THIRTEENTH_GRAVE if code == MYSTICAL_ELF else code
                    for code in defender]
    paths = (tmp_path / "smashing.ydk", tmp_path / "book.ydk")
    for path, cards in zip(paths, (attacker, defender)):
        path.write_text("#main\n" + "\n".join(map(str, cards)) +
                        "\n#extra\n!side\n")
    return tuple(map(str, paths))


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
@pytest.mark.parametrize("book_response", [False, True])
def test_smashing_rechecks_highest_faceup_def_after_book(tmp_path, book_response):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (SMASHING_GROUND, BOOK_OF_MOON):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    own, other = _decks(tmp_path)
    with GoatEnvironment(own, other, seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert SMASHING_GROUND in {card.code for card in obs.hand}
        assert {GEMINI_ELF, MYSTICAL_ELF, BOOK_OF_MOON} <= {
            card.code for card in env.engine.probe.observation(1).hand}
        book_set = gemini_summoned = mystical_summoned = smashing_used = False
        book_used = book_targeted = checked = False
        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"smashing_book_{book_response}.json"
                write_trajectory(path, env.trajectory())
                replay = read_trajectory(path)
                assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(
                    replay.decisions)
                audit_trajectory_visibility(replay)
                loaded = env.engine.probe.loaded_script_sha256
                assert {f"official/c{code}.lua" for code in (
                    SMASHING_GROUND, BOOK_OF_MOON)} <= set(loaded)
                return
            actions = env.legal_actions()
            action = None

            def choose(kind, code=None):
                return next((candidate for candidate in actions
                             if candidate.kind == kind and (code is None or
                                candidate.parameters.get("code") == code)), None)

            if not checked and obs.turn == 2 and obs.acting_player == 1:
                if not book_set:
                    action = choose("set_spell_trap", BOOK_OF_MOON)
                    book_set |= action is not None
                if book_set and not gemini_summoned and action is None:
                    action = choose("normal_summon", GEMINI_ELF)
                    gemini_summoned |= action is not None
            if not checked and obs.turn == 4 and obs.acting_player == 1 \
                    and not mystical_summoned:
                action = choose("normal_summon", MYSTICAL_ELF)
                mystical_summoned |= action is not None
            if not checked and obs.turn == 5 and obs.acting_player == 0 \
                    and not smashing_used:
                action = choose("activate", SMASHING_GROUND)
                smashing_used |= action is not None
                if action is not None:
                    faceup = {(card.code, card.defense) for card in obs.field
                              if card.controller == 1 and card.zone == "monster"}
                    assert faceup == {(GEMINI_ELF, 900), (MYSTICAL_ELF, 2000)}
            if smashing_used and not checked and obs.chain and \
                    obs.chain[0].card_code == SMASHING_GROUND:
                assert obs.chain[0].targets == ()
                if book_response and obs.acting_player == 1 and not book_used:
                    action = choose("chain", BOOK_OF_MOON)
                    book_used |= action is not None
                if book_used and not book_targeted and \
                        actions[0].kind == "select_card":
                    action = choose("select_card", MYSTICAL_ELF)
                    book_targeted |= action is not None
            if smashing_used and not checked and not obs.chain and \
                    SMASHING_GROUND in {card.code for card in obs.graveyards[0]}:
                assert gemini_summoned and mystical_summoned and book_set
                assert obs.life_points == (8000, 8000)
                if book_response:
                    assert book_used and book_targeted
                    assert GEMINI_ELF in {card.code for card in obs.graveyards[1]}
                    assert MYSTICAL_ELF not in {card.code for card in obs.graveyards[1]}
                    hidden = [card for card in obs.field if card.controller == 1
                              and card.zone == "monster"]
                    assert len(hidden) == 1 and hidden[0].position == "facedown"
                    assert hidden[0].code is None
                    owner = env.engine.probe.observation(1)
                    assert any(card.code == MYSTICAL_ELF and card.position == "facedown"
                               for card in owner.field)
                else:
                    assert not book_used
                    assert MYSTICAL_ELF in {card.code for card in obs.graveyards[1]}
                    assert GEMINI_ELF not in {card.code for card in obs.graveyards[1]}
                    assert any(card.code == GEMINI_ELF and card.position == "faceup"
                               for card in obs.field)
                checked = True
            if action is None:
                action = (agents[obs.acting_player].select_action(obs, actions)
                          if checked else next((candidate for candidate in actions
                                                if candidate.kind in (
                                                    "place", "pass", "end_phase")),
                                               actions[0]))
            obs = env.step(action)
    pytest.fail("Smashing Ground fixture did not reach a verified terminal duel")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
@pytest.mark.parametrize("destroyed", [GEMINI_ELF, THIRTEENTH_GRAVE])
def test_smashing_ground_tied_highest_def_offers_both_choices(tmp_path, destroyed):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{SMASHING_GROUND}.lua").is_file():
        pytest.skip("Smashing Ground script not installed")
    own, other = _decks(tmp_path, tie=True)
    with GoatEnvironment(own, other, seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        book_set = gemini_summoned = grave_summoned = smashing_used = False
        selected = checked = False
        agents = (RandomAgent(200), RandomAgent(201))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"smashing_tie_{destroyed}.json"
                write_trajectory(path, env.trajectory())
                replay = read_trajectory(path)
                assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(
                    replay.decisions)
                audit_trajectory_visibility(replay)
                assert f"official/c{SMASHING_GROUND}.lua" in \
                    env.engine.probe.loaded_script_sha256
                return
            actions = env.legal_actions()
            action = None

            def choose(kind, code=None):
                return next((candidate for candidate in actions
                             if candidate.kind == kind and (code is None or
                                candidate.parameters.get("code") == code)), None)

            if not checked and obs.turn == 2 and obs.acting_player == 1:
                if not book_set:
                    action = choose("set_spell_trap", BOOK_OF_MOON)
                    book_set |= action is not None
                if book_set and not gemini_summoned and action is None:
                    action = choose("normal_summon", GEMINI_ELF)
                    gemini_summoned |= action is not None
            if not checked and obs.turn == 4 and obs.acting_player == 1 \
                    and not grave_summoned:
                action = choose("normal_summon", THIRTEENTH_GRAVE)
                grave_summoned |= action is not None
            if not checked and obs.turn == 5 and obs.acting_player == 0 \
                    and not smashing_used:
                action = choose("activate", SMASHING_GROUND)
                smashing_used |= action is not None
            if smashing_used and not checked and choose("select_card"):
                assert {candidate.parameters.get("code") for candidate in actions
                        if candidate.kind == "select_card"} == {
                            GEMINI_ELF, THIRTEENTH_GRAVE}
                assert all(candidate.parameters.get("controller") == 1
                           for candidate in actions if candidate.kind == "select_card")
                action = choose("select_card", destroyed)
                selected = True
            if smashing_used and selected and not checked and \
                    SMASHING_GROUND in {card.code for card in obs.graveyards[0]}:
                assert destroyed in {card.code for card in obs.graveyards[1]}
                survivor = ({GEMINI_ELF, THIRTEENTH_GRAVE} - {destroyed}).pop()
                assert any(card.code == survivor and card.position == "faceup"
                           for card in obs.field)
                assert obs.life_points == (8000, 8000)
                checked = True
            if action is None:
                action = (agents[obs.acting_player].select_action(obs, actions)
                          if checked else next((candidate for candidate in actions
                                                if candidate.kind in (
                                                    "place", "pass", "end_phase")),
                                               actions[0]))
            obs = env.step(action)
    pytest.fail("Smashing Ground tie fixture did not reach a verified terminal duel")
