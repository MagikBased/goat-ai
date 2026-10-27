"""Sourced 2008 Synchro interactions in MR1; not complete Edison rules."""

import hashlib
import json
import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.mr1_synchro_probe import (
    BLACK_ROSE_DRAGON,
    BOKOICHI,
    GOYO_GUARDIAN,
    JUNK_SYNCHRON,
    JUNK_WARRIOR,
    MIRROR_FORCE,
    STARDUST_DRAGON,
    Mr1SynchroProbeEngine,
)
from goat_ai.engine.ocgcore_probe import MR1_FLAGS
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory
from scripts.record_mr1_black_rose_probe import GEMINI_ELF, record_probe
from scripts.record_mr1_goyo_probe import DARK_BLADE, GIANT_SOLDIER
from scripts.record_mr1_goyo_probe import record_probe as record_goyo_probe
from scripts.record_mr1_stardust_black_rose_probe import (
    SURVIVING_NORMAL,
)
from scripts.record_mr1_stardust_black_rose_probe import (
    record_probe as record_stardust_black_rose_probe,
)
from scripts.record_mr1_stardust_probe import record_probe as record_stardust_probe
from scripts.record_mr1_synchro_probe import record_attack_probe, select_setup_action
from scripts.render_replay import render_replay

ROOT = Path(__file__).resolve().parents[1]
DECK = ROOT / "examples/decks/mr1_junk_warrior_probe.ydk"
OPPONENT = ROOT / "examples/decks/vanilla_reverse.ydk"


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_mr1_junk_warrior_synchro_complete_duel(tmp_path):
    native_root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    engine = Mr1SynchroProbeEngine(native_root)
    with GoatEnvironment(str(DECK), str(OPPONENT), seed=3, engine=engine) as env:
        view = env.reset()
        agents = (RandomAgent(3), RandomAgent(4))
        summoned_at = None
        for index in range(5000):
            actions = env.legal_actions()
            action = (select_setup_action(view, actions) if summoned_at is None else
                      agents[view.acting_player].select_action(view, actions))
            view = env.step(action)
            if summoned_at is None and any(card.code == JUNK_WARRIOR
                                           for card in view.field):
                summoned_at = index + 1
                assert view.acting_player == 0
                assert {card.code for card in view.graveyards[0]} >= {
                    JUNK_SYNCHRON, BOKOICHI}
            if env.is_terminal():
                break
        else:
            pytest.fail("MR1 Synchro duel exceeded decision cap")
        trajectory = env.trajectory()
        assert engine.probe.flags == MR1_FLAGS
        assert engine.probe.loaded_script_sha256["utility.lua"] == hashlib.sha256(
            (native_root / "scripts/utility.lua").read_bytes()).hexdigest()
        assert "official/c63977008.lua" in engine.probe.loaded_script_sha256
        assert "official/c60800381.lua" in engine.probe.loaded_script_sha256
    assert summoned_at == 55
    assert any(card.code == JUNK_WARRIOR and card.attack == 2300
               for record in trajectory.decisions[55:]
               if record.observation.turn == 3
               for card in record.observation.field)
    assert len(trajectory.decisions) == 1439
    assert trajectory.winner == 1
    assert trajectory.ruleset == "mr1-synchro-protocol"
    path = tmp_path / "mr1_synchro.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    assert verify_trajectory(loaded, Mr1SynchroProbeEngine(native_root)) == 1439
    assert audit_trajectory_visibility(loaded)["decisions"] == 1439
    output = tmp_path / "mr1_synchro.html"
    assert render_replay(path, output, native_root, reviewer_reveal=True)[0] == 1439
    review = json.loads(output.with_suffix(".review.json").read_text())
    assert review["source_trajectory_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert len(review["frames"]) == 1440
    assert any(JUNK_WARRIOR in frame["extra"][0] for frame in review["frames"])


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_mr1_junk_warrior_gains_atk_from_surviving_level_two(tmp_path):
    native_root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    trajectory, (summoned_at, boosted_at) = record_attack_probe(native_root)
    assert (summoned_at, boosted_at) == (69, 73)
    assert len(trajectory.decisions) == 1202
    assert trajectory.winner == 1
    before = trajectory.decisions[boosted_at - 1].observation
    after = trajectory.decisions[boosted_at].observation
    assert next(card.attack for card in before.field
                if card.code == JUNK_WARRIOR) == 2300
    assert next(card.attack for card in after.field
                if card.code == JUNK_WARRIOR) == 2800
    assert sum(card.code == BOKOICHI and card.controller == 0
               for card in after.field) == 1
    path = tmp_path / "junk_warrior_atk.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    assert verify_trajectory(loaded, Mr1SynchroProbeEngine(native_root)) == 1202
    assert audit_trajectory_visibility(loaded)["decisions"] == 1202


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_mr1_junk_warrior_excludes_opposing_level_two_atk(tmp_path):
    native_root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    trajectory, (summoned_at, resolved_at) = record_attack_probe(
        native_root, opposing_level_two=True)
    assert (summoned_at, resolved_at) == (69, 73)
    assert len(trajectory.decisions) == 1592
    assert trajectory.winner == 1
    after = trajectory.decisions[resolved_at].observation
    assert next(card.attack for card in after.field
                if card.code == JUNK_WARRIOR) == 2300
    assert sum(card.code == BOKOICHI and card.controller == 1
               for card in after.field) == 1
    assert not any(card.code == BOKOICHI and card.controller == 0
                   for card in after.field)
    path = tmp_path / "junk_warrior_opposing_level2.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    assert verify_trajectory(loaded, Mr1SynchroProbeEngine(native_root)) == 1592
    assert audit_trajectory_visibility(loaded)["decisions"] == 1592


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_mr1_synchro_probe_rejects_unsourced_extra_card(tmp_path):
    native_root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck = tmp_path / "brionac.ydk"
    deck.write_text(DECK.read_text().replace(str(JUNK_WARRIOR), "50321796"))
    with (GoatEnvironment(str(deck), str(OPPONENT), seed=3,
                          engine=Mr1SynchroProbeEngine(native_root)) as env,
          pytest.raises(ValueError, match="MR1 Synchro probe allows only")):
        env.reset()


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("activate,decisions", ((True, 1281), (False, 1389)))
def test_mr1_goyo_uses_2010_generic_tuner_and_optional_recruit(
        tmp_path, activate, decisions):
    native_root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    trajectory, choice, loaded_script = record_goyo_probe(native_root, activate=activate)
    assert choice == ("yes" if activate else "no", 71)
    assert len(trajectory.decisions) == decisions
    assert trajectory.ruleset == "mr1-synchro-protocol"
    assert loaded_script == "4c2dc55206a96699a270b1ad1ef74ae2760795b9e402026b9b22869704769f27"
    raw_script = native_root / f"scripts/official/c{GOYO_GUARDIAN}.lua"
    assert hashlib.sha256(raw_script.read_bytes()).hexdigest() != loaded_script
    summon = next(record for record in trajectory.decisions
                  if any(card.code == GOYO_GUARDIAN for card in record.observation.field))
    assert {JUNK_SYNCHRON, GIANT_SOLDIER} <= {
        card.code for card in summon.observation.graveyards[0]}
    branch = trajectory.decisions[choice[1] + 3].observation
    if activate:
        assert any(card.code == DARK_BLADE and card.controller == 0
                   and card.orientation == "defense" for card in branch.field)
    else:
        assert not any(card.code == DARK_BLADE for card in branch.field)
        assert any(card.code == DARK_BLADE for card in branch.graveyards[1])
    path = tmp_path / f"goyo_{activate}.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    assert verify_trajectory(loaded, Mr1SynchroProbeEngine(native_root)) == decisions
    assert audit_trajectory_visibility(loaded)["decisions"] == decisions


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("activate,decisions", ((True, 1258), (False, 1376)))
def test_mr1_black_rose_optional_wipe_completes_and_replays(
        tmp_path, activate, decisions):
    native_root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    trajectory, choice = record_probe(native_root, 3, activate=activate)
    assert choice == ("yes" if activate else "no", 36)
    assert len(trajectory.decisions) == decisions
    assert trajectory.winner == 1
    assert trajectory.ruleset == "mr1-synchro-protocol"
    assert trajectory.asset_sha256["scripts/utility.lua"] == hashlib.sha256(
        (native_root / "scripts/utility.lua").read_bytes()).hexdigest()
    assert "scripts/official/c73580471.lua" in trajectory.asset_sha256
    assert "scripts/official/c63977008.lua" in trajectory.asset_sha256
    after_choice = [record.observation for record in trajectory.decisions[choice[1]:]
                    if record.observation.turn == 3]
    if activate:
        assert any(not {BLACK_ROSE_DRAGON, GEMINI_ELF} & {
            card.code for card in view.field} and
            BLACK_ROSE_DRAGON in {card.code for card in view.graveyards[0]} and
            GEMINI_ELF in {card.code for card in view.graveyards[1]}
            for view in after_choice)
    else:
        assert any({BLACK_ROSE_DRAGON, GEMINI_ELF} <= {
            card.code for card in view.field}
            for view in after_choice)
    path = tmp_path / "black_rose.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    assert verify_trajectory(loaded, Mr1SynchroProbeEngine(native_root)) == decisions
    assert audit_trajectory_visibility(loaded)["decisions"] == decisions


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_mr1_black_rose_obeys_march_2010_one_copy_limit(tmp_path):
    native_root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck = tmp_path / "two_black_rose.ydk"
    source = (ROOT / "examples/decks/mr1_black_rose_probe.ydk").read_text()
    deck.write_text(source.replace("#extra\n73580471\n", "#extra\n73580471\n73580471\n"))
    with (GoatEnvironment(str(deck), str(OPPONENT), seed=3,
                          engine=Mr1SynchroProbeEngine(native_root)) as env,
          pytest.raises(ValueError, match="exceeds Edison copy limit 1")):
        env.reset()


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("negate,decisions,destroyed,revived", (
    (True, 1413, 58, 68), (False, 1465, 57, None)))
def test_mr1_stardust_negates_mirror_force_and_returns_at_end_phase(
        tmp_path, negate, decisions, destroyed, revived):
    native_root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    trajectory, (choice, destruction, return_step) = record_stardust_probe(
        native_root, negate=negate)
    assert choice == ("chain" if negate else "pass", 56)
    assert (destruction, return_step) == (destroyed, revived)
    assert len(trajectory.decisions) == decisions
    assert trajectory.winner == 1
    assert trajectory.ruleset == "mr1-synchro-protocol"
    for code in (44508094, 44095762, 63977008):
        assert f"scripts/official/c{code}.lua" in trajectory.asset_sha256
    chain_view = trajectory.decisions[choice[1] - 1].observation
    assert any(card.code == STARDUST_DRAGON and card.controller == 0
               for card in chain_view.field)
    assert any(card.code == MIRROR_FORCE and card.controller == 1
               for card in chain_view.field)
    before_activation = trajectory.decisions[53].observation
    assert any(card.code is None and card.controller == 1
               for card in before_activation.field)
    after_force = trajectory.decisions[destroyed].observation
    assert STARDUST_DRAGON in {card.code for card in after_force.graveyards[0]}
    assert MIRROR_FORCE in {card.code for card in after_force.graveyards[1]}
    assert STARDUST_DRAGON not in {card.code for card in after_force.field}
    if negate:
        assert after_force.life_points == (8000, 8000)
        returned = trajectory.decisions[revived].observation
        assert returned.turn == 5 and returned.phase == "end"
        assert any(card.code == STARDUST_DRAGON and card.controller == 0
                   for card in returned.field)
        assert STARDUST_DRAGON not in {card.code for card in returned.graveyards[0]}
    else:
        assert after_force.life_points == (8000, 8000)
        assert not any(card.code == STARDUST_DRAGON
                       for record in trajectory.decisions[destroyed:]
                       if record.observation.turn == 5
                       for card in record.observation.field)
    path = tmp_path / "stardust.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    assert verify_trajectory(loaded, Mr1SynchroProbeEngine(native_root)) == decisions
    assert audit_trajectory_visibility(loaded)["decisions"] == decisions


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("negate,decisions,resolved,revived", (
    (True, 1621, 79, 88), (False, 1230, 78, None)))
def test_mr1_stardust_response_to_black_rose_wipe_completes_and_replays(
        tmp_path, negate, decisions, resolved, revived):
    native_root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    trajectory, (choice, resolution, returned) = record_stardust_black_rose_probe(
        native_root, negate=negate)
    assert choice == ("chain" if negate else "pass", 77)
    assert (resolution, returned) == (resolved, revived)
    assert len(trajectory.decisions) == decisions
    assert trajectory.winner == 1
    assert trajectory.ruleset == "mr1-synchro-protocol"
    for code in (BLACK_ROSE_DRAGON, STARDUST_DRAGON, JUNK_SYNCHRON):
        assert f"scripts/official/c{code}.lua" in trajectory.asset_sha256
    response = trajectory.decisions[choice[1] - 1]
    assert [(link.card_code, link.controller) for link in response.observation.chain] == [
        (BLACK_ROSE_DRAGON, 1)]
    assert {(card.code, card.controller) for card in response.observation.field} >= {
        (BLACK_ROSE_DRAGON, 1), (STARDUST_DRAGON, 0), (SURVIVING_NORMAL, 1)}
    assert response.selected_action.kind == choice[0]
    after = trajectory.decisions[resolution].observation
    assert BLACK_ROSE_DRAGON in {card.code for card in after.graveyards[1]}
    assert STARDUST_DRAGON in {card.code for card in after.graveyards[0]}
    assert ((SURVIVING_NORMAL, 1) in {
        (card.code, card.controller) for card in after.field}) == negate
    if negate:
        returned_view = trajectory.decisions[revived].observation
        assert returned_view.turn == 6 and returned_view.phase == "end"
        assert (STARDUST_DRAGON, 0) in {
            (card.code, card.controller) for card in returned_view.field}
        assert STARDUST_DRAGON not in {
            card.code for card in returned_view.graveyards[0]}
    else:
        assert not any(card.code == STARDUST_DRAGON
                       for record in trajectory.decisions[resolution:]
                       if record.observation.turn == 6
                       for card in record.observation.field)
    path = tmp_path / "stardust_black_rose.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    assert verify_trajectory(loaded, Mr1SynchroProbeEngine(native_root)) == decisions
    assert audit_trajectory_visibility(loaded)["decisions"] == decisions
