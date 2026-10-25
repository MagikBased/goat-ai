"""Face-up Thousand-Eyes Restrict prevents attacks by other monsters."""

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
@pytest.mark.parametrize("set_restrict", [False, True])
def test_restrict_attack_lock_lifts_after_book_sets_it(tmp_path, set_restrict):
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
        first_summon = second_summon = booked = book_target = False
        battle_entered = False
        first_code = second_code = None
        for _ in range(110):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not goat:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                goat |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not first_summon:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    first_code = action.parameters["code"]
                    first_summon = True
            if obs.turn == 3 and obs.acting_player == 0 and not meta:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == METAMORPHOSIS), action)
                meta |= action is not None and action.kind == "activate"
            if meta and not token and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               in SHEEP_CODES and a.parameters.get("controller") == 0), action)
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
                               == first_code and a.parameters.get("controller") == 1),
                              action)
                target |= action is not None and action.kind == "select_card"
            if obs.turn == 4 and obs.acting_player == 1:
                if not second_summon:
                    action = next((a for a in actions if a.kind == "normal_summon"), action)
                    if action is not None and action.kind == "normal_summon":
                        second_code = action.parameters["code"]
                        second_summon = True
                if second_summon and not booked and set_restrict \
                        and action is None and obs.phase == "main1":
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == BOOK), None)
                    booked |= action is not None
                if booked and not book_target and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == RESTRICT and a.parameters.get("controller") == 0),
                                  action)
                    book_target |= action is not None and action.kind == "select_card"
                if second_summon and (not set_restrict or book_target) \
                        and not battle_entered and action is None:
                    option = next((a for a in actions if a.kind == "battle_phase"), None)
                    if option is not None:
                        action = option
                        battle_entered = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if battle_entered and obs.turn == 4 and obs.acting_player == 1 \
                    and obs.phase == "battle_start":
                own = env.engine.probe.observation(1)
                opponent = env.engine.probe.observation(0)
                assert first_summon and target and second_summon
                assert second_code in {c.code for c in own.field if c.zone == "monster"}
                restrict_card = next(c for c in opponent.field if c.code == RESTRICT)
                assert restrict_card.position == (
                    "facedown" if set_restrict else "faceup")
                attack_options = [a for a in env.legal_actions() if a.kind == "attack"]
                assert bool(attack_options) == set_restrict
                if set_restrict:
                    assert booked and book_target
                    assert first_code in {c.code for c in own.graveyards[1]}
                    assert first_code not in {c.code for c in own.field}
                    assert BOOK in {c.code for c in own.graveyards[1]}
                else:
                    assert not booked
                    assert first_code in {c.code for c in own.field
                                          if c.zone == "spell_trap"}
                    assert BOOK in {c.code for c in own.hand}
                assert own.life_points == (8000, 8000)
                assert {f"goat/c{SCAPEGOAT}.lua", f"official/c{METAMORPHOSIS}.lua",
                        f"goat/c{RESTRICT}.lua"} \
                    <= env.engine.probe.loaded_script_sha256.keys()
                if set_restrict:
                    assert f"official/c{BOOK}.lua" in \
                        env.engine.probe.loaded_script_sha256
                return
    pytest.fail("Restrict attack-lock battle decision not reached")
