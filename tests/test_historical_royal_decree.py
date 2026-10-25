"""Royal Decree chained to Mirror Force negates the Trap effect."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

ROYAL_DECREE = 51452091
MIRROR_FORCE = 44095762


def _deck(path, cards):
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_decree", [False, True])
def test_decree_chained_to_mirror_force_saves_attacker(tmp_path, chain_decree):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (ROYAL_DECREE, MIRROR_FORCE):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    attacker = _deck(tmp_path / "decree.ydk", (
        *([ROYAL_DECREE] * 3), *VANILLA_DECK[3:]))
    defender = _deck(tmp_path / "mirror.ydk", (MIRROR_FORCE, *VANILLA_DECK[1:]))
    with GoatEnvironment(attacker, defender, seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        summoned = set_decree = set_mirror = battle = attacked = chained_mirror = False
        chained_decree = False
        mirror_resolved = False
        attacker_code = None
        for _ in range(65):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0:
                if not summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        attacker_code = action.parameters["code"]
                        summoned = True
                if action is None and not set_decree:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == ROYAL_DECREE), None)
                    set_decree |= action is not None
            if observation.turn == 2 and observation.acting_player == 1 and not set_mirror:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == MIRROR_FORCE), None)
                set_mirror |= action is not None
            if observation.turn == 3 and observation.acting_player == 0 \
                    and observation.phase == "main1" and not battle:
                action = next((a for a in actions if a.kind == "battle_phase"), None)
                battle |= action is not None
            if battle and observation.turn == 3 and observation.acting_player == 0 \
                    and observation.phase == "battle_start" and not attacked:
                action = next((a for a in actions if a.kind == "attack"
                               and a.parameters.get("code") == attacker_code), None)
                attacked |= action is not None
            if attacked and observation.acting_player == 1 and not chained_mirror:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == MIRROR_FORCE), None)
                chained_mirror |= action is not None
            if chained_mirror and chain_decree and observation.acting_player == 0 \
                    and not chained_decree:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == ROYAL_DECREE), None)
                if action is not None:
                    assert observation.chain[0].card_code == MIRROR_FORCE
                    chained_decree = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if chained_mirror and not mirror_resolved and any(
                    c.code == MIRROR_FORCE for c in observation.graveyards[1]):
                mirror_resolved = True
                assert observation.life_points == (8000, 8000)
                own_monsters = [c for c in observation.field
                                if c.controller == 0 and c.zone == "monster"]
                if chain_decree:
                    assert chained_decree
                    assert len(own_monsters) == 1
                    assert own_monsters[0].code == attacker_code
                    assert any(c.code == ROYAL_DECREE and c.position == "faceup"
                               for c in observation.field)
                    assert f"official/c{ROYAL_DECREE}.lua" in (
                        env.engine.probe.loaded_script_sha256)
                else:
                    assert not own_monsters
                    assert attacker_code in {c.code for c in observation.graveyards[0]}
                    assert any(c.code == ROYAL_DECREE and c.position == "facedown"
                               for c in observation.field)
                assert f"official/c{MIRROR_FORCE}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                if not chain_decree:
                    return
            if mirror_resolved and chain_decree and observation.life_points[1] < 8000:
                assert observation.life_points == (8000, 6100)
                assert any(c.code == attacker_code and c.controller == 0
                           for c in observation.field)
                return
    pytest.fail(f"Decree/Mirror chain did not resolve (decree={chain_decree})")
