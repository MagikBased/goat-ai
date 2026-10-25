"""Metamorphosis may Tribute an owned Set monster of matching Fusion Level."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

DARK_MIMIC_LV1 = 504700129
METAMORPHOSIS = 46411259
RESTRICT = 504700102


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("eligible_fusion", [False, True])
def test_metamorphosis_set_monster_cost_requires_matching_fusion(tmp_path, eligible_fusion):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{DARK_MIMIC_LV1}.lua",
               f"official/c{METAMORPHOSIS}.lua", f"goat/c{RESTRICT}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card scripts not installed")
    deck = tmp_path / "set_mimic_meta.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        *([DARK_MIMIC_LV1] * 3), *([METAMORPHOSIS] * 3),
        *VANILLA_DECK[6:]))) + "\n#extra\n"
        + (f"{RESTRICT}\n" if eligible_fusion else "") + "!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {DARK_MIMIC_LV1, METAMORPHOSIS}.issubset(c.code for c in obs.hand)
        set_done = activated = tributed = fusion_chosen = checked = False
        deck_before = obs.deck_counts[0]
        for _ in range(40):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not set_done:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == DARK_MIMIC_LV1), None)
                set_done = action is not None
            elif (set_done and not checked and obs.turn == 1
                  and obs.acting_player == 0 and any(
                      c.zone == "monster" and c.controller == 0
                      and c.position == "facedown" for c in obs.field)
                  and any(a.kind != "pass" for a in actions)):
                own_set = next(c for c in obs.field if c.zone == "monster"
                               and c.controller == 0 and c.code == DARK_MIMIC_LV1)
                assert own_set.position == "facedown"
                opposing_view = env.engine.probe.observation(1)
                hidden = next(c for c in opposing_view.field if c.zone == "monster"
                              and c.controller == 0 and c.sequence == own_set.sequence)
                assert hidden.code is None and hidden.position == "facedown"
                option = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == METAMORPHOSIS), None)
                assert (option is not None) == eligible_fusion
                checked = True
                if not eligible_fusion:
                    assert deck_before == obs.deck_counts[0]
                    assert METAMORPHOSIS in {c.code for c in obs.hand}
                    assert not any(c.code == DARK_MIMIC_LV1
                                   for c in obs.graveyards[0])
                    return
                action = option
                activated = True
            elif activated and not tributed and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == DARK_MIMIC_LV1 and a.parameters.get("location") == 4
                               and a.parameters.get("controller") == 0), None)
                tributed = action is not None
            elif tributed and not fusion_chosen and actions[0].kind == "select_card":
                assert {a.parameters.get("code") for a in actions} == {RESTRICT}
                action = next(a for a in actions if a.parameters.get("code") == RESTRICT)
                fusion_chosen = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if fusion_chosen and any(c.code == RESTRICT and c.zone == "monster"
                                     for c in obs.field):
                assert checked and set_done and activated and tributed
                assert DARK_MIMIC_LV1 in {c.code for c in obs.graveyards[0]}
                assert METAMORPHOSIS in {c.code for c in obs.graveyards[0]}
                assert obs.deck_counts[0] == deck_before  # No Flip Effect draw.
                assert obs.extra_deck_counts[0] == 0
                assert {f"official/c{METAMORPHOSIS}.lua",
                        f"goat/c{RESTRICT}.lua"}.issubset(
                            env.engine.probe.loaded_script_sha256)
                agents = (RandomAgent(18), RandomAgent(19))
                for _ in range(3000):
                    if env.is_terminal():
                        break
                    legal = env.legal_actions()
                    obs = env.step(agents[obs.acting_player].select_action(obs, legal))
                assert env.is_terminal(), "Set-monster Metamorphosis duel did not terminate"
                path = tmp_path / "set_mimic_meta.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                                             env.trajectory().decisions)
                return
    pytest.fail("Set-monster Metamorphosis line did not resolve")
