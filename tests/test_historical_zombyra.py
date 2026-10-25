"""GOAT Zombyra loses ATK after battle, cannot attack directly, and resets."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

ZOMBYRA = 504700152
BOOK_OF_MOON = 14087893
MYSTICAL_ELF = 15025844


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("reset_with_book", [False, True])
def test_zombyra_battle_reduction_direct_lock_and_book_reset(tmp_path,
                                                              reset_with_book):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{ZOMBYRA}.lua", f"official/c{BOOK_OF_MOON}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("GOAT Zombyra / Book of Moon scripts not installed")
    own = tmp_path / "zombyra.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        ZOMBYRA, BOOK_OF_MOON, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), "examples/decks/vanilla_probe.ydk", seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {ZOMBYRA, BOOK_OF_MOON} <= {c.code for c in obs.hand}
        assert MYSTICAL_ELF in {
            c.code for c in env.engine.probe.observation(1).hand}
        zombyra_summoned = elf_summoned = attacked = battle_resolved = False
        book_used = book_targeted = flipped = battle_checked = False
        for _ in range(125):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not zombyra_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == ZOMBYRA), None)
                zombyra_summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not elf_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == MYSTICAL_ELF), None)
                elf_summoned |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not attacked:
                if obs.phase == "main1":
                    action = next((a for a in actions if a.kind == "battle_phase"),
                                  action)
                elif obs.phase in ("battle_start", "battle_step"):
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == ZOMBYRA), action)
                    attacked |= action is not None and action.kind == "attack"
            if attacked and not battle_resolved and obs.turn == 3 \
                    and obs.acting_player == 0 and obs.phase == "battle_step" \
                    and any(a.kind == "main2" for a in actions):
                assert obs.life_points == (8000, 6700)
                assert MYSTICAL_ELF in {c.code for c in obs.graveyards[1]}
                zombyra = next(c for c in obs.field if c.code == ZOMBYRA)
                assert zombyra.attack == 1900 and zombyra.position == "faceup"
                battle_resolved = True
            if battle_resolved and reset_with_book and not book_used \
                    and obs.turn == 3 and obs.acting_player == 0 \
                    and obs.phase == "main2":
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == BOOK_OF_MOON), action)
                book_used |= action is not None and action.kind == "activate"
            if book_used and not book_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == ZOMBYRA and a.parameters.get("controller") == 0), None)
                assert action is not None
                book_targeted = True
            if book_targeted and obs.turn == 3 and obs.acting_player == 0 \
                    and not obs.chain:
                zombyra = next(c for c in obs.field if c.code == ZOMBYRA)
                assert zombyra.position == "facedown"
            if obs.turn == 5 and obs.acting_player == 0 and reset_with_book \
                    and not flipped:
                action = next((a for a in actions if a.kind == "flip_summon"
                               and a.parameters.get("code") == ZOMBYRA), action)
                flipped |= action is not None and action.kind == "flip_summon"
            if obs.turn == 5 and obs.acting_player == 0 and obs.phase == "main1" \
                    and (not reset_with_book or flipped) and not battle_checked \
                    and action is None:
                action = next((a for a in actions if a.kind == "battle_phase"), None)
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "main2", "end_phase")), actions[0])
            obs = env.step(action)
            if obs.turn == 5 and obs.acting_player == 0 \
                    and obs.phase == "battle_start" and not battle_checked:
                zombyra = next(c for c in obs.field if c.code == ZOMBYRA)
                assert zombyra.attack == (2100 if reset_with_book else 1900)
                assert zombyra.position == "faceup"
                assert not any(c.zone == "monster" and c.controller == 1
                               for c in obs.field)
                assert not any(a.kind == "attack" for a in env.legal_actions())
                assert obs.life_points == (8000, 6700)
                required = (scripts if reset_with_book else
                            {f"goat/c{ZOMBYRA}.lua"})
                assert required <= env.engine.probe.loaded_script_sha256.keys()
                battle_checked = True
                agents = (RandomAgent(52), RandomAgent(53))
                for _ in range(5000):
                    obs = env.step(agents[obs.acting_player].select_action(
                        obs, env.legal_actions()))
                    if env.is_terminal():
                        path = tmp_path / f"zombyra_{reset_with_book}.json"
                        write_trajectory(path, env.trajectory())
                        assert verify_trajectory(read_trajectory(path),
                                                 ExperimentalOcgcoreEngine(root)) == len(
                                                     env.trajectory().decisions)
                        return
                pytest.fail("Zombyra duel did not finish")
    pytest.fail("Zombyra did not reach post-reset Battle Phase")
