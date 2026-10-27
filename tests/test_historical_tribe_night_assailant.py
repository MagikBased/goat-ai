"""Night Assailant discarded for Tribe triggers after Tribe's effect resolves."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import verify_trajectory

TRIBE = 33184167
NIGHT_ASSAILANT = 16226796  # GOAT pre-errata variant
MAGICIAN_OF_FAITH = 31560081
GRACEFUL_CHARITY = 79571449
GAGAGIGO = 49003308
REPTILE = 524288


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_tribe_cost_night_assailant_recovers_flip_after_resolution(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{TRIBE}.lua", f"pre-errata/c{NIGHT_ASSAILANT}.lua",
               f"official/c{GRACEFUL_CHARITY}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required pinned scripts not installed")
    deck = tmp_path / "tribe_night.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL_CHARITY, TRIBE, NIGHT_ASSAILANT, NIGHT_ASSAILANT,
        *([MAGICIAN_OF_FAITH] * 3), *VANILLA_DECK[7:])))
        + "\n#extra\n!side\n")
    agent = RandomAgent(18)
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        graceful = faith_discarded = tribe_summoned = opponent_summoned = False
        tribe_activated = night_discarded = type_named = faith_targeted = False
        faith_recovered = False
        for _ in range(3000):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL_CHARITY), None)
                    graceful |= action is not None
                if graceful and not faith_discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if sum(
                        c["code"] == MAGICIAN_OF_FAITH for c in a.parameters["cards"]) == 1
                        and all(c["code"] not in (TRIBE, NIGHT_ASSAILANT)
                                for c in a.parameters["cards"])), None)
                    assert action is not None
                    faith_discarded = True
                if faith_discarded and not tribe_summoned and action is None:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == TRIBE), None)
                    tribe_summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not opponent_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == GAGAGIGO), None)
                opponent_summoned |= action is not None
            if obs.turn == 3 and obs.acting_player == 0:
                if not tribe_activated:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == TRIBE), None)
                    tribe_activated |= action is not None
                if tribe_activated and not night_discarded \
                        and actions[0].kind == "select_card":
                    action = next((a for a in actions if a.parameters.get("code")
                                   == NIGHT_ASSAILANT
                                   and a.parameters.get("location") == 2), None)
                    night_discarded |= action is not None
                if night_discarded and not type_named \
                        and actions[0].kind == "announce_race":
                    assert NIGHT_ASSAILANT in {c.code for c in obs.graveyards[0]}
                    assert MAGICIAN_OF_FAITH in {c.code for c in obs.graveyards[0]}
                    action = next(a for a in actions
                                  if a.parameters["race"] == REPTILE)
                    type_named = True
                if type_named and not faith_targeted and action is None \
                        and actions[0].kind == "select_card":
                    # Tribe's destruction must resolve before this new-chain
                    # discard trigger offers a Graveyard recovery target.
                    assert GAGAGIGO in {c.code for c in obs.graveyards[1]}
                    assert TRIBE in {c.code for c in obs.field}
                    action = next((a for a in actions if a.parameters.get("code")
                                   == MAGICIAN_OF_FAITH
                                   and a.parameters.get("location") == 16), None)
                    assert action is not None
                    faith_targeted = True
            if action is None:
                action = (agent.select_action(obs, actions) if faith_recovered else
                          next((a for a in actions if a.kind in (
                              "place", "pass", "end_phase")), actions[0]))
            obs = env.step(action)
            if faith_targeted and not faith_recovered and obs.turn == 3 \
                    and obs.phase == "main1" and obs.acting_player == 0 \
                    and not obs.chain:
                assert MAGICIAN_OF_FAITH in {c.code for c in obs.hand}
                assert NIGHT_ASSAILANT in {c.code for c in obs.graveyards[0]}
                other = env.engine.probe.observation(1)
                assert any([c.code for c in reveal.cards] == [MAGICIAN_OF_FAITH]
                           for reveal in other.private_reveals)
                faith_recovered = True
            if env.is_terminal():
                assert all((graceful, faith_discarded, tribe_summoned,
                            opponent_summoned, tribe_activated, night_discarded,
                            type_named, faith_targeted, faith_recovered))
                trajectory = env.trajectory()
                assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) \
                       == len(trajectory.decisions)
                audit_trajectory_visibility(trajectory)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                return
    pytest.fail("Tribe / Night Assailant fixture did not reach terminal")
