"""A hidden Set after Dustshoot cannot erase guaranteed duplicate hand knowledge."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

DUSTSHOOT = 64697231


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("set_choice", [0, -1])
def test_dustshoot_duplicate_hand_knowledge_survives_opaque_set(tmp_path, set_choice):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{DUSTSHOOT}.lua").is_file():
        pytest.skip("Trap Dustshoot script not installed")
    trap_deck = tmp_path / "dustshoot.ydk"
    trap_deck.write_text("#main\n" + "\n".join(map(str, (
        *([DUSTSHOOT] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(trap_deck), "examples/decks/vanilla_probe.ydk", seed=11,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        trap_set = trap_used = monster_chosen = opponent_set = False
        known_before_set = Counter()
        for _ in range(65):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not trap_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                trap_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 0 and not trap_used:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == DUSTSHOOT), None)
                trap_used |= action is not None
            if trap_used and not monster_chosen and actions[0].kind == "select_card":
                assert obs.chain[0].card_code == DUSTSHOOT
                action = actions[0]
                monster_chosen = True
            if monster_chosen and obs.acting_player == 1 and obs.phase == "main1" \
                    and not opponent_set:
                known_before_set = Counter(env.engine.probe.observation(0)
                                           .known_opponent_hand_cards)
                assert sum(known_before_set.values()) >= 4
                assert max(known_before_set.values()) >= 2
                assert known_before_set == Counter(c.code for c in obs.hand)
                set_options = [a for a in actions if a.kind == "set_monster"]
                assert len({a.parameters["code"] for a in set_options}) >= 2
                action = set_options[set_choice]
                opponent_set |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if opponent_set and any(c.controller == 1 and c.zone == "monster"
                                    and c.position == "facedown" for c in obs.field):
                chooser = env.engine.probe.observation(0)
                expected = Counter({code: count - 1 for code, count
                                    in known_before_set.items() if count > 1})
                assert Counter(chooser.known_opponent_hand_cards) == expected
                assert any(c.controller == 1 and c.zone == "monster"
                           and c.position == "facedown" and c.code is None
                           for c in chooser.field)
                assert chooser.opponent_hand_count == sum(known_before_set.values()) - 1
                return
    pytest.fail("Dustshoot hand reveal and hidden Set did not complete")
