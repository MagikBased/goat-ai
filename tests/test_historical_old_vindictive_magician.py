"""Old Vindictive Magician destroys a visible or hidden opposing monster."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

OLD_VINDICTIVE = 45141844
GEMINI_ELF = 69140098


def _deck(path, cards):
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("hidden_target", [False, True])
def test_old_vindictive_flip_effect_destroys_opposing_monster(tmp_path, hidden_target):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{OLD_VINDICTIVE}.lua").is_file():
        pytest.skip("Old Vindictive Magician script not installed")
    own = _deck(tmp_path / "old_vindictive.ydk", (OLD_VINDICTIVE, *VANILLA_DECK[1:]))
    opposing = _deck(tmp_path / "gemini.ydk", (
        *([GEMINI_ELF] * 3), *(c for c in VANILLA_DECK if c != GEMINI_ELF)))
    with GoatEnvironment(own, opposing, seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        set_old = summoned_elf = flipped = targeted = False
        for _ in range(45):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not set_old:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == OLD_VINDICTIVE), None)
                set_old |= action is not None
            if observation.turn == 2 and observation.acting_player == 1 and not summoned_elf:
                kind = "set_monster" if hidden_target else "normal_summon"
                action = next((a for a in actions if a.kind == kind
                               and a.parameters.get("code") == GEMINI_ELF), None)
                summoned_elf |= action is not None
            if observation.turn == 3 and observation.acting_player == 0 and not flipped:
                action = next((a for a in actions if a.kind == "flip_summon"
                               and a.parameters.get("code") == OLD_VINDICTIVE), None)
                flipped |= action is not None
            if flipped and not targeted and actions[0].kind == "select_card":
                assert observation.chain[0].card_code == OLD_VINDICTIVE
                targets = [a for a in actions if a.kind == "select_card"
                           and a.parameters.get("controller") == 1]
                assert len(targets) == 1
                assert targets[0].parameters.get("location") == 4
                if hidden_target:
                    assert "code" not in targets[0].parameters
                    assert any(c.controller == 1 and c.position == "facedown"
                               and c.code is None for c in observation.field)
                    assert not observation.known_opponent_field_cards
                else:
                    assert targets[0].parameters["code"] == GEMINI_ELF
                action = targets[0]
                targeted = True
            if targeted and any(c.code == GEMINI_ELF for c in observation.graveyards[1]):
                assert not any(c.controller == 1 and c.zone == "monster"
                               for c in observation.field)
                assert any(c.code == OLD_VINDICTIVE and c.position == "faceup"
                           for c in observation.field)
                assert observation.life_points == (8000, 8000)
                assert f"official/c{OLD_VINDICTIVE}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
    pytest.fail(f"Old Vindictive did not destroy target (hidden={hidden_target})")
