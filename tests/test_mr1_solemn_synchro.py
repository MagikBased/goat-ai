"""Contemporaneous Solemn Judgment response to a Synchro Summon in MR1."""

import hashlib
import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.decks import Decklist, read_advanced_restrictions
from goat_ai.engine.edison_decks import validate_edison_deck
from goat_ai.engine.mr1_synchro_probe import (
    BOKOICHI,
    JUNK_SYNCHRON,
    JUNK_WARRIOR,
    SOLEMN_JUDGMENT,
    PROBE_ELIGIBLE_IDS,
    RESTRICTION_TABLE,
    Mr1SynchroProbeEngine,
)
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SETUP = (
    (1, 0, "set_monster", BOKOICHI),
    (2, 1, "set_spell_trap", SOLEMN_JUDGMENT),
    (3, 0, "flip_summon", BOKOICHI),
    (3, 0, "normal_summon", JUNK_SYNCHRON),
    (3, 0, "special_summon", JUNK_WARRIOR),
)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
def test_solemn_can_negate_synchro_after_materials_are_sent(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    script = root / f"scripts/official/c{SOLEMN_JUDGMENT}.lua"
    if not script.is_file():
        pytest.skip("Solemn Judgment script not installed")
    restrictions = read_advanced_restrictions(RESTRICTION_TABLE)
    assert restrictions[SOLEMN_JUDGMENT] == 1
    with pytest.raises(ValueError, match="copy limit 1"):
        validate_edison_deck(
            Decklist((SOLEMN_JUDGMENT, SOLEMN_JUDGMENT, *VANILLA_DECK[2:])),
            PROBE_ELIGIBLE_IDS, restrictions, root / "database/cards.cdb")
    own_deck = Path("examples/decks/mr1_junk_warrior_probe.ydk")
    other_deck = tmp_path / "solemn.ydk"
    other_deck.write_text("#main\n" + "\n".join(map(str, (
        SOLEMN_JUDGMENT, *VANILLA_DECK[1:]
    ))) + "\n#extra\n!side\n")
    results = {}
    for negate in (False, True):
        with GoatEnvironment(str(own_deck), str(other_deck), seed=52,
                             engine=Mr1SynchroProbeEngine(root)) as env:
            view = env.reset()
            completed = set()
            offered_at = resolved = None
            agents = (RandomAgent(52), RandomAgent(53))
            for index in range(3000):
                if env.is_terminal():
                    break
                actions = env.legal_actions()
                action = None
                if resolved is None:
                    for step in SETUP:
                        turn, seat, kind, code = step
                        if step in completed or (view.turn, view.acting_player) != (turn, seat):
                            continue
                        action = next((candidate for candidate in actions
                                       if candidate.kind == kind
                                       and candidate.parameters.get("code") == code), None)
                        if action is not None:
                            if step == SETUP[2]:
                                hidden = env.engine.probe.observation(0)
                                assert any(card.controller == 1
                                           and card.zone == "spell_trap"
                                           and card.position == "facedown"
                                           and card.code is None
                                           for card in hidden.field)
                            completed.add(step)
                            break
                    if len(completed) == len(SETUP) and offered_at is None \
                            and view.acting_player == 1:
                        solemn = next((candidate for candidate in actions
                                       if candidate.kind == "chain"
                                       and candidate.parameters.get("code")
                                       == SOLEMN_JUDGMENT), None)
                        if solemn is not None:
                            offered_at = index
                            action = solemn if negate else next(
                                candidate for candidate in actions
                                if candidate.kind == "pass")
                    if action is None:
                        action = next((candidate for kind in (
                            "place", "pass", "end_phase", "yes", "select_card")
                            for candidate in actions if candidate.kind == kind), actions[0])
                else:
                    action = agents[view.acting_player].select_action(view, actions)
                view = env.step(action)
                if offered_at is not None and resolved is None and index > offered_at \
                        and not view.chain:
                    resolved = index + 1
                    assert view.life_points == ((8000, 4000) if negate
                                                else (8000, 8000))
                    assert BOKOICHI in {card.code for card in view.graveyards[0]}
                    assert JUNK_SYNCHRON in {card.code for card in view.graveyards[0]}
                    if negate:
                        assert JUNK_WARRIOR in {card.code for card in view.graveyards[0]}
                        assert not any(card.code == JUNK_WARRIOR for card in view.field)
                    else:
                        assert any(card.code == JUNK_WARRIOR for card in view.field)
                        assert JUNK_WARRIOR not in {
                            card.code for card in view.graveyards[0]}
            else:
                pytest.fail("MR1 Solemn Judgment duel exceeded decision cap")
            assert env.is_terminal()
            assert completed == set(SETUP)
            assert offered_at is not None and resolved is not None
            assert env.engine.probe.loaded_script_sha256[
                f"official/c{SOLEMN_JUDGMENT}.lua"] == hashlib.sha256(
                    script.read_bytes()).hexdigest()
            trajectory = env.trajectory()
            path = tmp_path / f"solemn_{negate}.json"
            write_trajectory(path, trajectory)
            loaded = read_trajectory(path)
            assert loaded == trajectory
            assert verify_trajectory(loaded, Mr1SynchroProbeEngine(root)) == len(
                loaded.decisions)
            assert audit_trajectory_visibility(loaded)["decisions"] == len(
                loaded.decisions)
            results[negate] = (trajectory, offered_at)
    assert results[False][1] == results[True][1]
    assert results[False][0].decisions[:results[False][1]] == (
        results[True][0].decisions[:results[True][1]])
