"""Morphing Jar's five-card draw can end a duel before the next Draw Phase."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

MORPHING_JAR = 33508719
EXTRA_VANILLAS = (
    32864, 549481, 1184620, 1761063, 1784619, 2118022, 2311603, 2468169,
    2483611, 2863439, 2964201, 3134241, 3170832, 3573512, 3797883,
    4035199, 4042268, 4179849, 4920010, 5265750,
)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("short_player,remaining,seed", [
    (0, 4, 3), (0, 5, 3), (1, 4, 5), (1, 5, 5),
])
def test_morphing_jar_near_empty_deck_terminal_timing(
        tmp_path, short_player, remaining, seed):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    script = f"official/c{MORPHING_JAR}.lua"
    if not (root / "scripts" / script).is_file():
        pytest.skip("Morphing Jar script not installed")
    jar_deck = tmp_path / "jar.ydk"
    jar_cards = ((MORPHING_JAR, *VANILLA_DECK[1:]) if short_player == 0
                 else (MORPHING_JAR, *VANILLA_DECK, *EXTRA_VANILLAS[:-1]))
    jar_deck.write_text("#main\n" + "\n".join(map(str, jar_cards))
                        + "\n#extra\n!side\n")
    other_deck = tmp_path / "other.ydk"
    other_cards = (VANILLA_DECK + EXTRA_VANILLAS
                   if short_player == 0 else VANILLA_DECK)
    other_deck.write_text("#main\n" + "\n".join(map(str, other_cards))
                          + "\n#extra\n!side\n")
    with GoatEnvironment(str(jar_deck), str(other_deck), seed=seed,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert MORPHING_JAR in {card.code for card in obs.hand}
        jar_set = jar_flipped = emptied = False
        for _ in range(700):
            if env.is_terminal():
                assert jar_flipped
                assert env.result() == 1 - short_player
                assert obs.deck_counts[short_player] == 0
                assert obs.deck_counts[1 - short_player] > 0
                assert obs.phase == ("main1" if remaining == 4 else "draw")
                assert obs.life_points == (8000, 8000)
                assert emptied == (remaining == 5)
                assert script in env.engine.probe.loaded_script_sha256
                path = tmp_path / f"jar_deckout_{short_player}_{remaining}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                                             env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.acting_player == 0 and obs.phase == "main1":
                if not jar_set:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == MORPHING_JAR), None)
                    jar_set |= action is not None
                if jar_set and not jar_flipped \
                        and obs.deck_counts[short_player] == remaining \
                        and action is None \
                        and any(a.kind == "end_phase" for a in actions):
                    action = next((a for a in actions if a.kind == "flip_summon"
                                   and a.parameters.get("code") == MORPHING_JAR), None)
                    assert action is not None
                    jar_flipped = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "end_phase", "pass")), actions[0])
            obs = env.step(action)
            if jar_flipped and remaining == 5 \
                    and obs.deck_counts[short_player] == 0 \
                    and not emptied:
                assert not env.is_terminal()
                emptied = True
    pytest.fail("Morphing Jar did not reach the deck-out boundary")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("remaining,expected_winner", [(4, None), (5, 0)])
def test_morphing_jar_equal_decks_terminal_order(tmp_path, remaining, expected_winner):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    script = f"official/c{MORPHING_JAR}.lua"
    if not (root / "scripts" / script).is_file():
        pytest.skip("Morphing Jar script not installed")
    jar_deck = tmp_path / "jar_41.ydk"
    jar_deck.write_text("#main\n" + "\n".join(map(str, (
        MORPHING_JAR, *VANILLA_DECK))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(jar_deck), "examples/decks/vanilla_probe.ydk", seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert MORPHING_JAR in {card.code for card in obs.hand}
        assert obs.deck_counts == (35, 35)
        jar_set = jar_flipped = emptied = False
        for _ in range(700):
            if env.is_terminal():
                assert jar_flipped
                assert env.result() == expected_winner
                assert obs.deck_counts == (0, 0)
                assert obs.life_points == (8000, 8000)
                assert obs.phase == ("main1" if remaining == 4 else "draw")
                assert emptied == (remaining == 5)
                assert script in env.engine.probe.loaded_script_sha256
                path = tmp_path / f"jar_equal_decks_{remaining}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                                             env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.acting_player == 0 and obs.phase == "main1":
                if not jar_set:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == MORPHING_JAR), None)
                    jar_set |= action is not None
                if jar_set and not jar_flipped \
                        and obs.deck_counts == (remaining, remaining) \
                        and action is None \
                        and any(a.kind == "end_phase" for a in actions):
                    action = next((a for a in actions if a.kind == "flip_summon"
                                   and a.parameters.get("code") == MORPHING_JAR), None)
                    assert action is not None
                    jar_flipped = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "end_phase", "pass")), actions[0])
            obs = env.step(action)
            if jar_flipped and remaining == 5 and obs.deck_counts == (0, 0) \
                    and not emptied:
                assert not env.is_terminal()
                emptied = True
    pytest.fail("Morphing Jar did not reach the equal-Deck draw boundary")
