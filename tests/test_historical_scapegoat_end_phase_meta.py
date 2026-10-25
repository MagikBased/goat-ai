"""End Phase Scapegoat sets up next-turn Metamorphosis in Goat Control."""

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
SHEEP_CODES = {73915052, 73915053, 73915054, 73915055}
RESTRICTION = "player0:cannot_summon_this_turn:scapegoat"


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_end_phase_scapegoat_allows_next_turn_metamorphosis(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{SCAPEGOAT}.lua", f"official/c{METAMORPHOSIS}.lua",
               f"goat/c{RESTRICT}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card scripts not installed")
    deck = tmp_path / "end_phase_goat.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        *((SCAPEGOAT, METAMORPHOSIS) * 3), *VANILLA_DECK[6:])))
        + f"\n#extra\n{RESTRICT}\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {SCAPEGOAT, METAMORPHOSIS}.issubset(c.code for c in obs.hand)
        goat_set = opponent_summoned = goat_activated = tokens_seen = False
        next_turn_checked = meta_activated = token_tributed = fusion_chosen = False
        for _ in range(110):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not goat_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                goat_set = action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not opponent_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                opponent_summoned = action is not None
            if (obs.turn == 2 and obs.phase == "end" and obs.acting_player == 0
                    and goat_set and not goat_activated):
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                goat_activated = action is not None
            if goat_activated and obs.turn == 2 and RESTRICTION in obs.restrictions:
                tokens_seen |= sum(c.code in SHEEP_CODES for c in obs.field) == 4
            if (obs.turn == 3 and obs.phase == "main1" and obs.acting_player == 0
                    and tokens_seen and not next_turn_checked
                    and any(a.kind == "activate" for a in actions)):
                assert RESTRICTION not in obs.restrictions
                assert any(a.kind == "normal_summon" for a in actions)
                assert sum(c.code in SHEEP_CODES for c in obs.field) == 4
                assert any(a.kind == "activate"
                           and a.parameters.get("code") == METAMORPHOSIS for a in actions)
                next_turn_checked = True
            if next_turn_checked and not meta_activated:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == METAMORPHOSIS), action)
                meta_activated = action is not None and action.kind == "activate"
            if meta_activated and not token_tributed and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") in SHEEP_CODES
                               and a.parameters.get("controller") == 0), None)
                token_tributed = action is not None
            if token_tributed and not fusion_chosen and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == RESTRICT),
                              None)
                fusion_chosen = action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "end_phase", "pass")), actions[0])
            obs = env.step(action)
            if fusion_chosen and any(c.code == RESTRICT and c.zone == "monster"
                                     for c in obs.field):
                assert goat_set and opponent_summoned and goat_activated
                assert tokens_seen and next_turn_checked and meta_activated and token_tributed
                assert sum(c.code in SHEEP_CODES for c in obs.field) == 3
                assert RESTRICTION not in obs.restrictions
                assert SCAPEGOAT in {c.code for c in obs.graveyards[0]}
                assert METAMORPHOSIS in {c.code for c in obs.graveyards[0]}
                assert obs.extra_deck_counts[0] == 0
                assert scripts.issubset(env.engine.probe.loaded_script_sha256)
                agents = (RandomAgent(52), RandomAgent(53))
                for _ in range(3000):
                    if env.is_terminal():
                        break
                    legal = env.legal_actions()
                    obs = env.step(agents[obs.acting_player].select_action(obs, legal))
                assert env.is_terminal(), "End Phase Goat duel did not terminate"
                path = tmp_path / "end_phase_goat.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                                             env.trajectory().decisions)
                return
    pytest.fail("End Phase Scapegoat / next-turn Metamorphosis line did not resolve")
