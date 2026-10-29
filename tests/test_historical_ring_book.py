"""Book of Moon can remove Ring of Destruction's face-up target."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

RING = 511000824  # pre-errata GOAT variant
BOOK = 14087893
ARCHFIEND_SOLDIER = 49881766


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_book", [False, True])
def test_book_chained_to_ring_protects_face_up_monster(tmp_path, chain_book):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"scripts/pre-errata/c{RING}.lua",
                     f"scripts/official/c{BOOK}.lua"):
        if not (root / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    monster_deck = tmp_path / "monster.ydk"
    monster_deck.write_text("#main\n" + "\n".join(map(str, (
        ARCHFIEND_SOLDIER, BOOK, BOOK, BOOK,
        *tuple(code for code in VANILLA_DECK if code != ARCHFIEND_SOLDIER)[:36])))
        + "\n#extra\n!side\n")
    ring_deck = tmp_path / "ring.ydk"
    ring_deck.write_text("#main\n" + "\n".join(map(str, (
        RING, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(monster_deck), str(ring_deck), seed=316,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        summoned = book_set = ring_set = ring_used = ring_targeted = False
        book_chained = book_targeted = False
        resolved = False
        for _ in range(80):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == ARCHFIEND_SOLDIER), None)
                    summoned |= action is not None
                if action is None and summoned and not book_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOOK), None)
                    book_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not ring_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == RING), None)
                ring_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 1 and ring_set and not ring_used:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == RING), None)
                ring_used |= action is not None
            if ring_used and not ring_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == ARCHFIEND_SOLDIER), None)
                ring_targeted |= action is not None
            if chain_book and ring_targeted and obs.acting_player == 0 \
                    and not book_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK), None)
                book_chained |= action is not None
            if book_chained and not book_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == ARCHFIEND_SOLDIER), None)
                book_targeted |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if ring_targeted and RING in {c.code for c in obs.graveyards[1]}:
                assert obs.chain == ()
                assert summoned and book_set and ring_set and ring_used
                owner = env.engine.probe.observation(0)
                opponent = env.engine.probe.observation(1)
                if chain_book:
                    assert book_chained and book_targeted
                    assert obs.life_points == (8000, 8000)
                    assert BOOK in {c.code for c in obs.graveyards[0]}
                    assert any(c.code == ARCHFIEND_SOLDIER and c.position == "facedown"
                               for c in owner.field)
                    assert any(c.controller == 0 and c.zone == "monster"
                               and c.position == "facedown" and c.code is None
                               for c in opponent.field)
                    assert not any(c.code == ARCHFIEND_SOLDIER for c in owner.graveyards[0])
                else:
                    assert not book_chained
                    assert obs.life_points == (6100, 6100)
                    assert ARCHFIEND_SOLDIER in {c.code for c in obs.graveyards[0]}
                loaded = env.engine.probe.loaded_script_sha256
                assert f"pre-errata/c{RING}.lua" in loaded
                if chain_book:
                    assert f"official/c{BOOK}.lua" in loaded
                resolved = True
                break
        assert resolved, "Ring / Book response did not resolve"
        agents = (RandomAgent(316), RandomAgent(317))
        for _ in range(3000):
            if env.is_terminal():
                break
            action = agents[obs.acting_player].select_action(obs, env.legal_actions())
            obs = env.step(action)
        assert env.is_terminal(), "Ring / Book continuation did not finish"
        path = tmp_path / f"ring_book_{chain_book}.json"
        write_trajectory(path, env.trajectory())
        saved = read_trajectory(path)
        assert verify_trajectory(saved, ExperimentalOcgcoreEngine(root)) == len(saved.decisions)
        audit_trajectory_visibility(saved)
