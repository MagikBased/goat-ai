"""A 2005 Spell Counter timing ruling on a real GOAT-mode duel."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

SKILLED = 504700122
POT = 55144522
SOLEMN = 41420027


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("negate_spell", [False, True])
def test_skilled_counter_requires_spell_activation_to_resolve(tmp_path, negate_spell):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{SKILLED}.lua", f"official/c{POT}.lua",
                     f"official/c{SOLEMN}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"{relative} not installed")
    own = tmp_path / "skilled.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        SKILLED, POT, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    other = tmp_path / "solemn.ydk"
    other.write_text("#main\n" + "\n".join(map(str, (
        SOLEMN, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(other), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {SKILLED, POT} <= {card.code for card in obs.hand}
        assert SOLEMN in {card.code for card in env.engine.probe.observation(1).hand}
        summoned = trap_set = pot_used = solemn_chained = False
        deck_before = None
        for _ in range(90):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == SKILLED), None)
                summoned = action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not trap_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SOLEMN), None)
                trap_set = action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not pot_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == POT), None)
                if action is not None:
                    pot_used = True
                    deck_before = obs.deck_counts[0]
            if pot_used and negate_spell and obs.acting_player == 1 \
                    and not solemn_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SOLEMN), None)
                if action is not None:
                    assert [link.card_code for link in obs.chain] == [POT]
                    solemn_chained = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if pot_used and not obs.chain and POT in {c.code for c in obs.graveyards[0]}:
                own_view = env.engine.probe.observation(0)
                skilled = next(c for c in own_view.field if c.code == SKILLED)
                assert skilled.position == "faceup"
                assert sum(count for _, count in skilled.counters) == (0 if negate_spell else 1)
                opponent_view = env.engine.probe.observation(1)
                public_skilled = next(c for c in opponent_view.field if c.code == SKILLED)
                assert public_skilled.counters == skilled.counters
                assert own_view.deck_counts[0] == deck_before - (0 if negate_spell else 2)
                assert own_view.life_points[1] == (4000 if negate_spell else 8000)
                assert solemn_chained == negate_spell
                assert {f"goat/c{SKILLED}.lua", f"official/c{POT}.lua"} \
                    <= env.engine.probe.loaded_script_sha256.keys()
                return
    pytest.fail("Skilled Dark Magician / Pot of Greed chain did not resolve")
