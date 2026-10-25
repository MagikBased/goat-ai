"""Compulsory can remove Nobleman of Crossout's set-monster target."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

NOBLEMAN = 504700116
COMPULSORY = 94192409
DEKOICHI = 87621407


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_compulsory_removes_nobleman_target_without_deck_reveal(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for script in (f"goat/c{NOBLEMAN}.lua", f"official/c{COMPULSORY}.lua",
                   f"official/c{DEKOICHI}.lua"):
        if not (root / "scripts" / script).is_file():
            pytest.skip(f"script {script} not installed")
    attacker = tmp_path / "nobleman.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        NOBLEMAN, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    defender = tmp_path / "defender.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        *([DEKOICHI] * 3), *([COMPULSORY] * 3),
        *VANILLA_DECK[6:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        set_monster = set_trap = nobleman_used = nobleman_targeted = False
        compulsory_chained = compulsory_targeted = False
        hand_before = deck_before = None
        for _ in range(85):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1:
                if not set_monster:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == DEKOICHI), None)
                    set_monster |= action is not None
                if set_monster and not set_trap and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == COMPULSORY), None)
                    set_trap |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and set_trap \
                    and not nobleman_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == NOBLEMAN), None)
                nobleman_used |= action is not None
                if nobleman_used:
                    deck_before = obs.deck_counts
                    hand_before = len(env.engine.probe.observation(1).hand)
            if nobleman_used and not nobleman_targeted and actions[0].kind == "select_card":
                assert any(c.controller == 1 and c.zone == "monster"
                           and c.position == "facedown" and c.code is None
                           for c in obs.field)
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("controller") == 1
                               and "code" not in a.parameters), None)
                nobleman_targeted |= action is not None
            if nobleman_targeted and obs.acting_player == 1 and not compulsory_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == COMPULSORY), None)
                compulsory_chained |= action is not None
            if compulsory_chained and not compulsory_targeted \
                    and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 4), None)
                compulsory_targeted |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if compulsory_targeted and all(
                    code in {c.code for pile in obs.graveyards for c in pile}
                    for code in (NOBLEMAN, COMPULSORY)):
                owner = env.engine.probe.observation(1)
                chooser = env.engine.probe.observation(0)
                assert obs.chain == ()
                assert len(owner.hand) == hand_before + 1
                assert DEKOICHI in {c.code for c in owner.hand}
                assert chooser.known_opponent_hand_cards == ()
                assert chooser.opponent_hand_count == len(owner.hand)
                assert chooser.deck_counts == deck_before
                assert not any(c.controller == 1 and c.zone == "monster"
                               for c in chooser.field)
                assert not any(c.code == DEKOICHI for pile in obs.banished for c in pile)
                assert not chooser.private_reveals
                assert not owner.private_reveals
                loaded = env.engine.probe.loaded_script_sha256
                assert {f"goat/c{NOBLEMAN}.lua", f"official/c{COMPULSORY}.lua"}.issubset(
                    loaded)
                return
    pytest.fail("Nobleman/Compulsory chain did not resolve")
