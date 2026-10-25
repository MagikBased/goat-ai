"""Destroying activated Nobleman with Dust Tornado does not negate it."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

NOBLEMAN = 504700116
SPY = 504700044
DUST = 60082869


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_dust", [False, True])
def test_dust_destroys_nobleman_but_spy_is_still_banished(tmp_path, chain_dust):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{NOBLEMAN}.lua", f"goat/c{SPY}.lua",
               f"official/c{DUST}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    attacker_cards = list(VANILLA_DECK)
    attacker_cards[0] = NOBLEMAN
    attacker_cards[6] = NOBLEMAN
    attacker = tmp_path / "nobleman.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, attacker_cards))
                        + "\n#extra\n!side\n")
    defender = tmp_path / "dust_spy.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        DUST, *([SPY] * 3), *VANILLA_DECK[4:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=7,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert NOBLEMAN in {c.code for c in obs.hand}
        assert {DUST, SPY} <= {c.code for c in env.engine.probe.observation(1).hand}
        spy_set = dust_set = nobleman_used = spy_targeted = response = False
        dust_targeted = checked = False
        defender_hand_spies = None
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"nobleman_dust_{chain_dust}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1:
                if not spy_set:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == SPY), None)
                    spy_set = action is not None
                elif not dust_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == DUST), None)
                    dust_set = action is not None
            if obs.turn == 3 and obs.acting_player == 0 and dust_set \
                    and not nobleman_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == NOBLEMAN), None)
                nobleman_used = action is not None
            if nobleman_used and not spy_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and "code" not in a.parameters), None)
                spy_targeted = action is not None
                if spy_targeted:
                    assert any(c.controller == 1 and c.zone == "spell_trap"
                               and c.position == "facedown" and c.code is None
                               for c in obs.field)
                    defender_hand_spies = sum(c.code == SPY for c in
                                             env.engine.probe.observation(1).hand)
            if spy_targeted and obs.acting_player == 1 and not response:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == DUST), None)
                if option is not None:
                    assert [link.card_code for link in obs.chain] == [NOBLEMAN]
                    action = option if chain_dust else next(
                        a for a in actions if a.kind == "pass")
                    response = True
            if response and chain_dust and not dust_targeted \
                    and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == NOBLEMAN
                               and a.parameters.get("controller") == 0), None)
                dust_targeted = action is not None
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase", "no")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if response and not checked and obs.turn == 3 and obs.phase == "main1" \
                    and obs.acting_player == 0 and not obs.chain \
                    and SPY in {c.code for c in obs.banished[1]}:
                assert dust_targeted == chain_dust
                assert sum(c.code == SPY for c in obs.banished[1]) \
                    == 3 - defender_hand_spies
                assert not any(c.code == SPY for c in obs.graveyards[1])
                assert NOBLEMAN in {c.code for c in obs.graveyards[0]}
                assert (DUST in {c.code for c in obs.graveyards[1]}) == chain_dust
                assert obs.life_points == (8000, 8000)
                loaded = env.engine.probe.loaded_script_sha256
                assert {f"goat/c{NOBLEMAN}.lua", f"goat/c{SPY}.lua"} <= loaded.keys()
                if chain_dust:
                    assert f"official/c{DUST}.lua" in loaded
                checked = True
    pytest.fail("Nobleman / Dust response did not complete")
