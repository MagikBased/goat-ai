"""Dimension Fusion revives pre-errata DMoC and offers immediate Spell recovery."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

GRACEFUL = 79571449
DMOC = 511001039
BAZOO = 40133511
DIMENSION_FUSION = 23557835
RETURN = 27174286
HEAVY_STORM = 19613556


@pytest.mark.parametrize("recover_spell", [False, True])
@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_dimension_fusion_dmoc_optional_spell_recovery(tmp_path, recover_spell):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"pre-errata/c{DMOC}.lua", f"official/c{BAZOO}.lua",
                     f"official/c{DIMENSION_FUSION}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")

    # Seed 100 starts with these four key cards; the filler swap changes no
    # card count and makes the opening line reproducible.
    cards = [GRACEFUL, DMOC, BAZOO, DIMENSION_FUSION, *VANILLA_DECK[4:]]
    cards[3], cards[17] = cards[17], cards[3]
    deck = tmp_path / "dmoc_dimension_fusion.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    opponent = Path(__file__).resolve().parent.parent / "examples/decks/vanilla_probe.ydk"

    with GoatEnvironment(str(deck), str(opponent), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert {GRACEFUL, DMOC, BAZOO, DIMENSION_FUSION} <= {
            card.code for card in observation.hand}
        stages: set[str] = set()
        checked = False
        random_agents = (RandomAgent(100), RandomAgent(1100))
        for _ in range(3000):
            actions = env.legal_actions()
            action = None
            if not checked and observation.acting_player == 0:
                if "graceful" not in stages:
                    action = next((item for item in actions if item.kind == "activate"
                                   and item.parameters.get("code") == GRACEFUL), None)
                    if action is not None:
                        stages.add("graceful")
                if (action is None and "graceful" in stages
                        and "discard" not in stages and actions[0].kind == "select_cards"):
                    action = next((item for item in actions if
                                   DMOC in {card.get("code") for card in
                                            item.parameters.get("cards", ())}
                                   and not {BAZOO, DIMENSION_FUSION} & {
                                       card.get("code") for card in
                                       item.parameters.get("cards", ())}), None)
                    assert action is not None
                    stages.add("discard")
                if action is None and "discard" in stages and "bazoo" not in stages:
                    action = next((item for item in actions if item.kind == "normal_summon"
                                   and item.parameters.get("code") == BAZOO), None)
                    if action is not None:
                        stages.add("bazoo")
                if action is None and "bazoo" in stages and "bazoo_effect" not in stages:
                    action = next((item for item in actions if item.kind == "chain"
                                   and item.parameters.get("code") == BAZOO), None)
                    if action is not None:
                        stages.add("bazoo_effect")
                if action is None and "bazoo_effect" in stages and "banish" not in stages:
                    action = next((item for item in actions if item.kind == "select_card"
                                   and item.parameters.get("code") == DMOC), None)
                    if action is not None:
                        stages.add("banish")
                if action is None and "banish" in stages and "fusion" not in stages:
                    assert DMOC in {card.code for card in observation.banished[0]}
                    action = next((item for item in actions if item.kind == "activate"
                                   and item.parameters.get("code") == DIMENSION_FUSION), None)
                    if action is not None:
                        stages.add("fusion")
                if action is None and "fusion" in stages and "dmoc_prompt" not in stages:
                    action = next((item for item in actions if item.kind == (
                        "yes" if recover_spell else "no")
                                   and item.parameters.get("code") == DMOC), None)
                    if action is not None:
                        assert DMOC in {card.code for card in observation.field}
                        assert DIMENSION_FUSION in {
                            card.code for card in observation.graveyards[0]}
                        assert observation.life_points == (6000, 8000)
                        stages.add("dmoc_prompt")
                if (action is None and recover_spell and "dmoc_prompt" in stages
                        and "spell_target" not in stages):
                    choices = {item.parameters.get("code") for item in actions
                               if item.kind == "select_card"}
                    if choices:
                        assert {DIMENSION_FUSION, GRACEFUL} <= choices
                        action = next(item for item in actions if item.kind == "select_card"
                                      and item.parameters.get("code") == DIMENSION_FUSION)
                        stages.add("spell_target")
                if action is None and "dmoc_prompt" in stages and not checked:
                    own_hand = {card.code for card in observation.hand}
                    grave = {card.code for card in observation.graveyards[0]}
                    if (DIMENSION_FUSION in own_hand if recover_spell
                            else DIMENSION_FUSION in grave):
                        assert {BAZOO, DMOC} <= {
                            card.code for card in observation.field
                            if card.controller == 0 and card.zone == "monster"}
                        assert DMOC not in {card.code for card in observation.banished[0]}
                        assert observation.life_points == (6000, 8000)
                        assert (DIMENSION_FUSION in grave) != recover_spell
                        opponent_view = env.engine.probe.observation(1)
                        assert (DIMENSION_FUSION in
                                opponent_view.known_opponent_hand_cards) == recover_spell
                        checked = True
            if action is None:
                if checked:
                    action = random_agents[observation.acting_player].select_action(
                        observation, actions)
                else:
                    action = next((item for item in actions if item.kind in (
                        "place", "select_position", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if env.is_terminal():
                assert checked and "dmoc_prompt" in stages
                assert ("spell_target" in stages) == recover_spell
                trajectory = env.trajectory()
                assert {f"pre-errata/c{DMOC}.lua", f"official/c{BAZOO}.lua",
                        f"official/c{DIMENSION_FUSION}.lua"} <= set(
                            env.engine.probe.loaded_script_sha256)
                break
        else:
            pytest.fail("DMoC/Dimension Fusion duel exceeded 3000 decisions")

    path = tmp_path / "dmoc_dimension_fusion.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    audit_trajectory_visibility(loaded)
    assert verify_trajectory(loaded, ExperimentalOcgcoreEngine(root)) == len(
        trajectory.decisions)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_dmoc_summoned_mid_chain_misses_spell_recovery(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"pre-errata/c{DMOC}.lua", f"official/c{BAZOO}.lua",
                     f"official/c{RETURN}.lua", f"official/c{HEAVY_STORM}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")

    own = [GRACEFUL, DMOC, BAZOO, RETURN, *VANILLA_DECK[4:]]
    own[3], own[17] = own[17], own[3]
    other = [HEAVY_STORM, *VANILLA_DECK[1:]]
    own_path = tmp_path / "dmoc_return.ydk"
    other_path = tmp_path / "heavy_storm.ydk"
    own_path.write_text("#main\n" + "\n".join(map(str, own)) + "\n#extra\n!side\n")
    other_path.write_text("#main\n" + "\n".join(map(str, other)) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own_path), str(other_path), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert {GRACEFUL, DMOC, BAZOO, RETURN} <= {
            card.code for card in observation.hand}
        assert HEAVY_STORM in {card.code for card in env.engine.probe.observation(1).hand}
        stages: set[str] = set()
        checked = False
        random_agents = (RandomAgent(100), RandomAgent(1100))
        for _ in range(3000):
            actions = env.legal_actions()
            action = None
            if not checked:
                if observation.acting_player == 0:
                    if "graceful" not in stages:
                        action = next((item for item in actions if item.kind == "activate"
                                       and item.parameters.get("code") == GRACEFUL), None)
                        if action is not None:
                            stages.add("graceful")
                    if (action is None and "graceful" in stages
                            and "discard" not in stages
                            and actions[0].kind == "select_cards"):
                        action = next((item for item in actions if
                                       DMOC in {card.get("code") for card in
                                                item.parameters.get("cards", ())}
                                       and not {BAZOO, RETURN} & {
                                           card.get("code") for card in
                                           item.parameters.get("cards", ())}), None)
                        assert action is not None
                        stages.add("discard")
                    if action is None and "discard" in stages and "bazoo" not in stages:
                        action = next((item for item in actions if
                                       item.kind == "normal_summon"
                                       and item.parameters.get("code") == BAZOO), None)
                        if action is not None:
                            stages.add("bazoo")
                    if action is None and "bazoo" in stages and "bazoo_effect" not in stages:
                        action = next((item for item in actions if item.kind == "chain"
                                       and item.parameters.get("code") == BAZOO), None)
                        if action is not None:
                            stages.add("bazoo_effect")
                    if (action is None and "bazoo_effect" in stages
                            and "banish" not in stages):
                        action = next((item for item in actions if item.kind == "select_card"
                                       and item.parameters.get("code") == DMOC), None)
                        if action is not None:
                            stages.add("banish")
                    if action is None and "banish" in stages and "set_return" not in stages:
                        assert DMOC in {card.code for card in observation.banished[0]}
                        action = next((item for item in actions if
                                       item.kind == "set_spell_trap"
                                       and item.parameters.get("code") == RETURN), None)
                        if action is not None:
                            stages.add("set_return")
                    if action is None and "heavy" in stages and "return_chain" not in stages:
                        assert tuple(link.card_code for link in observation.chain) == (
                            HEAVY_STORM,)
                        action = next((item for item in actions if item.kind == "chain"
                                       and item.parameters.get("code") == RETURN), None)
                        if action is not None:
                            stages.add("return_chain")
                elif observation.turn == 2 and "heavy" not in stages:
                    assert "set_return" in stages
                    action = next((item for item in actions if item.kind == "activate"
                                   and item.parameters.get("code") == HEAVY_STORM), None)
                    if action is not None:
                        stages.add("heavy")
                if ("return_chain" in stages and not observation.chain
                        and DMOC in {card.code for card in observation.field}
                        and HEAVY_STORM in {card.code for card in observation.graveyards[1]}):
                    assert observation.life_points == (4000, 8000)
                    assert RETURN in {card.code for card in observation.graveyards[0]}
                    assert GRACEFUL in {card.code for card in observation.graveyards[0]}
                    assert DMOC not in {card.code for card in observation.banished[0]}
                    assert not any(item.kind == "yes" and
                                   item.parameters.get("code") == DMOC for item in actions)
                    assert GRACEFUL not in env.engine.probe.observation(
                        1).known_opponent_hand_cards
                    checked = True
            if action is None:
                if checked:
                    action = random_agents[observation.acting_player].select_action(
                        observation, actions)
                else:
                    action = next((item for item in actions if item.kind in (
                        "place", "select_position", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if env.is_terminal():
                assert checked and "return_chain" in stages
                trajectory = env.trajectory()
                assert {f"pre-errata/c{DMOC}.lua", f"official/c{BAZOO}.lua",
                        f"official/c{RETURN}.lua", f"official/c{HEAVY_STORM}.lua"} <= set(
                            env.engine.probe.loaded_script_sha256)
                break
        else:
            pytest.fail("mid-chain DMoC duel exceeded 3000 decisions")

    path = tmp_path / "dmoc_mid_chain.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    audit_trajectory_visibility(loaded)
    assert verify_trajectory(loaded, ExperimentalOcgcoreEngine(root)) == len(
        trajectory.decisions)
