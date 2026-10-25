"""Common BLS attack lines against Mirror Force and Book of Moon."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

BLS = 504700118
GRACEFUL = 79571449
MIRROR_FORCE = 44095762
BOOK = 14087893
LIGHT = 15025844
DARK = 7359741


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("save_with_book", [False, True])
def test_mirror_force_destroys_attacking_bls_unless_book_sets_it(tmp_path, save_with_book):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{BLS}.lua", f"official/c{GRACEFUL}.lua",
                     f"official/c{MIRROR_FORCE}.lua", f"official/c{BOOK}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    lights = (LIGHT, 62651957)
    darks = (49881766, DARK)
    filler = [code for code in VANILLA_DECK if code not in (*lights, *darks)]
    filler[3] = BOOK
    attacker = tmp_path / "bls.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL, BLS, *(code for code in lights for _ in range(3)),
        *(code for code in darks for _ in range(3)), *filler[:26])))
        + "\n#extra\n!side\n")
    defender = tmp_path / "mirror.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        MIRROR_FORCE, *VANILLA_DECK[1:])))
        + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, BLS, BOOK, LIGHT, DARK}.issubset(c.code for c in obs.hand)
        assert MIRROR_FORCE in {c.code for c in env.engine.probe.observation(1).hand}
        graceful = discarded = summoned = mirror_set = attacked = False
        mirror_chained = book_chained = book_targeted = False
        costs = set()
        for _ in range(100):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not graceful:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == GRACEFUL), None)
                graceful |= action is not None
            if graceful and not discarded and actions[0].kind == "select_cards":
                action = next((a for a in actions if {c["code"] for c in
                               a.parameters["cards"]} == {LIGHT, DARK}), None)
                discarded |= action is not None
            if discarded and not summoned and obs.turn == 1 and action is None:
                action = next((a for a in actions if a.kind == "special_summon"
                               and a.parameters.get("code") == BLS), None)
                summoned |= action is not None
            if summoned and len(costs) < 2 and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               in ({LIGHT, DARK} - costs)), None)
                if action is not None:
                    costs.add(action.parameters["code"])
            if obs.turn == 2 and obs.acting_player == 1 and not mirror_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == MIRROR_FORCE), action)
                mirror_set |= action is not None and action.kind == "set_spell_trap"
            if obs.turn == 3 and obs.acting_player == 0 and mirror_set and not attacked:
                action = next((a for a in actions if a.kind in ("battle_phase", "attack")
                               and (a.kind != "attack" or
                                    a.parameters.get("code") == BLS)), action)
                attacked |= action is not None and action.kind == "attack"
            if attacked and obs.acting_player == 1 and not mirror_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == MIRROR_FORCE), action)
                mirror_chained |= action is not None and action.kind == "chain"
            if save_with_book and mirror_chained and obs.acting_player == 0 \
                    and not book_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK), action)
                book_chained |= action is not None and action.kind == "chain"
            if book_chained and not book_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == BLS
                               and a.parameters.get("controller") == 0), None)
                book_targeted |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if mirror_chained and any(c.code == MIRROR_FORCE for c in obs.graveyards[1]):
                assert costs == {LIGHT, DARK}
                assert {c.code for c in obs.banished[0]} == {LIGHT, DARK}
                assert obs.life_points == (8000, 8000)
                assert not any(a.kind == "yes" and a.parameters.get("code") == BLS
                               for a in env.legal_actions())
                if save_with_book:
                    assert book_chained and book_targeted
                    assert any(c.code == BLS and c.position == "facedown"
                               for c in env.engine.probe.observation(0).field)
                    assert not any(c.code == BLS for c in obs.graveyards[0])
                    assert any(c.code == BOOK for c in obs.graveyards[0])
                else:
                    assert not book_chained
                    assert any(c.code == BLS for c in obs.graveyards[0])
                    assert not any(c.code == BLS for c in obs.field)
                assert {f"goat/c{BLS}.lua", f"official/c{GRACEFUL}.lua",
                        f"official/c{MIRROR_FORCE}.lua"}.issubset(
                            env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("BLS/Mirror Force attack response did not resolve")
