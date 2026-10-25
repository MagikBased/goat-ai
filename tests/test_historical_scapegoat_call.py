"""Scapegoat chained to Call prevents the earlier revival from resolving."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

GRACEFUL = 79571449
CALL = 97077563
GOAT = 504700123
SANGAN = 504700178
MYSTICAL_ELF = 15025844
SECOND_DISCARD = 79182538


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_goat", [False, True])
def test_scapegoat_chain_prevents_call_revival(tmp_path, chain_goat):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (GRACEFUL, CALL)}
    scripts.update(f"goat/c{code}.lua" for code in (GOAT, SANGAN))
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card scripts not installed")
    cards = [GRACEFUL, CALL, GOAT, *VANILLA_DECK[3:]]
    cards[cards.index(MYSTICAL_ELF)] = SANGAN
    own = tmp_path / "call_goat.ydk"
    own.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), "examples/decks/vanilla_probe.ydk", seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, CALL, GOAT, SANGAN} <= {c.code for c in obs.hand}
        graceful = discarded = call_set = goat_set = call_used = target_chosen = False
        response_seen = goat_chained = checked = False
        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"call_goat_{chain_goat}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    graceful = action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"] for c in
                                   a.parameters["cards"]} == {SANGAN, SECOND_DISCARD}),
                                  None)
                    discarded = action is not None
                if discarded and not call_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == CALL), None)
                    call_set = action is not None
                if discarded and call_set and not goat_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == GOAT), None)
                    goat_set = action is not None
            if obs.turn == 3 and obs.acting_player == 0 and goat_set \
                    and not call_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == CALL), None)
                call_used = action is not None
            if call_used and not target_chosen and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == SANGAN
                               and a.parameters.get("controller") == 0), None)
                target_chosen = action is not None
            if target_chosen and obs.acting_player == 0 and obs.chain \
                    and not response_seen:
                goat = next((a for a in actions if a.kind == "chain"
                             and a.parameters.get("code") == GOAT), None)
                if goat is not None:
                    assert [link.card_code for link in obs.chain] == [CALL]
                    action = goat if chain_goat else next(
                        a for a in actions if a.kind == "pass")
                    goat_chained = chain_goat
                    response_seen = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if response_seen and not checked and not obs.chain and obs.turn == 3:
                owner = env.engine.probe.observation(0)
                monsters = [c for c in owner.field
                            if c.controller == 0 and c.zone == "monster"]
                if chain_goat:
                    assert goat_chained and len(monsters) == 4
                    assert SANGAN in {c.code for c in owner.graveyards[0]}
                    assert GOAT in {c.code for c in owner.graveyards[0]}
                else:
                    assert not goat_chained and len(monsters) == 1
                    assert monsters[0].code == SANGAN
                    assert SANGAN not in {c.code for c in owner.graveyards[0]}
                    assert GOAT in {c.code for c in owner.field}
                assert owner.life_points == (8000, 8000)
                expected_scripts = (scripts if chain_goat else
                                    scripts - {f"goat/c{GOAT}.lua"})
                assert expected_scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail("Scapegoat / Call chain did not finish")
