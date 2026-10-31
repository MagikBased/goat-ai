"""Historical Metamorphosis uses a WATER monster's current Ocean-reduced Level."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

OCEAN = 295517
METAMORPHOSIS = 46411259
GAGAGIGO = 49003308  # Level 4 WATER monster.
FLAME_GHOST = 58528964  # Level 3 Fusion.
DARKFIRE_DRAGON = 17881964  # Level 4 Fusion.


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("activate_ocean", (False, True), ids=("without_ocean", "ocean"))
def test_ocean_changes_metamorphosis_fusion_choice(tmp_path, activate_ocean):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{OCEAN}.lua", f"official/c{METAMORPHOSIS}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required pinned card scripts not installed")
    deck = tmp_path / "ocean_meta.ydk"
    remaining = list(VANILLA_DECK)
    remaining.remove(GAGAGIGO)
    deck.write_text("#main\n" + "\n".join(map(str, (
        OCEAN, METAMORPHOSIS, GAGAGIGO, *remaining[:37])))
        + f"\n#extra\n{FLAME_GHOST}\n{DARKFIRE_DRAGON}\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {OCEAN, METAMORPHOSIS, GAGAGIGO} <= {c.code for c in obs.hand}
        ocean_used = summoned = meta_used = paid = fusion_chosen = checked = False
        expected_fusion = FLAME_GHOST if activate_ocean else DARKFIRE_DRAGON
        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(3000):
            if env.is_terminal():
                break
            actions = env.legal_actions()
            action = None
            if not checked and obs.turn == 1 and obs.acting_player == 0:
                if activate_ocean and not ocean_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == OCEAN), None)
                    ocean_used |= action is not None
                if (not activate_ocean or ocean_used) and not summoned and action is None:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == GAGAGIGO), None)
                    summoned |= action is not None
                if summoned and not meta_used and action is None:
                    faceup = next((c for c in obs.field if c.code == GAGAGIGO
                                   and c.position == "faceup"), None)
                    meta_option = next((a for a in actions if a.kind == "activate"
                                        and a.parameters.get("code") == METAMORPHOSIS), None)
                    if faceup is not None and meta_option is not None:
                        assert faceup.level == (3 if activate_ocean else 4), (
                            [(c.code, c.position, c.zone) for c in obs.field],
                            obs.public_history)
                        assert faceup.attack == (2050 if activate_ocean else 1850)
                        other = env.engine.probe.observation(1)
                        assert next(c for c in other.field if c.code == GAGAGIGO).level \
                            == faceup.level
                    action = meta_option
                    meta_used |= action is not None
            if meta_used and not paid and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == GAGAGIGO),
                              None)
                paid |= action is not None
            if paid and not fusion_chosen and action is None \
                    and actions[0].kind == "select_card":
                assert {a.parameters.get("code") for a in actions} == {expected_fusion}
                action = next(a for a in actions
                              if a.parameters.get("code") == expected_fusion)
                fusion_chosen = True
            if fusion_chosen and not checked and action is None \
                    and not obs.chain and obs.phase == "main1":
                assert any(c.code == expected_fusion for c in obs.field)
                assert GAGAGIGO in {c.code for c in obs.graveyards[0]}
                assert (OCEAN in {c.code for c in obs.field}) == activate_ocean
                assert env.engine.probe.loaded_script_sha256.keys() >= (
                    scripts if activate_ocean else {f"official/c{METAMORPHOSIS}.lua"})
                checked = True
            if action is None:
                action = (next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0]) if not checked else
                    agents[obs.acting_player].select_action(obs, actions))
            obs = env.step(action)
        assert checked and env.is_terminal(), "Ocean/Metamorphosis duel did not finish"
        path = tmp_path / f"ocean_meta_{activate_ocean}.json"
        write_trajectory(path, env.trajectory())
    replay = read_trajectory(path)
    assert audit_trajectory_visibility(replay)["decisions"] == len(replay.decisions)
    assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(replay.decisions)
