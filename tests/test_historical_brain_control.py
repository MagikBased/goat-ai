"""Pre-errata Brain Control, Book of Moon, and End Phase control return."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

BRAIN_CONTROL = 511002995  # pre-errata GOAT whitelist entry
BOOK_OF_MOON = 14087893
SCAPEGOAT = 504700123
METAMORPHOSIS = 46411259
RESTRICT = 504700102  # GOAT Fusion variant
SHEEP_CODES = {73915052, 73915053, 73915054, 73915055}


def _deck(path, cards):
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("book_timing", ["none", "chained", "after_control"])
def test_brain_control_and_book_timing(tmp_path, book_timing):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/pre-errata/c{BRAIN_CONTROL}.lua").is_file():
        pytest.skip("pre-errata Brain Control script not installed")
    if not (root / f"scripts/official/c{BOOK_OF_MOON}.lua").is_file():
        pytest.skip("Book of Moon script not installed")
    attacker = _deck(tmp_path / "brain.ydk", (
        *([BRAIN_CONTROL] * 3), *([BOOK_OF_MOON] * 3), *VANILLA_DECK[6:]))
    defender = _deck(tmp_path / "book.ydk", (
        *([BOOK_OF_MOON] * 3), *VANILLA_DECK[3:]))
    with GoatEnvironment(attacker, defender, seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        summoned = set_book = brain_used = book_used = took_control = False
        target_code = None
        for _ in range(65):
            actions = env.legal_actions()
            action = None
            if observation.turn == 2 and observation.acting_player == 1:
                if not summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        target_code = action.parameters["code"]
                        summoned = True
                if action is None and not set_book:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOOK_OF_MOON), None)
                    set_book |= action is not None
            if observation.turn == 3 and observation.acting_player == 0 and not brain_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == BRAIN_CONTROL), None)
                brain_used |= action is not None
                if action is not None:
                    other = env.engine.probe.observation(0)
                    assert any(c.controller == 1 and c.code is None
                               and c.zone == "spell_trap" for c in other.field)
            if brain_used and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == target_code), None)
                assert action is not None
                if not took_control and not book_used:
                    assert observation.life_points == (7200, 8000)
                    assert action.parameters["controller"] == 1
            if brain_used and book_timing == "chained" \
                    and observation.acting_player == 1 and not book_used:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK_OF_MOON), None)
                if option is not None:
                    action = option
                    book_used = True
            stolen = next((c for c in observation.field if c.zone == "monster"
                           and c.controller == 0 and c.code == target_code), None)
            if stolen is not None and brain_used:
                took_control = True
                if book_timing == "after_control" and not book_used \
                        and observation.acting_player == 0:
                    option = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == BOOK_OF_MOON), None)
                    if option is not None:
                        action = option
                        book_used = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if brain_used and book_timing == "chained" and BRAIN_CONTROL in {
                    c.code for c in observation.graveyards[0]} and BOOK_OF_MOON in {
                        c.code for c in observation.graveyards[1]}:
                assert not took_control
                assert any(c.controller == 1 and c.code == target_code
                           and c.position == "facedown" for c in
                           env.engine.probe.observation(1).field)
                assert observation.life_points == (7200, 8000)
                break
            if brain_used and observation.turn >= 4:
                assert took_control
                own = env.engine.probe.observation(1)
                returned = next(c for c in own.field if c.zone == "monster"
                                and c.code == target_code)
                assert returned.controller == 1
                assert returned.position == (
                    "facedown" if book_timing == "after_control" else "faceup")
                assert observation.life_points == (7200, 8000)
                if book_timing == "after_control":
                    assert book_used
                    attacker_view = env.engine.probe.observation(0)
                    hidden = next(c for c in attacker_view.field
                                  if c.controller == 1 and c.zone == "monster")
                    assert hidden.code is None and hidden.position == "facedown"
                    assert (1, "monster", hidden.sequence, target_code) in {
                        (c.controller, c.zone, c.sequence, c.code)
                        for c in attacker_view.known_opponent_field_cards}
                    agents = (RandomAgent(15), RandomAgent(16))
                    for _ in range(5000):
                        action = agents[observation.acting_player].select_action(
                            observation, env.legal_actions())
                        observation = env.step(action)
                        if env.is_terminal():
                            trajectory = env.trajectory()
                            assert trajectory.schema_version == 22
                            path = tmp_path / "brain_control.json"
                            write_trajectory(path, trajectory)
                            assert verify_trajectory(read_trajectory(path),
                                                     ExperimentalOcgcoreEngine(root)) == len(
                                                         trajectory.decisions)
                            break
                    else:
                        pytest.fail("Brain Control duel did not finish")
                break
        else:
            pytest.fail(f"Brain Control line did not finish ({book_timing})")
        assert f"pre-errata/c{BRAIN_CONTROL}.lua" in (
            env.engine.probe.loaded_script_sha256)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_pre_errata_brain_control_can_take_fusion_monster(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"scripts/pre-errata/c{BRAIN_CONTROL}.lua",
               f"scripts/goat/c{SCAPEGOAT}.lua",
               f"scripts/official/c{METAMORPHOSIS}.lua",
               f"scripts/goat/c{RESTRICT}.lua")
    if not all((root / script).is_file() for script in scripts):
        pytest.skip("Brain Control/Fusion line scripts not installed")
    attacker = _deck(tmp_path / "brain.ydk", (
        *([BRAIN_CONTROL] * 3), *VANILLA_DECK[3:]))
    defender = tmp_path / "metamorphosis.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        *([SCAPEGOAT] * 3), *([METAMORPHOSIS] * 3), *VANILLA_DECK[6:])))
        + f"\n#extra\n{RESTRICT}\n!side\n")
    with GoatEnvironment(attacker, str(defender), seed=11,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        goat = metamorphosis = paid_token = selected_fusion = False
        brain = selected_target = False
        for _ in range(70):
            actions = env.legal_actions()
            action = None
            if observation.turn == 2 and observation.acting_player == 1 and not goat:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                goat |= action is not None
            if action is None and observation.turn == 4 \
                    and observation.acting_player == 1 and not metamorphosis:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == METAMORPHOSIS), None)
                metamorphosis |= action is not None
            if action is None and metamorphosis and not paid_token:
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") in SHEEP_CODES), None)
                paid_token |= action is not None
            if action is None and paid_token and not selected_fusion:
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == RESTRICT), None)
                selected_fusion |= action is not None
                if action is not None:
                    assert action.parameters["location"] == 64
                    assert "sequence" not in action.parameters
            if action is None and observation.turn == 5 \
                    and observation.acting_player == 0 and not brain:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == BRAIN_CONTROL), None)
                brain |= action is not None
            if action is None and brain and not selected_target \
                    and actions[0].kind == "select_card":
                assert observation.life_points == (7200, 8000)
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == RESTRICT), None)
                selected_target |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "select_position", "pass", "end_phase")),
                    actions[0])
            observation = env.step(action)
            if selected_target and any(c.code == RESTRICT and c.controller == 0
                                       for c in observation.field):
                assert observation.life_points == (7200, 8000)
                assert observation.extra_deck_counts == (0, 0)
                assert sum(c.code in SHEEP_CODES for c in observation.field) == 3
                loaded = env.engine.probe.loaded_script_sha256
                assert f"pre-errata/c{BRAIN_CONTROL}.lua" in loaded
                assert f"official/c{METAMORPHOSIS}.lua" in loaded
                assert f"goat/c{SCAPEGOAT}.lua" in loaded
                assert f"goat/c{RESTRICT}.lua" in loaded
                return
    pytest.fail("pre-errata Brain Control did not take Thousand-Eyes Restrict")
