"""Mirror Force removes a monster stolen with Snatch Steal on attack."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SNATCH = 45986603
MIRROR = 44095762


def _deck(path, first, second=None):
    cards = list(VANILLA_DECK)
    cards[0] = first
    if second is not None:
        cards[1] = second
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("use_mirror", [False, True])
def test_mirror_destroys_stolen_attacker_in_owners_graveyard(tmp_path, use_mirror):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{SNATCH}.lua", f"official/c{MIRROR}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("Snatch Steal or Mirror Force script not installed")
    own = _deck(tmp_path / "snatch.ydk", SNATCH)
    other = _deck(tmp_path / "mirror.ydk", MIRROR, VANILLA_DECK[0])

    with GoatEnvironment(own, other, seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert SNATCH in {card.code for card in observation.hand}
        assert MIRROR in {card.code for card in env.engine.probe.observation(1).hand}
        summoned = set_mirror = snatched = targeted = attacked = responded = resolved = False
        stolen_code = None
        for _ in range(90):
            actions = env.legal_actions()
            action = None
            if observation.turn == 2 and observation.acting_player == 1:
                if not summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        stolen_code = action.parameters["code"]
                        summoned = True
                if summoned and not set_mirror and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == MIRROR), None)
                    set_mirror |= action is not None
            if observation.turn == 3 and observation.acting_player == 0:
                if not snatched:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == SNATCH), None)
                    snatched |= action is not None
                if snatched and not targeted and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code") ==
                                   stolen_code and a.parameters.get("controller") == 1), None)
                    targeted |= action is not None
                if targeted and not attacked and action is None:
                    action = next((a for a in actions if a.kind in ("battle_phase", "attack")), None)
                    attacked |= action is not None and action.kind == "attack"
            if attacked and observation.acting_player == 1 and not responded:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == MIRROR), None)
                if option is not None:
                    assert any(card.code == stolen_code and card.controller == 0
                               for card in observation.field)
                    action = option if use_mirror else next(a for a in actions if a.kind == "pass")
                    responded = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if responded and not resolved and observation.chain == ():
                if use_mirror and MIRROR not in {c.code for c in observation.graveyards[1]}:
                    continue
                if not use_mirror and observation.life_points[1] == 8000:
                    continue
                assert summoned and set_mirror and snatched and targeted and attacked
                assert (stolen_code in {c.code for c in observation.graveyards[1]}) == use_mirror
                assert (SNATCH in {c.code for c in observation.graveyards[0]}) == use_mirror
                assert (MIRROR in {c.code for c in observation.graveyards[1]}) == use_mirror
                assert any(c.code == stolen_code and c.controller == 0
                           for c in observation.field) != use_mirror
                assert observation.life_points[0] == 8000
                resolved = True
                break
        assert resolved, "Snatch / Mirror attack branch did not resolve"
        assert f"official/c{SNATCH}.lua" in env.engine.probe.loaded_script_sha256
        if use_mirror:
            assert scripts <= env.engine.probe.loaded_script_sha256.keys()

        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(5000):
            if env.is_terminal():
                break
            legal = env.legal_actions()
            observation = env.step(
                agents[observation.acting_player].select_action(observation, legal))
        assert env.is_terminal(), "Snatch / Mirror duel exceeded 5000 decisions"
        trajectory = env.trajectory()
        path = tmp_path / f"snatch_mirror_{use_mirror}.json"
        write_trajectory(path, trajectory)
        assert verify_trajectory(read_trajectory(path),
                                 ExperimentalOcgcoreEngine(root)) == len(trajectory.decisions)
        assert audit_trajectory_visibility(trajectory)["decisions"] == len(
            trajectory.decisions)
