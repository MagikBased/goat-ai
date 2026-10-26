"""Name announcements use the public GOAT catalog, never the opponent's hidden deck."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import verify_trajectory

PROHIBITION = 43711255
MIND_CRUSH = 15800838
DARK_DESIGNATOR = 78053598
HEAVY_STORM = 19613556
CHAOS_SORCERER = 9596126
THOUSAND_EYES_RESTRICT = 63519819


def _deck(path: Path, card: int) -> None:
    path.write_text("#main\n" + "\n".join(map(str, (card, *VANILLA_DECK[1:])))
                    + "\n#extra\n!side\n")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("card,includes_spell,includes_fusion", [
    (PROHIBITION, True, True),
    (MIND_CRUSH, True, False),
    (DARK_DESIGNATOR, False, False),
])
def test_announcement_catalog_is_format_bound_and_opponent_independent(
        tmp_path, card, includes_spell, includes_fusion):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck = tmp_path / "announcer.ydk"
    _deck(deck, card)
    catalogs = []
    for opponent in ("examples/decks/vanilla_probe.ydk",
                     "examples/decks/vanilla_reverse.ydk"):
        with GoatEnvironment(str(deck), opponent, 3,
                             ExperimentalOcgcoreEngine(root)) as env:
            observation = env.reset()
            random_agent = RandomAgent(3)
            named = False
            for _ in range(3000):
                legal = env.legal_actions()
                if legal[0].kind == "announce_card" and not named:
                    names = frozenset(action.parameters["code"] for action in legal)
                    catalogs.append(names)
                    assert CHAOS_SORCERER in names
                    assert (HEAVY_STORM in names) == includes_spell
                    assert (THOUSAND_EYES_RESTRICT in names) == includes_fusion
                    assert 504700102 not in names  # GOAT script ID is an alias.
                    assert 73915052 not in names  # Sheep Token is not a printed name.
                    assert observation.acting_player == 0
                    action = next(option for option in legal
                                  if option.parameters["code"] == CHAOS_SORCERER)
                    named = True
                elif not named:
                    action = next((option for option in legal
                                   if option.kind in ("activate", "chain")
                                   and option.parameters.get("code") == card), None)
                    if action is None and card == MIND_CRUSH:
                        action = next((option for option in legal
                                       if option.kind == "set_spell_trap"
                                       and option.parameters.get("code") == card), None)
                    if action is None:
                        action = next((option for option in legal
                                       if option.kind == "place"), None)
                    if action is None:
                        action = next((option for option in legal
                                       if option.kind in ("pass", "end_phase")), legal[0])
                else:
                    action = random_agent.select_action(observation, legal)
                observation = env.step(action)
                if env.is_terminal():
                    trajectory = env.trajectory()
                    assert named
                    assert verify_trajectory(trajectory,
                                             ExperimentalOcgcoreEngine(root)) == len(
                        trajectory.decisions)
                    audit_trajectory_visibility(trajectory)
                    break
            else:
                pytest.fail(f"{card} duel did not terminate")
    assert len(catalogs) == 2 and catalogs[0] == catalogs[1]
