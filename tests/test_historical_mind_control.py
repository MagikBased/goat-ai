"""Mind Control's Tribute restriction survives Book of Moon until End Phase."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

MIND_CONTROL = 37520316
CANNON_SOLDIER = 11384280
BOOK_OF_MOON = 14087893
METAMORPHOSIS = 46411259
DARKFIRE_DRAGON = 17881964
MYSTICAL_ELF = 15025844


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("book_response", [False, True])
def test_mind_control_stolen_monster_cannot_be_tributed_and_returns(
        tmp_path, book_response):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (
        MIND_CONTROL, CANNON_SOLDIER, BOOK_OF_MOON)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("Mind Control / Cannon Soldier / Book scripts not installed")
    own = tmp_path / "mind_control.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        CANNON_SOLDIER, MIND_CONTROL, BOOK_OF_MOON, *VANILLA_DECK[3:])))
                   + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), "examples/decks/vanilla_probe.ydk", seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {CANNON_SOLDIER, MIND_CONTROL, BOOK_OF_MOON} <= {
            c.code for c in obs.hand}
        cannon_summoned = defender_summoned = mind_used = mind_targeted = False
        control_taken = book_used = book_targeted = cannon_used = tribute_paid = False
        battle_checked = returned = False
        stolen_code = None
        for _ in range(120):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not cannon_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == CANNON_SOLDIER), None)
                cannon_summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not defender_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    stolen_code = action.parameters["code"]
                    defender_summoned = True
            if obs.turn == 3 and obs.acting_player == 0 and not mind_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == MIND_CONTROL), None)
                mind_used |= action is not None
            if mind_used and not mind_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == stolen_code and a.parameters.get("controller") == 1),
                              None)
                assert action is not None
                mind_targeted = True
            if mind_targeted and obs.turn == 3 and obs.acting_player == 0 \
                    and not control_taken and not obs.chain:
                control_taken = any(c.code == stolen_code and c.controller == 0
                                    for c in obs.field)
            if control_taken and book_response and not book_used \
                    and obs.turn == 3 and obs.acting_player == 0:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == BOOK_OF_MOON), action)
                book_used |= action is not None and action.kind == "activate"
            if book_used and not book_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == stolen_code and a.parameters.get("controller") == 0),
                              None)
                assert action is not None
                book_targeted = True
            if control_taken and not cannon_used and obs.turn == 3 \
                    and obs.acting_player == 0 and not obs.chain \
                    and (not book_response or book_targeted) \
                    and actions[0].kind != "select_card":
                action = next((a for a in actions if a.kind in ("activate", "chain")
                               and a.parameters.get("code") == CANNON_SOLDIER), action)
                cannon_used |= action is not None and action.parameters.get("code") \
                    == CANNON_SOLDIER
            if cannon_used and not tribute_paid and actions[0].kind == "select_card":
                assert all(a.parameters.get("code") != stolen_code
                           for a in actions if a.kind == "select_card")
                assert all(a.parameters.get("controller") == 0
                           for a in actions if a.kind == "select_card")
                action = next((a for a in actions if a.parameters.get("code")
                               == CANNON_SOLDIER), None)
                assert action is not None
                tribute_paid = True
            if tribute_paid and not battle_checked and obs.turn == 3 \
                    and obs.acting_player == 0:
                if obs.phase == "main1" and not obs.chain:
                    action = next((a for a in actions if a.kind == "battle_phase"), action)
                elif obs.phase == "battle_start":
                    assert obs.life_points == (8000, 7500)
                    assert CANNON_SOLDIER in {c.code for c in obs.graveyards[0]}
                    assert not any(a.kind == "attack" for a in actions)
                    stolen = next(c for c in obs.field if c.controller == 0
                                  and c.zone == "monster")
                    assert stolen.code == stolen_code
                    assert stolen.position == ("facedown" if book_response
                                               else "faceup")
                    battle_checked = True
            if battle_checked and obs.turn == 4 and not returned:
                own_view = env.engine.probe.observation(0)
                other_view = env.engine.probe.observation(1)
                assert not any(c.controller == 0 and c.zone == "monster"
                               for c in own_view.field)
                returned_card = next(c for c in other_view.field
                                     if c.controller == 1 and c.zone == "monster")
                assert returned_card.code == stolen_code
                assert returned_card.position == ("facedown" if book_response
                                                  else "faceup")
                opponent_card = next(c for c in own_view.field
                                     if c.controller == 1 and c.zone == "monster")
                assert opponent_card.code == (None if book_response else stolen_code)
                if book_response:
                    assert (1, "monster", opponent_card.sequence, stolen_code) in {
                        (c.controller, c.zone, c.sequence, c.code)
                        for c in own_view.known_opponent_field_cards}
                assert MIND_CONTROL in {c.code for c in own_view.graveyards[0]}
                assert (BOOK_OF_MOON in {c.code for c in own_view.graveyards[0]}) \
                    == book_response
                required = (scripts if book_response else
                            scripts - {f"official/c{BOOK_OF_MOON}.lua"})
                assert required <= env.engine.probe.loaded_script_sha256.keys()
                returned = True
                agents = (RandomAgent(100), RandomAgent(101))
                for _ in range(5000):
                    obs = env.step(agents[obs.acting_player].select_action(
                        obs, env.legal_actions()))
                    if env.is_terminal():
                        path = tmp_path / f"mind_control_{book_response}.json"
                        write_trajectory(path, env.trajectory())
                        assert verify_trajectory(read_trajectory(path),
                                                 ExperimentalOcgcoreEngine(root)) == len(
                                                     env.trajectory().decisions)
                        return
                pytest.fail("Mind Control duel did not finish")
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "main2", "end_phase")), actions[0])
            obs = env.step(action)
    pytest.fail(f"Mind Control return did not occur: {returned}")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_mind_control_targets_set_monster_without_revealing_its_target(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{MIND_CONTROL}.lua").is_file():
        pytest.skip("Mind Control script not installed")
    own = tmp_path / "mind_control_set.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        CANNON_SOLDIER, MIND_CONTROL, BOOK_OF_MOON, *VANILLA_DECK[3:])))
                   + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), "examples/decks/vanilla_probe.ydk", seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert MIND_CONTROL in {c.code for c in obs.hand}
        monster_set = mind_used = targeted = stolen = returned = False
        monster_code = None
        for _ in range(90):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1 and not monster_set:
                action = next((a for a in actions if a.kind == "set_monster"), None)
                if action is not None:
                    monster_code = action.parameters["code"]
                    monster_set = True
            if obs.turn == 3 and obs.acting_player == 0 and not mind_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == MIND_CONTROL), None)
                mind_used |= action is not None
            if mind_used and not targeted and actions[0].kind == "select_card":
                assert obs.acting_player == obs.viewer == 0
                hidden = next(c for c in obs.field if c.zone == "monster"
                              and c.controller == 1)
                assert hidden.code is None and hidden.position == "facedown"
                assert len(actions) == 1
                action = actions[0]
                assert action.parameters.get("controller") == 1
                assert "code" not in action.parameters
                targeted = True
            if targeted and not stolen and obs.turn == 3 and obs.acting_player == 0 \
                    and not obs.chain:
                controlled = next((c for c in obs.field if c.zone == "monster"
                                   and c.controller == 0), None)
                if controlled is not None:
                    assert controlled.code == monster_code
                    assert controlled.position == "facedown"
                    other_view = env.engine.probe.observation(1)
                    former_card = next(c for c in other_view.field
                                       if c.zone == "monster" and c.controller == 0)
                    assert former_card.code is None
                    assert former_card.position == "facedown"
                    stolen = True
            if stolen and obs.turn == 4 and not returned:
                own_view = env.engine.probe.observation(0)
                other_view = env.engine.probe.observation(1)
                returned_card = next(c for c in other_view.field
                                     if c.zone == "monster" and c.controller == 1)
                assert returned_card.code == monster_code
                assert returned_card.position == "facedown"
                hidden = next(c for c in own_view.field if c.zone == "monster"
                              and c.controller == 1)
                assert hidden.code is None and hidden.position == "facedown"
                assert (1, "monster", hidden.sequence, monster_code) in {
                    (c.controller, c.zone, c.sequence, c.code)
                    for c in own_view.known_opponent_field_cards}
                assert MIND_CONTROL in {c.code for c in own_view.graveyards[0]}
                assert f"official/c{MIND_CONTROL}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                returned = True
                agents = (RandomAgent(100), RandomAgent(101))
                for _ in range(5000):
                    obs = env.step(agents[obs.acting_player].select_action(
                        obs, env.legal_actions()))
                    if env.is_terminal():
                        path = tmp_path / "mind_control_set.json"
                        write_trajectory(path, env.trajectory())
                        assert verify_trajectory(read_trajectory(path),
                                                 ExperimentalOcgcoreEngine(root)) == len(
                                                     env.trajectory().decisions)
                        return
                pytest.fail("Mind Control set-target duel did not finish")
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
    pytest.fail(f"Mind Control set-target return did not occur: {returned}")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_mind_control_prevents_metamorphosis_tribute_of_stolen_monster(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (MIND_CONTROL, METAMORPHOSIS)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("Mind Control / Metamorphosis scripts not installed")
    own = tmp_path / "mind_metamorphosis.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        CANNON_SOLDIER, MIND_CONTROL, METAMORPHOSIS, *VANILLA_DECK[3:])))
                   + f"\n#extra\n{DARKFIRE_DRAGON}\n!side\n")

    with GoatEnvironment(str(own), "examples/decks/vanilla_probe.ydk", seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {CANNON_SOLDIER, MIND_CONTROL, METAMORPHOSIS} <= {
            c.code for c in obs.hand}
        assert MYSTICAL_ELF in {
            c.code for c in env.engine.probe.observation(1).hand}
        cannon_summoned = elf_summoned = mind_used = mind_targeted = False
        meta_used = own_tributed = fusion_selected = False
        for _ in range(100):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not cannon_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == CANNON_SOLDIER), None)
                cannon_summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not elf_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == MYSTICAL_ELF), None)
                elf_summoned |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not mind_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == MIND_CONTROL), None)
                mind_used |= action is not None
            if mind_used and not mind_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == MYSTICAL_ELF and a.parameters.get("controller") == 1),
                              None)
                assert action is not None
                mind_targeted = True
            if mind_targeted and not meta_used and obs.turn == 3 \
                    and obs.acting_player == 0 and not obs.chain \
                    and any(c.code == MYSTICAL_ELF and c.controller == 0
                            for c in obs.field):
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == METAMORPHOSIS), None)
                meta_used |= action is not None
            if meta_used and not own_tributed and actions[0].kind == "select_card":
                assert len(actions) == 1
                assert actions[0].parameters.get("code") == CANNON_SOLDIER
                assert actions[0].parameters.get("controller") == 0
                assert MYSTICAL_ELF in {c.code for c in obs.field}
                action = actions[0]
                own_tributed = True
            if own_tributed and not fusion_selected and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == DARKFIRE_DRAGON), None)
                fusion_selected |= action is not None
            if fusion_selected and obs.turn == 3 and obs.acting_player == 0 \
                    and obs.chain == () and any(c.code == DARKFIRE_DRAGON
                                                for c in obs.field):
                assert CANNON_SOLDIER in {c.code for c in obs.graveyards[0]}
                assert METAMORPHOSIS in {c.code for c in obs.graveyards[0]}
                assert any(c.code == MYSTICAL_ELF and c.controller == 0
                           for c in obs.field)
                assert obs.life_points == (8000, 8000)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                agents = (RandomAgent(100), RandomAgent(101))
                for _ in range(5000):
                    obs = env.step(agents[obs.acting_player].select_action(
                        obs, env.legal_actions()))
                    if env.is_terminal():
                        path = tmp_path / "mind_metamorphosis.json"
                        write_trajectory(path, env.trajectory())
                        assert verify_trajectory(read_trajectory(path),
                                                 ExperimentalOcgcoreEngine(root)) == len(
                                                     env.trajectory().decisions)
                        return
                pytest.fail("Mind Control / Metamorphosis duel did not finish")
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
    pytest.fail("Mind Control / Metamorphosis cost choice did not resolve")
