"""Book of Moon resets a previously Summoned Restrict's equip effect."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SCAPEGOAT = 504700123
METAMORPHOSIS = 46411259
RESTRICT = 504700102
BOOK = 14087893
SHEEP_CODES = {73915052, 73915053, 73915054, 73915055}


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_book_reset_allows_second_restrict_equip_same_turn(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{SCAPEGOAT}.lua", f"official/c{METAMORPHOSIS}.lua",
               f"goat/c{RESTRICT}.lua", f"official/c{BOOK}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    attacker = tmp_path / "restrict_book.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        *([SCAPEGOAT] * 3), *([METAMORPHOSIS] * 3), *([BOOK] * 3),
        *VANILLA_DECK[9:]))) + f"\n#extra\n{RESTRICT}\n!side\n")
    defender = tmp_path / "sheep.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        *([SCAPEGOAT] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=70,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {SCAPEGOAT, METAMORPHOSIS, BOOK} <= {card.code for card in obs.hand}
        own_goat = other_goat = meta = own_token = fusion = False
        first_effect = first_target = first_equipped = book = book_target = False
        flipped = second_effect = second_target = False
        first_slot = second_slot = None
        for _ in range(160):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not own_goat:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                own_goat |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not other_goat:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                other_goat |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not meta:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == METAMORPHOSIS), action)
                meta |= action is not None and action.kind == "activate"
            if meta and not own_token and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               in SHEEP_CODES and a.parameters.get("controller") == 0), None)
                own_token |= action is not None
            if own_token and not fusion and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == RESTRICT),
                              None)
                fusion |= action is not None
            if obs.turn == 5 and obs.acting_player == 0 and fusion:
                if not first_effect:
                    action = next((a for a in actions if a.kind in ("activate", "chain")
                                   and a.parameters.get("code") == RESTRICT), None)
                    first_effect |= action is not None
                if first_effect and not first_target and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("controller") == 1
                                   and a.parameters.get("code") in SHEEP_CODES), None)
                    if action is not None:
                        first_slot = action.parameters["sequence"]
                        first_target = True
                if first_target and not obs.chain and not first_equipped:
                    restrict = next(c for c in obs.field if c.code == RESTRICT)
                    equipped = [c for c in obs.field if c.zone == "spell_trap"
                                and c.controller == 0 and c.equipped_to == (
                                    0, restrict.sequence)]
                    if equipped:
                        first_equipped = True
                        assert len(equipped) == 1
                        assert not any(a.kind in ("activate", "chain")
                                       and a.parameters.get("code") == RESTRICT
                                       for a in actions)
                if first_equipped and not book:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == BOOK), None)
                    book |= action is not None
                if book and not book_target and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == RESTRICT
                                   and a.parameters.get("controller") == 0), None)
                    book_target |= action is not None
                if book_target and not obs.chain and not flipped:
                    restrict = next(c for c in obs.field if c.code == RESTRICT)
                    assert restrict.position == "facedown"
                    assert BOOK in {c.code for c in obs.graveyards[0]}
                    assert not any(c.zone == "spell_trap" and c.equipped_to == (
                        0, restrict.sequence) for c in obs.field)
                    assert sum(c.code in SHEEP_CODES for c in obs.field
                               if c.controller == 1 and c.zone == "monster") == 3
                    action = next((a for a in actions if a.kind == "flip_summon"
                                   and a.parameters.get("code") == RESTRICT), None)
                    flipped |= action is not None
                if flipped and not second_effect and action is None:
                    action = next((a for a in actions if a.kind in ("activate", "chain")
                                   and a.parameters.get("code") == RESTRICT), None)
                    second_effect |= action is not None
                if second_effect and not second_target and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("controller") == 1
                                   and a.parameters.get("code") in SHEEP_CODES
                                   and a.parameters.get("sequence") != first_slot), None)
                    if action is not None:
                        second_slot = action.parameters["sequence"]
                        second_target = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if second_target and not obs.chain and obs.turn == 5:
                assert first_equipped and book and book_target and flipped
                assert first_slot != second_slot
                restrict = next(c for c in obs.field if c.code == RESTRICT)
                assert restrict.position == "faceup"
                assert any(c.zone == "spell_trap" and c.controller == 0
                           and c.equipped_to == (0, restrict.sequence) for c in obs.field)
                assert sum(c.code in SHEEP_CODES for c in obs.field
                           if c.controller == 1 and c.zone == "monster") == 2
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                agents = (RandomAgent(70), RandomAgent(71))
                for _ in range(3000):
                    if env.is_terminal():
                        break
                    obs = env.step(agents[obs.acting_player].select_action(
                        obs, env.legal_actions()))
                else:
                    pytest.fail("Restrict / Book continuation exceeded 3000 decisions")
                trajectory = env.trajectory()
                assert trajectory.schema_version == 21
                path = tmp_path / "restrict_book_reset.json"
                write_trajectory(path, trajectory)
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                                             trajectory.decisions)
                return
    pytest.fail(f"Restrict reset stalled: turn={obs.turn} phase={obs.phase} "
                f"goats={own_goat}/{other_goat} meta={meta}/{own_token}/{fusion} "
                f"first={first_effect}/{first_target}/{first_equipped} "
                f"book={book}/{book_target} flip={flipped} "
                f"second={second_effect}/{second_target}")
