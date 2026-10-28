"""Ceasefire flips Set monsters without their Flip Effects and counts Effects."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

POT = 55144522
FAITH = 31560081
ELF = 15025844
CEASEFIRE = 36468556
JINZO = 77585513
SCAPEGOAT = 504700123  # GOAT variant


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("set_monster", [FAITH, ELF])
def test_ceasefire_flips_without_flip_effect_and_counts_effect_monsters(tmp_path,
                                                                        set_monster):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    script = f"official/c{CEASEFIRE}.lua"
    if not (root / "scripts" / script).is_file():
        pytest.skip("Ceasefire script not installed")
    own = tmp_path / "own.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        POT, set_monster, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    opponent = tmp_path / "ceasefire.ydk"
    opponent.write_text("#main\n" + "\n".join(map(str, (
        CEASEFIRE, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(opponent), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {POT, set_monster} <= {card.code for card in obs.hand}
        assert CEASEFIRE in {card.code for card in env.engine.probe.observation(1).hand}
        pot_used = monster_set = trap_set = responded = checked = False
        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"ceasefire_{set_monster}.json"
                write_trajectory(path, env.trajectory())
                replay = read_trajectory(path)
                assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(
                    replay.decisions)
                assert audit_trajectory_visibility(replay)["decisions"] == len(
                    replay.decisions)
                return
            actions = env.legal_actions()
            action = None
            if not checked:
                if obs.turn == 1 and obs.acting_player == 0:
                    if not pot_used:
                        action = next((a for a in actions if a.kind == "activate"
                                       and a.parameters.get("code") == POT), None)
                        pot_used |= action is not None
                    if pot_used and not monster_set and action is None:
                        action = next((a for a in actions if a.kind == "set_monster"
                                       and a.parameters.get("code") == set_monster), None)
                        monster_set |= action is not None
                if obs.turn == 2 and obs.acting_player == 1 and not trap_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == CEASEFIRE), None)
                    trap_set |= action is not None
                if obs.turn == 3 and obs.acting_player == 1 and not responded:
                    option = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == CEASEFIRE), None)
                    if option is not None:
                        own_view = env.engine.probe.observation(0)
                        assert POT in {c.code for c in own_view.graveyards[0]}
                        assert any(c.code == set_monster and c.position == "facedown"
                                   for c in own_view.field)
                        assert any(c.controller == 0 and c.code is None
                                   for c in obs.field)
                        action = option
                        responded = True
                if action is None:
                    action = next((a for a in actions if a.kind in (
                        "place", "pass", "end_phase")), actions[0])
            else:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if responded and not checked and not obs.chain \
                    and CEASEFIRE in {c.code for c in obs.graveyards[1]}:
                own_view = env.engine.probe.observation(0)
                assert own_view.life_points == (8000 - (500 if set_monster == FAITH else 0),
                                                8000)
                assert any(c.code == set_monster and c.position == "faceup"
                           and c.orientation == "defense" for c in own_view.field)
                assert POT in {c.code for c in own_view.graveyards[0]}
                assert POT not in {c.code for c in own_view.hand}
                assert not obs.chain
                assert script in env.engine.probe.loaded_script_sha256
                checked = True
    pytest.fail("Ceasefire duel did not finish")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_ceasefire_finishes_resolving_after_it_flips_jinzo_faceup(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (CEASEFIRE, JINZO):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"card script for {code} not installed")
    own = tmp_path / "jinzo.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        ELF, JINZO, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    opponent = tmp_path / "ceasefire.ydk"
    opponent.write_text("#main\n" + "\n".join(map(str, (
        CEASEFIRE, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(opponent), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {ELF, JINZO} <= {card.code for card in obs.hand}
        first_summoned = trap_set = jinzo_set = tributed = responded = checked = False
        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / "ceasefire_jinzo.json"
                write_trajectory(path, env.trajectory())
                replay = read_trajectory(path)
                assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(
                    replay.decisions)
                assert audit_trajectory_visibility(replay)["decisions"] == len(
                    replay.decisions)
                return
            actions = env.legal_actions()
            action = None
            if not checked:
                if obs.turn == 1 and obs.acting_player == 0 and not first_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == ELF), None)
                    first_summoned |= action is not None
                if obs.turn == 2 and obs.acting_player == 1 and not trap_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == CEASEFIRE), None)
                    trap_set |= action is not None
                if obs.turn == 3 and obs.acting_player == 0 and not jinzo_set:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == JINZO), None)
                    jinzo_set |= action is not None
                if jinzo_set and not tributed and action is None:
                    action = next((a for a in actions if a.kind == "tribute"
                                   and a.parameters.get("code") == ELF), None)
                    tributed |= action is not None
                if tributed and obs.acting_player == 1 and not responded:
                    option = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == CEASEFIRE), None)
                    if option is not None:
                        assert not obs.chain
                        assert any(c.controller == 0 and c.code is None
                                   and c.position == "facedown" for c in obs.field)
                        action = option
                        responded = True
                if action is None:
                    action = next((a for a in actions if a.kind in (
                        "place", "pass", "end_phase")), actions[0])
            else:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if responded and not checked and not obs.chain \
                    and CEASEFIRE in {c.code for c in obs.graveyards[1]}:
                own_view = env.engine.probe.observation(0)
                assert own_view.life_points == (7500, 8000)
                assert any(c.controller == 0 and c.code == JINZO
                           and c.position == "faceup" and c.orientation == "defense"
                           for c in own_view.field)
                assert ELF in {c.code for c in own_view.graveyards[0]}
                assert {f"official/c{code}.lua" for code in (CEASEFIRE, JINZO)} \
                    <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail("Ceasefire / Jinzo duel did not finish")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_ceasefire", [False, True])
def test_ceasefire_chained_to_faith_does_not_cancel_pending_flip_effect(
        tmp_path, chain_ceasefire):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (POT, FAITH, CEASEFIRE)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card scripts not installed")
    own = tmp_path / "faith.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        POT, FAITH, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    opponent = tmp_path / "ceasefire.ydk"
    opponent.write_text("#main\n" + "\n".join(map(str, (
        CEASEFIRE, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(opponent), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {POT, FAITH} <= {card.code for card in obs.hand}
        pot_used = faith_set = trap_set = faith_flipped = pot_targeted = False
        response_seen = checked = False
        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"ceasefire_faith_chain_{chain_ceasefire}.json"
                write_trajectory(path, env.trajectory())
                replay = read_trajectory(path)
                assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(
                    replay.decisions)
                assert audit_trajectory_visibility(replay)["decisions"] == len(
                    replay.decisions)
                return
            actions = env.legal_actions()
            action = None
            if not checked:
                if obs.turn == 1 and obs.acting_player == 0:
                    if not pot_used:
                        action = next((a for a in actions if a.kind == "activate"
                                       and a.parameters.get("code") == POT), None)
                        pot_used |= action is not None
                    if pot_used and not faith_set and action is None:
                        action = next((a for a in actions if a.kind == "set_monster"
                                       and a.parameters.get("code") == FAITH), None)
                        faith_set |= action is not None
                if obs.turn == 2 and obs.acting_player == 1 and not trap_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == CEASEFIRE), None)
                    trap_set |= action is not None
                if obs.turn == 3 and obs.acting_player == 0 and not faith_flipped:
                    action = next((a for a in actions if a.kind == "flip_summon"
                                   and a.parameters.get("code") == FAITH), None)
                    faith_flipped |= action is not None
                if faith_flipped and not pot_targeted and actions[0].kind == "select_card" \
                        and [link.card_code for link in obs.chain] == [FAITH]:
                    action = next((a for a in actions if a.parameters.get("code") == POT
                                   and a.parameters.get("location") == 16), None)
                    pot_targeted |= action is not None
                if pot_targeted and not response_seen and obs.acting_player == 1 \
                        and [link.card_code for link in obs.chain] == [FAITH]:
                    option = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == CEASEFIRE), None)
                    assert option is not None
                    action = option if chain_ceasefire else next(
                        a for a in actions if a.kind == "pass")
                    response_seen = True
                if action is None:
                    action = next((a for a in actions if a.kind in (
                        "place", "pass", "end_phase")), actions[0])
            else:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if response_seen and not checked and not obs.chain \
                    and POT in {c.code for c in obs.hand}:
                own_view = env.engine.probe.observation(0)
                other_view = env.engine.probe.observation(1)
                assert own_view.life_points == (7500 if chain_ceasefire else 8000, 8000)
                assert POT not in {c.code for c in own_view.graveyards[0]}
                assert other_view.known_opponent_hand_cards == (POT,)
                assert any(c.controller == 0 and c.code == FAITH
                           and c.position == "faceup" for c in own_view.field)
                assert (CEASEFIRE in {c.code for c in own_view.graveyards[1]}) \
                    == chain_ceasefire
                loaded = env.engine.probe.loaded_script_sha256.keys()
                assert scripts - (set() if chain_ceasefire else {
                    f"official/c{CEASEFIRE}.lua"}) <= loaded
                checked = True
    pytest.fail("Ceasefire chained to Faith did not finish")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_ceasefire_excludes_four_sheep_tokens_from_damage(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/goat/c{SCAPEGOAT}.lua").is_file():
        pytest.skip("GOAT Scapegoat script not installed")
    own = tmp_path / "goats.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        SCAPEGOAT, ELF, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    opponent = tmp_path / "ceasefire.ydk"
    opponent.write_text("#main\n" + "\n".join(map(str, (
        CEASEFIRE, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(opponent), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {SCAPEGOAT, ELF} <= {card.code for card in obs.hand}
        goats_used = trap_set = elf_set = responded = checked = False
        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / "ceasefire_goats.json"
                write_trajectory(path, env.trajectory())
                replay = read_trajectory(path)
                assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(
                    replay.decisions)
                assert audit_trajectory_visibility(replay)["decisions"] == len(
                    replay.decisions)
                return
            actions = env.legal_actions()
            action = None
            if not checked:
                if obs.turn == 1 and obs.acting_player == 0 and not goats_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == SCAPEGOAT), None)
                    goats_used |= action is not None
                if obs.turn == 2 and obs.acting_player == 1 and not trap_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == CEASEFIRE), None)
                    trap_set |= action is not None
                if obs.turn == 3 and obs.acting_player == 0 and not elf_set:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == ELF), None)
                    elf_set |= action is not None
                if elf_set and obs.turn == 3 and obs.acting_player == 1 \
                        and not responded:
                    option = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == CEASEFIRE), None)
                    if option is not None:
                        own_view = env.engine.probe.observation(0)
                        assert sum(c.zone == "monster" and c.controller == 0
                                   for c in own_view.field) == 5
                        action = option
                        responded = True
                if action is None:
                    action = next((a for a in actions if a.kind in (
                        "place", "pass", "end_phase")), actions[0])
            else:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if responded and not checked and not obs.chain \
                    and CEASEFIRE in {c.code for c in obs.graveyards[1]}:
                own_view = env.engine.probe.observation(0)
                assert own_view.life_points == (8000, 8000)
                assert any(c.code == ELF and c.position == "faceup"
                           for c in own_view.field)
                assert sum(c.zone == "monster" and c.controller == 0
                           for c in own_view.field) == 5
                assert f"goat/c{SCAPEGOAT}.lua" in env.engine.probe.loaded_script_sha256
                assert f"official/c{CEASEFIRE}.lua" in env.engine.probe.loaded_script_sha256
                checked = True
    pytest.fail("Ceasefire / Sheep Token duel did not finish")
