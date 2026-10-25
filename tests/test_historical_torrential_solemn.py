"""Solemn negates Torrential's activation after a successful Normal Summon."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SOLEMN = 41420027
TORRENTIAL = 53582587


def _deck(path, card):
    path.write_text("#main\n" + "\n".join(map(str, (
        card, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("negate", [False, True])
def test_solemn_negates_torrential_and_saves_summoned_monsters(tmp_path, negate):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (SOLEMN, TORRENTIAL)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card scripts not installed")
    own = _deck(tmp_path / "solemn.ydk", SOLEMN)
    other = _deck(tmp_path / "torrential.ydk", TORRENTIAL)

    with GoatEnvironment(own, other, seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert SOLEMN in {c.code for c in obs.hand}
        assert TORRENTIAL in {c.code for c in env.engine.probe.observation(1).hand}
        solemn_set = torrential_set = torrential_used = response = checked = False
        own_summons = opponent_summon = 0
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"torrential_solemn_{negate}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not solemn_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == SOLEMN), None)
                    solemn_set = action is not None
                elif own_summons == 0:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    own_summons += action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not torrential_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == TORRENTIAL), None)
                    torrential_set = action is not None
                elif not opponent_summon:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    opponent_summon += action is not None
            if obs.turn == 3 and obs.acting_player == 0 and own_summons == 1:
                assert solemn_set and torrential_set and opponent_summon
                assert len([c for c in obs.field if c.zone == "monster"]) == 2
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                own_summons += action is not None
            if own_summons == 2 and obs.acting_player == 1 and not torrential_used:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == TORRENTIAL), None)
                if option is not None:
                    assert obs.turn == 3 and obs.phase == "main1"
                    assert not obs.chain
                    assert len([c for c in obs.field if c.zone == "monster"]) == 3
                    action = option
                    torrential_used = True
            if torrential_used and obs.acting_player == 0 and not response:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SOLEMN), None)
                if option is not None:
                    assert [link.card_code for link in obs.chain] == [TORRENTIAL]
                    action = option if negate else next(a for a in actions
                                                       if a.kind == "pass")
                    response = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if response and not checked and not obs.chain \
                    and TORRENTIAL in {c.code for c in obs.graveyards[1]}:
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                assert own_summons == 2 and opponent_summon == 1
                if negate:
                    assert obs.life_points == (4000, 8000)
                    assert SOLEMN in {c.code for c in obs.graveyards[0]}
                    assert len(obs.graveyards[0]) == len(obs.graveyards[1]) == 1
                    assert len([c for c in obs.field if c.zone == "monster"]) == 3
                    assert len([c for c in obs.field if c.zone == "monster"
                                and c.controller == 0]) == 2
                else:
                    assert obs.life_points == (8000, 8000)
                    assert SOLEMN not in {c.code for c in obs.graveyards[0]}
                    assert not any(c.zone == "monster" for c in obs.field)
                    assert len(obs.graveyards[0]) == len(obs.graveyards[1]) == 2
                    assert any(c.code == SOLEMN and c.position == "facedown"
                               for c in env.engine.probe.observation(0).field)
                checked = True
    pytest.fail("Torrential / Solemn response did not complete")
