"""Compulsory Evacuation Device returns main and Fusion monsters correctly."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

COMPULSORY = 94192409
SCAPEGOAT = 504700123
METAMORPHOSIS = 46411259
RESTRICT = 504700102
SHEEP_CODES = {73915052, 73915053, 73915054, 73915055}


def _deck(path, cards, extra=()):
    path.write_text("#main\n" + "\n".join(map(str, cards))
                    + "\n#extra\n" + "\n".join(map(str, extra)) + "\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("fusion", [False, True])
def test_compulsory_return_destination_and_hidden_hand(tmp_path, fusion):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    required = [f"scripts/official/c{COMPULSORY}.lua"]
    if fusion:
        required += [f"scripts/goat/c{SCAPEGOAT}.lua",
                     f"scripts/official/c{METAMORPHOSIS}.lua",
                     f"scripts/goat/c{RESTRICT}.lua"]
    if not all((root / script).is_file() for script in required):
        pytest.skip("required card scripts not installed")
    own = _deck(tmp_path / "compulsory.ydk",
                (*([COMPULSORY] * 3), *VANILLA_DECK[3:]))
    other = _deck(tmp_path / "opponent.ydk",
                  (*([SCAPEGOAT] * 3), *([METAMORPHOSIS] * 3),
                   *VANILLA_DECK[6:]) if fusion else VANILLA_DECK,
                  (RESTRICT,) if fusion else ())
    with GoatEnvironment(own, other, seed=11 if fusion else 15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        trap_set = goat = metamorphosis = paid_token = selected_fusion = False
        summoned = activated = target_selected = False
        target_code = None
        hand_before = None
        for _ in range(90):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not trap_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == COMPULSORY), None)
                trap_set |= action is not None
            if fusion and obs.turn == 2 and obs.acting_player == 1 and not goat:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                goat |= action is not None
            if fusion and obs.turn == 4 and obs.acting_player == 1 and not metamorphosis:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == METAMORPHOSIS), None)
                metamorphosis |= action is not None
            if fusion and metamorphosis and not paid_token and action is None:
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") in SHEEP_CODES), None)
                paid_token |= action is not None
            if fusion and paid_token and not selected_fusion and action is None:
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == RESTRICT), None)
                selected_fusion |= action is not None
            if not fusion and obs.turn == 2 and obs.acting_player == 1 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    target_code = action.parameters["code"]
                    summoned = True
            target_on_field = any(c.controller == 1 and c.zone == "monster"
                                  and c.code == (RESTRICT if fusion else target_code)
                                  for c in obs.field)
            if trap_set and target_on_field and obs.acting_player == 0 and not activated:
                action = next((a for a in actions if a.kind in ("activate", "chain")
                               and a.parameters.get("code") == COMPULSORY), action)
                activated |= action is not None and action.parameters.get("code") == COMPULSORY
                if activated:
                    hand_before = len(env.engine.probe.observation(1).hand)
            if activated and not target_selected and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("controller") == 1
                               and a.parameters.get("code")
                               == (RESTRICT if fusion else target_code)), None)
                target_selected = action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "select_position", "pass", "end_phase")),
                    actions[0])
            obs = env.step(action)
            if target_selected and COMPULSORY in {c.code for c in obs.graveyards[0]}:
                assert not any(c.controller == 1 and c.zone == "monster"
                               and c.code == (RESTRICT if fusion else target_code)
                               for c in obs.field)
                owner_view = env.engine.probe.observation(1)
                chooser_view = env.engine.probe.observation(0)
                assert len(owner_view.hand) == hand_before + (0 if fusion else 1)
                assert chooser_view.opponent_hand_count == len(owner_view.hand)
                assert obs.extra_deck_counts[1] == (1 if fusion else 0)
                assert not any(c.code == (RESTRICT if fusion else target_code)
                               for c in obs.graveyards[1])
                assert all(c.controller == 0 for c in chooser_view.hand)
                assert f"official/c{COMPULSORY}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Compulsory did not return the selected monster")
