"""Lightning Vortex discards for cost and checks face-up monsters on resolution."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

VORTEX = 69162969
SERPENT = 511000818
BOOK = 14087893
GEMINI = 69140098


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_book", [False, True])
def test_vortex_cost_and_book_response_to_faceup_only_removal(tmp_path, chain_book):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (VORTEX, BOOK)}
    scripts.add(f"pre-errata/c{SERPENT}.lua")
    if any(not (root / "scripts" / relative).is_file() for relative in scripts):
        pytest.skip("required card script not installed")
    attacker = tmp_path / "vortex_serpent.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        VORTEX, SERPENT, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    defender_cards = list(VANILLA_DECK)
    defender_cards[0], defender_cards[6] = defender_cards[6], defender_cards[0]
    for index in (5, 18, 31):
        defender_cards[index] = BOOK
    defender = tmp_path / "gemini_book.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, defender_cards))
                        + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {VORTEX, SERPENT} <= {c.code for c in obs.hand}
        assert {GEMINI, BOOK} <= {c.code for c in env.engine.probe.observation(1).hand}
        elf_summoned = book_set = vortex_used = serpent_spent = False
        book_answered = book_targeted = checked = False
        agents = (RandomAgent(18), RandomAgent(19))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                trajectory = env.trajectory()
                path = tmp_path / f"vortex_book_{chain_book}.json"
                write_trajectory(path, trajectory)
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                                             trajectory.decisions)
                assert audit_trajectory_visibility(trajectory)["decisions"] == len(
                    trajectory.decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1:
                if not elf_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == GEMINI), None)
                    elf_summoned |= action is not None
                elif not book_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOOK), None)
                    book_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and book_set and not vortex_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == VORTEX), None)
                vortex_used |= action is not None
            if vortex_used and not serpent_spent and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == SERPENT
                               and a.parameters.get("location") == 2), None)
                serpent_spent |= action is not None
            if serpent_spent and obs.acting_player == 1 and not book_answered:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK), None)
                if option is not None:
                    assert SERPENT in {c.code for c in obs.graveyards[0]}
                    assert [link.card_code for link in obs.chain] == [VORTEX]
                    action = option if chain_book else next(
                        a for a in actions if a.kind == "pass")
                    book_answered = True
            if chain_book and book_answered and not book_targeted \
                    and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == GEMINI
                               and a.parameters.get("controller") == 1), None)
                book_targeted |= action is not None
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if book_answered and not checked and VORTEX in {
                    c.code for c in obs.graveyards[0]} and not obs.chain:
                assert elf_summoned and book_set and vortex_used and serpent_spent
                assert SERPENT in {c.code for c in obs.graveyards[0]}
                assert obs.life_points == (8000, 8000)
                if chain_book:
                    assert book_targeted
                    assert BOOK in {c.code for c in obs.graveyards[1]}
                    assert GEMINI in {c.code for c in env.engine.probe.observation(1).field}
                    hidden = next(c for c in obs.field if c.controller == 1
                                  and c.zone == "monster")
                    assert hidden.code is None and hidden.position == "facedown"
                    assert GEMINI not in {c.code for c in obs.graveyards[1]}
                    assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                else:
                    assert GEMINI in {c.code for c in obs.graveyards[1]}
                    assert BOOK not in {c.code for c in obs.graveyards[1]}
                    assert not any(c.controller == 1 and c.zone == "monster"
                                   for c in obs.field)
                    assert f"official/c{VORTEX}.lua" in \
                        env.engine.probe.loaded_script_sha256
                checked = True
    pytest.fail("Lightning Vortex chain did not finish")
