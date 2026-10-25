"""Dust Tornado destroys Graceful Charity without negating its private draw."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

GRACEFUL = 79571449
DUST = 60082869


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_dust", [False, True])
def test_dust_on_graceful_does_not_stop_private_draw_or_discard(tmp_path, chain_dust):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (GRACEFUL, DUST)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    attacker = tmp_path / "graceful.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    defender = tmp_path / "dust.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        DUST, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert GRACEFUL in {c.code for c in obs.hand}
        assert DUST in {c.code for c in env.engine.probe.observation(1).hand}
        dust_set = graceful_used = response_made = dust_targeted = False
        discarded = checked = False
        hand_before = deck_before = None
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"graceful_dust_{chain_dust}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if not checked and obs.turn == 2 and obs.acting_player == 1 \
                    and not dust_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == DUST), None)
                dust_set = action is not None
            if not checked and obs.turn == 3 and obs.acting_player == 0 \
                    and dust_set and not graceful_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == GRACEFUL), None)
                if action is not None:
                    graceful_used = True
                    hand_before = len(obs.hand)
                    deck_before = obs.deck_counts[0]
                    assert any(c.controller == 1 and c.zone == "spell_trap"
                               and c.position == "facedown" and c.code is None
                               for c in obs.field)
            if graceful_used and obs.acting_player == 1 and not response_made:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == DUST), None)
                if option is not None:
                    assert [link.card_code for link in obs.chain] == [GRACEFUL]
                    action = option if chain_dust else next(
                        a for a in actions if a.kind == "pass")
                    response_made = True
            if response_made and chain_dust and not dust_targeted \
                    and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == GRACEFUL
                               and a.parameters.get("controller") == 0), None)
                dust_targeted = action is not None
            if response_made and not discarded and actions[0].kind == "select_cards":
                assert obs.viewer == obs.acting_player == 0
                if chain_dust:
                    assert GRACEFUL in {c.code for c in obs.graveyards[0]}
                assert obs.deck_counts[0] == deck_before - 3
                assert len(obs.hand) == hand_before + 2
                other = env.engine.probe.observation(1)
                assert other.opponent_hand_count == len(obs.hand)
                assert not other.private_reveals
                action = actions[0]
                assert len(action.parameters["cards"]) == 2
                discarded = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase", "no")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if response_made and discarded and not checked \
                    and obs.turn == 3 and obs.phase == "main1" \
                    and obs.acting_player == 0 and not obs.chain:
                assert dust_targeted == chain_dust
                assert GRACEFUL in {c.code for c in obs.graveyards[0]}
                assert (DUST in {c.code for c in obs.graveyards[1]}) == chain_dust
                assert obs.deck_counts[0] == deck_before - 3
                assert len(obs.hand) == hand_before
                assert obs.life_points == (8000, 8000)
                assert not env.engine.probe.observation(1).private_reveals
                loaded = env.engine.probe.loaded_script_sha256
                assert f"official/c{GRACEFUL}.lua" in loaded
                if chain_dust:
                    assert scripts <= loaded.keys()
                checked = True
    pytest.fail("Graceful / Dust response did not complete")
