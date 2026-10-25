"""Creature Swap chooses monsters during resolution and changes control permanently."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

CREATURE_SWAP = 31036355
SCAPEGOAT = 504700123
RING = 511000824
SHEEP_CODES = {73915052, 73915053, 73915054, 73915055}


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_creature_swap_choices_after_chain_and_permanent_control(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{CREATURE_SWAP}.lua").is_file():
        pytest.skip("Creature Swap script not installed")
    own = tmp_path / "swap.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        *([CREATURE_SWAP] * 2), *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(own), "examples/decks/vanilla_probe.ydk", seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        first_summoned = opponent_summoned = second_summoned = swap_used = False
        chose_own = chose_opponent = resolved = False
        first_code = second_code = opponent_code = None
        for _ in range(50):
            actions = env.legal_actions()
            action = None
            if first_summoned and not opponent_summoned \
                    and observation.acting_player == 0:
                assert not any(a.kind == "activate" and a.parameters.get("code")
                               == CREATURE_SWAP for a in actions)
            if observation.turn == 1 and observation.acting_player == 0 \
                    and not first_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    first_summoned = True
                    first_code = action.parameters["code"]
            if observation.turn == 2 and observation.acting_player == 1 \
                    and not opponent_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    opponent_summoned = True
                    opponent_code = action.parameters["code"]
            if observation.turn == 3 and observation.acting_player == 0:
                if not second_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        second_summoned = True
                        second_code = action.parameters["code"]
                if action is None and second_summoned and not swap_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == CREATURE_SWAP), None)
                    swap_used |= action is not None
            if swap_used and actions[0].kind == "select_card":
                assert len(observation.chain) == 1
                assert observation.chain[0].card_code == CREATURE_SWAP
                if observation.acting_player == 0 and not chose_own:
                    assert {(a.parameters["code"], a.parameters["controller"])
                            for a in actions} == {(first_code, 0), (second_code, 0)}
                    action = next(a for a in actions
                                  if a.parameters["code"] == first_code)
                    chose_own = True
                elif observation.acting_player == 1 and not chose_opponent:
                    assert len(actions) == 1
                    assert actions[0].parameters["code"] == opponent_code
                    assert actions[0].parameters["controller"] == 1
                    action = actions[0]
                    chose_opponent = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if chose_own and chose_opponent and not resolved and CREATURE_SWAP in {
                    c.code for c in observation.graveyards[0]}:
                assert {(c.code, c.controller) for c in observation.field
                        if c.zone == "monster"} == {
                            (first_code, 1), (second_code, 0), (opponent_code, 0)}
                assert observation.life_points == (8000, 8000)
                resolved = True
            if resolved and observation.turn == 3 and observation.acting_player == 0 \
                    and any(a.kind == "end_phase" for a in env.legal_actions()):
                assert not any(a.kind == "change_position" and a.parameters.get("code")
                               == opponent_code for a in env.legal_actions())
            if resolved and observation.turn >= 4:
                assert {(c.code, c.controller) for c in observation.field
                        if c.zone == "monster"} == {
                            (first_code, 1), (second_code, 0), (opponent_code, 0)}
                assert f"official/c{CREATURE_SWAP}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Creature Swap did not exchange the chosen monsters")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("opponent_set", [False, True])
def test_swap_of_set_monster_keeps_former_controller_knowledge(tmp_path, opponent_set):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{CREATURE_SWAP}.lua").is_file():
        pytest.skip("Creature Swap script not installed")
    own = tmp_path / "swap.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        *([CREATURE_SWAP] * 2), *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(own), "examples/decks/vanilla_probe.ydk", seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        set_monster = opponent_summoned = swap_used = False
        own_code = opponent_code = None
        for _ in range(50):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 \
                    and not set_monster:
                action = next((a for a in actions if a.kind == "set_monster"), None)
                if action is not None:
                    set_monster = True
                    own_code = action.parameters["code"]
            if observation.turn == 2 and observation.acting_player == 1 \
                    and not opponent_summoned:
                kind = "set_monster" if opponent_set else "normal_summon"
                action = next((a for a in actions if a.kind == kind), None)
                if action is not None:
                    opponent_summoned = True
                    opponent_code = action.parameters["code"]
            if observation.turn == 3 and observation.acting_player == 0 and not swap_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == CREATURE_SWAP), None)
                swap_used |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if swap_used and CREATURE_SWAP in {c.code for c in observation.graveyards[0]}:
                hidden = next(c for c in observation.field if c.controller == 1
                              and c.zone == "monster")
                assert hidden.position == "facedown" and hidden.code is None
                assert {(c.controller, c.zone, c.sequence, c.code)
                        for c in observation.known_opponent_field_cards} == {
                            (1, "monster", hidden.sequence, own_code)}
                assert any(c.code == opponent_code and c.controller == 0
                           for c in observation.field)
                other = env.engine.probe.observation(1)
                assert any(c.code == own_code and c.controller == 1
                           and c.position == "facedown" for c in other.field)
                if opponent_set:
                    assert any(c.controller == 0 and c.code == opponent_code
                               and c.position == "facedown" for c in observation.field)
                    assert any(c.controller == 0 and c.code is None
                               and c.position == "facedown" for c in other.field)
                    assert {(c.controller, c.zone, c.sequence, c.code)
                            for c in other.known_opponent_field_cards} == {
                                (0, "monster", 0, opponent_code)}
                agents = (RandomAgent(3), RandomAgent(4))
                for _ in range(5000):
                    action = agents[observation.acting_player].select_action(
                        observation, env.legal_actions())
                    observation = env.step(action)
                    if env.is_terminal():
                        trajectory = env.trajectory()
                        assert trajectory.schema_version == 22
                        path = tmp_path / f"creature_swap_set_{opponent_set}.json"
                        write_trajectory(path, trajectory)
                        assert verify_trajectory(read_trajectory(path),
                                                 ExperimentalOcgcoreEngine(root)) == len(
                                                     trajectory.decisions)
                        return
                pytest.fail("set-monster Creature Swap duel did not finish")
    pytest.fail("Creature Swap did not transfer the set monster")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_goat", [False, True])
def test_creature_swap_selects_new_sheep_tokens_after_chain(tmp_path, chain_goat):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{CREATURE_SWAP}.lua", f"goat/c{SCAPEGOAT}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("Creature Swap / Scapegoat scripts not installed")
    swap_deck = tmp_path / "swap.ydk"
    swap_deck.write_text("#main\n" + "\n".join(map(str, (
        CREATURE_SWAP, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    goat_deck = tmp_path / "goat.ydk"
    goat_deck.write_text("#main\n" + "\n".join(map(str, (
        SCAPEGOAT, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(swap_deck), str(goat_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert CREATURE_SWAP in {card.code for card in obs.hand}
        assert SCAPEGOAT in {card.code for card in env.engine.probe.observation(1).hand}
        own_summoned = opponent_summoned = goat_set = swap_used = False
        goat_chained = own_chosen = opponent_chosen = False
        own_code = opponent_code = None
        for _ in range(95):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not own_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    own_code = action.parameters["code"]
                    own_summoned = True
            if obs.turn == 2 and obs.acting_player == 1:
                if not opponent_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        opponent_code = action.parameters["code"]
                        opponent_summoned = True
                if opponent_summoned and not goat_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == SCAPEGOAT), None)
                    goat_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not swap_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == CREATURE_SWAP), action)
                swap_used |= action is not None and action.kind == "activate"
            if swap_used and obs.acting_player == 1 and obs.chain and not goat_chained:
                assert [link.card_code for link in obs.chain] == [CREATURE_SWAP]
                assert obs.chain[0].targets == ()
                goat = next((a for a in actions if a.kind == "chain"
                             and a.parameters.get("code") == SCAPEGOAT), None)
                assert goat is not None
                if chain_goat:
                    action = goat
                goat_chained = True
            if swap_used and actions[0].kind == "select_card":
                if obs.acting_player == 0 and not own_chosen:
                    assert {a.parameters.get("code") for a in actions} == {own_code}
                    action = actions[0]
                    own_chosen = True
                elif obs.acting_player == 1 and not opponent_chosen:
                    offered = {a.parameters.get("code") for a in actions}
                    assert (offered == ({opponent_code} | SHEEP_CODES)
                            if chain_goat else offered == {opponent_code})
                    action = next(a for a in actions if a.parameters.get("code")
                                  in (SHEEP_CODES if chain_goat else {opponent_code}))
                    opponent_chosen = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if own_chosen and opponent_chosen and CREATURE_SWAP in {
                    card.code for card in obs.graveyards[0]}:
                assert obs.life_points == (8000, 8000)
                own_monsters = {card.code for card in obs.field
                                if card.zone == "monster" and card.controller == 0}
                other_monsters = {card.code for card in obs.field
                                  if card.zone == "monster" and card.controller == 1}
                assert own_code in other_monsters
                if chain_goat:
                    assert len(own_monsters & SHEEP_CODES) == 1
                    assert opponent_code in other_monsters
                    assert len(other_monsters & SHEEP_CODES) == 3
                else:
                    assert own_monsters == {opponent_code}
                    assert not other_monsters & SHEEP_CODES
                assert f"official/c{CREATURE_SWAP}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                if chain_goat:
                    assert f"goat/c{SCAPEGOAT}.lua" in (
                        env.engine.probe.loaded_script_sha256)
                agents = (RandomAgent(52), RandomAgent(53))
                for _ in range(5000):
                    choice = agents[obs.acting_player].select_action(
                        obs, env.legal_actions())
                    obs = env.step(choice)
                    if env.is_terminal():
                        path = tmp_path / f"swap_goat_chain_{chain_goat}.json"
                        write_trajectory(path, env.trajectory())
                        assert verify_trajectory(read_trajectory(path),
                                                 ExperimentalOcgcoreEngine(root)) == len(
                                                     env.trajectory().decisions)
                        return
                pytest.fail("Creature Swap / Scapegoat duel did not finish")
    pytest.fail("Creature Swap / Scapegoat chain did not resolve")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_creature_swap_fails_when_ring_removes_only_opposing_monster(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{CREATURE_SWAP}.lua", f"pre-errata/c{RING}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("Creature Swap / Ring scripts not installed")
    swap_deck = tmp_path / "swap.ydk"
    swap_deck.write_text("#main\n" + "\n".join(map(str, (
        CREATURE_SWAP, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    ring_deck = tmp_path / "ring.ydk"
    ring_deck.write_text("#main\n" + "\n".join(map(str, (
        RING, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(swap_deck), str(ring_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert CREATURE_SWAP in {card.code for card in obs.hand}
        assert RING in {card.code for card in env.engine.probe.observation(1).hand}
        own_summoned = opponent_summoned = ring_set = swap_used = False
        ring_chained = ring_targeted = False
        own_code = opponent_code = opponent_attack = None
        for _ in range(95):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not own_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    own_code = action.parameters["code"]
                    own_summoned = True
            if obs.turn == 2 and obs.acting_player == 1:
                if not opponent_summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        opponent_code = action.parameters["code"]
                        opponent_summoned = True
                if opponent_summoned and not ring_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == RING), None)
                    ring_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not swap_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == CREATURE_SWAP), action)
                swap_used |= action is not None and action.kind == "activate"
            if swap_used and obs.acting_player == 1 and obs.chain and not ring_chained:
                assert [link.card_code for link in obs.chain] == [CREATURE_SWAP]
                ring = next((a for a in actions if a.kind == "chain"
                             and a.parameters.get("code") == RING), None)
                assert ring is not None
                opponent_attack = next(card.attack for card in obs.field
                                       if card.zone == "monster" and card.controller == 1)
                action = ring
                ring_chained = True
            if ring_chained and not ring_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == opponent_code and a.parameters.get("controller") == 1), None)
                ring_targeted |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if ring_targeted and CREATURE_SWAP in {card.code for card in obs.graveyards[0]}:
                assert obs.life_points == (8000 - opponent_attack,) * 2
                assert own_code in {card.code for card in obs.field
                                    if card.zone == "monster" and card.controller == 0}
                assert not any(card.zone == "monster" and card.controller == 1
                               for card in obs.field)
                assert opponent_code in {card.code for card in obs.graveyards[1]}
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                agents = (RandomAgent(52), RandomAgent(53))
                for _ in range(5000):
                    choice = agents[obs.acting_player].select_action(
                        obs, env.legal_actions())
                    obs = env.step(choice)
                    if env.is_terminal():
                        path = tmp_path / "swap_ring.json"
                        write_trajectory(path, env.trajectory())
                        assert verify_trajectory(read_trajectory(path),
                                                 ExperimentalOcgcoreEngine(root)) == len(
                                                     env.trajectory().decisions)
                        return
                pytest.fail("Creature Swap / Ring duel did not finish")
    pytest.fail("Creature Swap / Ring chain did not resolve")
