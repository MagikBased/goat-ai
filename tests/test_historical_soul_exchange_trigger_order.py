"""Cross-controller GOAT trigger order for Soul Exchange and a Monarch."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment


SOUL_EXCHANGE = 68005187
SANGAN = 504700178  # Historical GOAT script.
THESTALOS = 26205777


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.xfail(
    strict=True,
    reason="pinned ocgcore places turn-player Thestalos before earlier opponent Sangan",
)
def test_soul_exchange_opponent_sangan_triggers_before_thestalos(tmp_path):
    """GoatFormat.com Rule #9 gives Sangan CL1 and Thestalos CL2 here."""
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    required = (f"official/c{SOUL_EXCHANGE}.lua", f"goat/c{SANGAN}.lua",
                f"official/c{THESTALOS}.lua")
    if any(not (root / "scripts" / name).is_file() for name in required):
        pytest.skip("full card script checkout not installed")
    attacker = tmp_path / "soul_thestalos.ydk"
    defender = tmp_path / "sangan.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        *([SOUL_EXCHANGE] * 3), *([THESTALOS] * 3), *VANILLA_DECK[6:])))
        + "\n#extra\n!side\n")
    defender.write_text("#main\n" + "\n".join(map(str, (
        SANGAN, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        summoned = soul_used = soul_targeted = thestalos_used = tribute_paid = False
        for _ in range(80):
            actions = env.legal_actions()

            def choose(kind, code=None):
                return next((a for a in actions if a.kind == kind and (
                    code is None or a.parameters.get("code") == code)), None)

            if tribute_paid and len(obs.chain) >= 2:
                assert tuple((link.index, link.card_code) for link in obs.chain[:2]) == (
                    (1, SANGAN), (2, THESTALOS))
                return

            action = None
            if obs.turn == 2 and obs.acting_player == 1 and not summoned:
                action = choose("normal_summon", SANGAN)
                summoned = action is not None
            if obs.turn == 3 and obs.acting_player == 0 and summoned:
                if not soul_used:
                    action = choose("activate", SOUL_EXCHANGE)
                    soul_used = action is not None
                elif soul_targeted and not thestalos_used:
                    action = choose("normal_summon", THESTALOS)
                    thestalos_used = action is not None
            if soul_used and not soul_targeted and choose("select_card"):
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 4), None)
                soul_targeted = action is not None
            if thestalos_used and not tribute_paid and choose("tribute"):
                action = choose("tribute", SANGAN)
                tribute_paid = action is not None
            if action is None:
                action = choose("place") or choose("pass") or choose("end_phase") or actions[0]
            obs = env.step(action)
        pytest.fail("Soul Exchange / Sangan / Thestalos chain was not reached")
