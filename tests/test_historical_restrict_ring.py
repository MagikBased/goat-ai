"""A chained Ring can remove Restrict or the monster it tries to equip."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

SCAPEGOAT = 504700123
METAMORPHOSIS = 46411259
RESTRICT = 504700102
RING = 511000824
SHEEP_CODES = {73915052, 73915053, 73915054, 73915055}


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("ring_hits_restrict", [False, True])
def test_ring_chained_to_restrict_removes_source_or_equip_target(tmp_path, ring_hits_restrict):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{SCAPEGOAT}.lua", f"official/c{METAMORPHOSIS}.lua",
                     f"goat/c{RESTRICT}.lua", f"pre-errata/c{RING}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    attacker = tmp_path / "goat.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        (SCAPEGOAT, METAMORPHOSIS) * 3 + VANILLA_DECK[6:])))
        + f"\n#extra\n{RESTRICT}\n!side\n")
    defender = tmp_path / "ring.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        RING, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        goat = meta = token = fusion = restrict = target = False
        summoned = set_ring = chained_ring = ring_target = False
        target_code = target_attack = None
        for _ in range(90):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not goat:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                goat |= action is not None
            if observation.turn == 2 and observation.acting_player == 1:
                if not summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        target_code = action.parameters["code"]
                        summoned = True
                if action is None and not set_ring:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == RING), None)
                    set_ring |= action is not None
            if observation.turn == 3 and observation.acting_player == 0 and not meta:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == METAMORPHOSIS), action)
                meta |= action is not None and action.kind == "activate"
            if meta and not token:
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") in SHEEP_CODES), action)
                token |= action is not None and action.kind == "select_card"
            if token and not fusion:
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == RESTRICT), action)
                fusion |= action is not None and action.kind == "select_card"
            if fusion and not restrict:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == RESTRICT), action)
                restrict |= action is not None and action.kind == "chain"
            if restrict and not target:
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("controller") == 1
                               and a.parameters.get("code") == target_code), action)
                target |= action is not None and action.kind == "select_card"
            if target and observation.acting_player == 1 and not chained_ring:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == RING), action)
                if action is not None and action.kind == "chain":
                    assert observation.chain[0].card_code == RESTRICT
                    chained_ring = True
            if chained_ring and not ring_target:
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("controller") == (0 if ring_hits_restrict else 1)
                               and a.parameters.get("code") == (
                                   RESTRICT if ring_hits_restrict else target_code)), action)
                ring_target |= action is not None and action.kind == "select_card"
                if ring_target:
                    target_attack = next(card.attack for card in observation.field
                                         if card.controller == (0 if ring_hits_restrict else 1)
                                         and card.code == (
                                             RESTRICT if ring_hits_restrict else target_code))
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if set_ring and not chained_ring and any(
                    card.code == RING for card in env.engine.probe.observation(1).field):
                attacker_view = env.engine.probe.observation(0)
                assert any(card.controller == 1 and card.zone == "spell_trap"
                           and card.position == "facedown" and card.code is None
                           for card in attacker_view.field)
            if ring_target and any(card.code == RING for card in observation.graveyards[1]):
                assert goat and meta and token and fusion and restrict and target
                assert summoned and set_ring and chained_ring
                assert observation.chain == ()
                assert observation.life_points == (8000 - target_attack,) * 2
                if ring_hits_restrict:
                    assert any(card.code == RESTRICT for card in observation.graveyards[0])
                    assert any(card.code == target_code and card.controller == 1
                               and card.zone == "monster" for card in observation.field)
                else:
                    assert any(card.code == target_code for card in observation.graveyards[1])
                    assert any(card.code == RESTRICT and card.controller == 0
                               for card in observation.field)
                    assert not any(card.zone == "spell_trap" and card.code == target_code
                                   for card in observation.field)
                assert f"goat/c{RESTRICT}.lua" in env.engine.probe.loaded_script_sha256
                assert f"pre-errata/c{RING}.lua" in env.engine.probe.loaded_script_sha256
                return
    pytest.fail(f"Ring line stalled: turn={observation.turn} phase={observation.phase} "
                f"goat={goat} meta={meta} token={token} fusion={fusion} "
                f"restrict={restrict} target={target} summon={summoned} set={set_ring} "
                f"ring={chained_ring} ring_target={ring_target}")
