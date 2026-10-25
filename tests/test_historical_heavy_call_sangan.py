"""A historical tournament line: Heavy Storm, Call, then Sangan search."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

GRACEFUL = 79571449
CALL = 97077563
HEAVY = 19613556
SANGAN = 504700178
MYSTICAL_ELF = 15025844
MAD_DOG = 79182538


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_call_chained_to_heavy_revives_sangan_then_searches(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (GRACEFUL, CALL, HEAVY)}
    scripts.add(f"goat/c{SANGAN}.lua")
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")

    caller_cards = [GRACEFUL, CALL, SANGAN, *VANILLA_DECK[3:]]
    caller = tmp_path / "caller.ydk"
    caller.write_text("#main\n" + "\n".join(map(str, caller_cards)) + "\n#extra\n!side\n")
    storm = tmp_path / "storm.ydk"
    storm.write_text("#main\n" + "\n".join(map(str, (HEAVY, *VANILLA_DECK[1:])))
                     + "\n#extra\n!side\n")

    with GoatEnvironment(str(caller), str(storm), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GRACEFUL, CALL, SANGAN, MAD_DOG} <= {c.code for c in obs.hand}
        graceful = discarded = call_set = heavy = call_chained = targeted = searched = False
        for _ in range(75):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    graceful |= action is not None
                if graceful and not discarded and actions[0].kind == "select_cards":
                    action = next((a for a in actions if {c["code"] for c in
                                   a.parameters["cards"]} == {SANGAN, MAD_DOG}), None)
                    discarded |= action is not None
                if discarded and not call_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == CALL), None)
                    call_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and call_set and not heavy:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == HEAVY), None)
                heavy |= action is not None
            if heavy and obs.acting_player == 0 and not call_chained:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == CALL), None)
                call_chained |= action is not None
            if call_chained and not targeted and actions[0].kind == "select_card":
                assert [link.card_code for link in obs.chain] == [HEAVY, CALL]
                action = next((a for a in actions if a.parameters.get("code") == SANGAN
                               and a.parameters.get("location") == 16), None)
                targeted |= action is not None
            if (targeted and not searched and actions[0].kind == "select_card"
                    and actions[0].parameters.get("location") == 1):
                assert [link.card_code for link in obs.chain] == [SANGAN]
                assert obs.acting_player == 0
                assert not env.engine.probe.observation(1).known_opponent_hand_cards
                action = next((a for a in actions if a.parameters.get("code") == MYSTICAL_ELF
                               and a.parameters.get("location") == 1), None)
                assert action is not None
                assert "sequence" not in action.parameters
                searched = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if searched and not obs.chain:
                owner = env.engine.probe.observation(0)
                opponent = env.engine.probe.observation(1)
                assert {CALL, SANGAN} <= {c.code for c in owner.graveyards[0]}
                assert HEAVY in {c.code for c in owner.graveyards[1]}
                assert not any(c.code == SANGAN and c.zone == "monster" for c in owner.field)
                assert MYSTICAL_ELF in {c.code for c in owner.hand}
                assert opponent.known_opponent_hand_cards == (MYSTICAL_ELF,)
                assert [c.code for c in opponent.private_reveals[-1].cards] == [MYSTICAL_ELF]
                assert not owner.private_reveals
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                return
        pytest.fail(f"Heavy/Call/Sangan line stalled at turn {obs.turn}; "
                    f"Graceful={graceful}/{discarded} Call={call_set}/{call_chained}/{targeted} "
                    f"Heavy={heavy} searched={searched}")
