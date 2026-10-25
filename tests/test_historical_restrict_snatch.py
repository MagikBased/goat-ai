"""Snatch Steal, Book of Moon, and an equipped Thousand-Eyes Restrict."""

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
SNATCH = 45986603
BOOK = 14087893


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("book_timing", ["none", "after", "chain"])
def test_snatch_steals_equipped_restrict(tmp_path, book_timing):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{SCAPEGOAT}.lua", f"official/c{METAMORPHOSIS}.lua",
               f"goat/c{RESTRICT}.lua", f"official/c{SNATCH}.lua"}
    if book_timing != "none":
        scripts.add(f"official/c{BOOK}.lua")
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    owner = tmp_path / "restrict.ydk"
    owner_cards = [*((SCAPEGOAT, METAMORPHOSIS) * 3), *VANILLA_DECK[6:]]
    if book_timing == "chain":
        owner_cards[8] = BOOK
    owner.write_text("#main\n" + "\n".join(map(str, owner_cards))
        + f"\n#extra\n{RESTRICT}\n!side\n")
    stealer = tmp_path / "snatch.ydk"
    stealer_cards = [SNATCH, *VANILLA_DECK[1:]]
    if book_timing == "after":
        stealer_cards[6] = BOOK
    stealer.write_text("#main\n" + "\n".join(map(str, stealer_cards))
                       + "\n#extra\n!side\n")

    with GoatEnvironment(str(owner), str(stealer),
                         seed=237 if book_timing == "chain" else 52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {SCAPEGOAT, METAMORPHOSIS} <= {c.code for c in obs.hand}
        if book_timing == "chain":
            assert BOOK in {c.code for c in obs.hand}
        assert SNATCH in {c.code for c in env.engine.probe.observation(1).hand}
        if book_timing == "after":
            assert BOOK in {c.code for c in env.engine.probe.observation(1).hand}
        goat = defender_summoned = meta = token = fusion = effect = target = False
        equipped = snatch = snatch_target = False
        book_set = control_checked = book_used = book_targeted = False
        defender_code = None
        for _ in range(130):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not goat:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                goat |= action is not None
            if book_timing == "chain" and obs.turn == 1 and obs.acting_player == 0 \
                    and goat and not book_set and action is None:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == BOOK), None)
                book_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not defender_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    defender_code = action.parameters["code"]
                    defender_summoned = True
            if obs.turn == 3 and obs.acting_player == 0:
                if not meta:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == METAMORPHOSIS), action)
                    meta |= action is not None and action.kind == "activate"
                if meta and not token and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("controller") == 0
                                   and a.parameters.get("code") in
                                   {73915052, 73915053, 73915054, 73915055}), action)
                    token |= action is not None and action.kind == "select_card"
                if token and not fusion and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == RESTRICT),
                                  action)
                    fusion |= action is not None and action.kind == "select_card"
                if fusion and not effect:
                    action = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == RESTRICT), action)
                    effect |= action is not None and action.kind == "chain"
                if effect and not target and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("controller") == 1
                                   and a.parameters.get("code") == defender_code), action)
                    target |= action is not None and action.kind == "select_card"
            if target and not obs.chain and obs.turn == 3:
                equipped |= any(c.code == defender_code and c.zone == "spell_trap"
                                and c.controller == 0 for c in obs.field)
            if book_timing == "chain" and snatch_target and obs.acting_player == 0 \
                    and not book_used:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK), action)
                book_used |= action is not None and action.kind == "chain"
            if book_timing == "chain" and book_used and not book_targeted \
                    and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == RESTRICT
                               and a.parameters.get("controller") == 0), action)
                book_targeted |= action is not None and action.kind == "select_card"
            if obs.turn == 4 and obs.acting_player == 1 and equipped:
                if not snatch:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == SNATCH), None)
                    snatch |= action is not None
                if snatch and not snatch_target and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == RESTRICT
                                   and a.parameters.get("controller") == 0), action)
                    snatch_target |= action is not None and action.kind == "select_card"
                if book_timing == "after" and control_checked and not book_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == BOOK), action)
                    book_used |= action is not None and action.kind == "activate"
                if book_timing == "after" and book_used and not book_targeted \
                        and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") == RESTRICT
                                   and a.parameters.get("controller") == 1), action)
                    book_targeted |= action is not None and action.kind == "select_card"
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if book_timing != "chain" and snatch_target and not control_checked \
                    and not obs.chain and obs.turn == 4:
                restrict = next(c for c in obs.field if c.code == RESTRICT)
                assert restrict.controller == 1 and restrict.position == "faceup"
                assert any(c.code == defender_code and c.zone == "spell_trap"
                           and c.controller == 0
                           and c.equipped_to == (1, restrict.sequence) for c in obs.field)
                assert any(c.code == SNATCH and c.zone == "spell_trap"
                           and c.controller == 1
                           and c.equipped_to == (1, restrict.sequence) for c in obs.field)
                assert obs.life_points == (8000, 8000)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                control_checked = True
            ready = (control_checked and book_timing == "none"
                     or book_targeted and not obs.chain and obs.turn == 4)
            if ready:
                if book_timing == "after":
                    stealer_view = env.engine.probe.observation(1)
                    restrict = next(c for c in stealer_view.field if c.code == RESTRICT)
                    assert restrict.controller == 1 and restrict.position == "facedown"
                    assert SNATCH in {c.code for c in stealer_view.graveyards[1]}
                    assert BOOK in {c.code for c in stealer_view.graveyards[1]}
                    assert defender_code in {c.code for c in stealer_view.graveyards[1]}
                    assert not any(c.code == defender_code and c.zone == "spell_trap"
                                   for c in stealer_view.field)
                    owner_view = env.engine.probe.observation(0)
                    hidden = next(c for c in owner_view.field if c.zone == "monster"
                                  and c.controller == 1 and c.sequence == restrict.sequence)
                    assert hidden.code is None and hidden.position == "facedown"
                    assert (1, "monster", hidden.sequence, RESTRICT) in {
                        (c.controller, c.zone, c.sequence, c.code)
                        for c in owner_view.known_opponent_field_cards}
                elif book_timing == "chain":
                    owner_view = env.engine.probe.observation(0)
                    restrict = next(c for c in owner_view.field if c.code == RESTRICT)
                    assert book_set and book_used and book_targeted
                    assert restrict.controller == 0 and restrict.position == "facedown"
                    assert SNATCH in {c.code for c in owner_view.graveyards[1]}
                    assert BOOK in {c.code for c in owner_view.graveyards[0]}
                    assert defender_code in {c.code for c in owner_view.graveyards[1]}
                    assert not any(c.code in {SNATCH, defender_code}
                                   and c.zone == "spell_trap" for c in owner_view.field)
                    stealer_view = env.engine.probe.observation(1)
                    hidden = next(c for c in stealer_view.field if c.zone == "monster"
                                  and c.controller == 0 and c.sequence == restrict.sequence)
                    assert hidden.code is None and hidden.position == "facedown"
                    assert (0, "monster", hidden.sequence, RESTRICT) in {
                        (c.controller, c.zone, c.sequence, c.code)
                        for c in stealer_view.known_opponent_field_cards}
                agents = (RandomAgent(52), RandomAgent(53))
                for _ in range(3000):
                    if env.is_terminal():
                        break
                    obs = env.step(agents[obs.acting_player].select_action(
                        obs, env.legal_actions()))
                else:
                    pytest.fail("Restrict / Snatch continuation exceeded 3000 decisions")
                trajectory = env.trajectory()
                path = tmp_path / f"restrict_snatch_{book_timing}.json"
                write_trajectory(path, trajectory)
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                                             trajectory.decisions)
                return
        pytest.fail(f"Restrict / Snatch line stalled: goat={goat} "
                    f"summon={defender_summoned} meta={meta}/{token}/{fusion} "
                    f"effect={effect}/{target}/{equipped} snatch={snatch}/{snatch_target} "
                    f"book={book_set}/{book_used}/{book_targeted} "
                    f"turn={obs.turn} phase={obs.phase}")
