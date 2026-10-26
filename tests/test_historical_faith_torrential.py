"""Torrential destroys Flip Summoned Faith but does not stop Spell recovery."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

POT_OF_GREED = 55144522
MAGICIAN_OF_FAITH = 31560081
TORRENTIAL_TRIBUTE = 53582587


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
@pytest.mark.parametrize("chain_torrential", [False, True])
def test_faith_recovers_pot_after_torrential_response(tmp_path, chain_torrential):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (
        POT_OF_GREED, MAGICIAN_OF_FAITH, TORRENTIAL_TRIBUTE)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required official script not installed")
    faith_deck = tmp_path / "faith.ydk"
    faith_deck.write_text("#main\n" + "\n".join(map(str, (
        POT_OF_GREED, MAGICIAN_OF_FAITH, *VANILLA_DECK[2:])))
        + "\n#extra\n!side\n")
    trap_deck = tmp_path / "torrential.ydk"
    trap_deck.write_text("#main\n" + "\n".join(map(str, (
        TORRENTIAL_TRIBUTE, *VANILLA_DECK[1:])))
        + "\n#extra\n!side\n")

    with GoatEnvironment(str(faith_deck), str(trap_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {POT_OF_GREED, MAGICIAN_OF_FAITH} <= {c.code for c in obs.hand}
        assert TORRENTIAL_TRIBUTE in {
            c.code for c in env.engine.probe.observation(1).hand}
        pot_used = faith_set = trap_set = faith_flipped = pot_targeted = False
        responded = checked = False
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"faith_torrential_{chain_torrential}.json"
                write_trajectory(path, env.trajectory())
                trajectory = read_trajectory(path)
                assert verify_trajectory(trajectory,
                                         ExperimentalOcgcoreEngine(root)) == len(
                    trajectory.decisions)
                audit_trajectory_visibility(trajectory)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not pot_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == POT_OF_GREED), None)
                    pot_used |= action is not None
                elif not faith_set:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == MAGICIAN_OF_FAITH), None)
                    faith_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not trap_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == TORRENTIAL_TRIBUTE), None)
                trap_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not faith_flipped:
                opponent = env.engine.probe.observation(1)
                assert any(c.zone == "monster" and c.position == "facedown"
                           and c.code is None for c in opponent.field)
                action = next((a for a in actions if a.kind == "flip_summon"
                               and a.parameters.get("code") == MAGICIAN_OF_FAITH), None)
                faith_flipped |= action is not None
            if (faith_flipped and not pot_targeted and obs.acting_player == 0
                    and actions[0].kind == "select_card"):
                assert [link.card_code for link in obs.chain] == [MAGICIAN_OF_FAITH]
                action = next((a for a in actions if a.parameters.get("code")
                               == POT_OF_GREED and a.parameters.get("location") == 16), None)
                pot_targeted |= action is not None
            if (pot_targeted and not responded and obs.acting_player == 1
                    and obs.chain):
                assert [link.card_code for link in obs.chain] == [MAGICIAN_OF_FAITH]
                torrential = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == TORRENTIAL_TRIBUTE), None)
                assert torrential is not None
                action = torrential if chain_torrential else next(
                    a for a in actions if a.kind == "pass")
                responded = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if (responded and not checked and obs.turn == 3
                    and obs.acting_player == 0 and obs.phase == "main1"
                    and not obs.chain and POT_OF_GREED in {c.code for c in obs.hand}):
                assert obs.life_points == (8000, 8000)
                assert POT_OF_GREED not in {c.code for c in obs.graveyards[0]}
                opponent = env.engine.probe.observation(1)
                assert opponent.known_opponent_hand_cards == (POT_OF_GREED,)
                assert [[c.code for c in reveal.cards]
                        for reveal in opponent.private_reveals] == [[POT_OF_GREED]]
                if chain_torrential:
                    assert MAGICIAN_OF_FAITH in {c.code for c in obs.graveyards[0]}
                    assert TORRENTIAL_TRIBUTE in {c.code for c in obs.graveyards[1]}
                    assert not any(c.code == MAGICIAN_OF_FAITH for c in obs.field)
                else:
                    assert any(c.code == MAGICIAN_OF_FAITH and c.position == "faceup"
                               for c in obs.field)
                    assert any(c.code == TORRENTIAL_TRIBUTE
                               and c.position == "facedown" for c in opponent.field)
                checked = True
    pytest.fail("Faith / Torrential duel did not finish")
