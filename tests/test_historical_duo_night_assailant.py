"""Duo completes both discards before a discarded Night Assailant triggers."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

DUO = 44763025
GRACEFUL = 79571449
NIGHT = 16226796
FAITH = 31560081


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_duo_random_night_discard_triggers_after_chosen_discard(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"official/c{DUO}.lua", f"official/c{GRACEFUL}.lua",
               f"pre-errata/c{NIGHT}.lua")
    for relative in scripts:
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    attacker = tmp_path / "duo.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        DUO, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    defender = tmp_path / "night.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL, FAITH, NIGHT, FAITH, FAITH, NIGHT,
        *VANILLA_DECK[6:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=316,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert DUO in {c.code for c in observation.hand}
        assert {GRACEFUL, NIGHT, FAITH}.issubset(
            c.code for c in env.engine.probe.observation(1).hand)
        graceful = faith_discarded = duo = second_choice = faith_recovered = False
        second_code = None
        for _ in range(65):
            actions = env.legal_actions()
            action = None
            if observation.turn == 2 and observation.acting_player == 1:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL), None)
                    graceful |= action is not None
                if graceful and not faith_discarded \
                        and actions[0].kind == "select_cards":
                    action = next((a for a in actions if FAITH in {
                        c["code"] for c in a.parameters["cards"]}
                        and NIGHT not in {c["code"] for c in a.parameters["cards"]}),
                        None)
                    faith_discarded |= action is not None
            if observation.turn == 3 and observation.acting_player == 0 and not duo:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == DUO), None)
                duo |= action is not None
            if duo and observation.acting_player == 1 and not second_choice \
                    and actions[0].kind == "select_card":
                assert [link.card_code for link in observation.chain] == [DUO]
                assert NIGHT in {c.code for c in observation.graveyards[1]}
                assert FAITH in {c.code for c in observation.graveyards[1]}
                assert len(actions) == len(observation.hand) == 5
                assert all(a.parameters.get("location") == 2 for a in actions)
                attacker_view = env.engine.probe.observation(0)
                assert attacker_view.opponent_hand_count == 5
                assert attacker_view.known_opponent_hand_cards == ()
                assert not attacker_view.private_reveals
                action = next((a for a in actions if a.parameters.get("code")
                               not in (NIGHT, FAITH)), None)
                assert action is not None
                second_code = action.parameters["code"]
                second_choice = True
            if second_choice and action is None and observation.acting_player == 1 \
                    and not faith_recovered and actions[0].kind == "select_card":
                assert [link.card_code for link in observation.chain] == [NIGHT]
                assert second_code in {c.code for c in observation.graveyards[1]}
                assert NIGHT in {c.code for c in observation.graveyards[1]}
                assert not env.engine.probe.observation(0).private_reveals
                action = next((a for a in actions if a.parameters.get("code") == FAITH
                               and a.parameters.get("location") == 16), None)
                faith_recovered |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if faith_recovered and FAITH in {
                    c.code for c in env.engine.probe.observation(1).hand}:
                own = env.engine.probe.observation(1)
                other = env.engine.probe.observation(0)
                assert observation.chain == ()
                assert own.life_points == (7000, 8000)
                assert FAITH not in {c.code for c in own.graveyards[1]}
                assert {NIGHT, second_code}.issubset(
                    c.code for c in own.graveyards[1])
                assert other.known_opponent_hand_cards == (FAITH,)
                assert [[c.code for c in reveal.cards]
                        for reveal in other.private_reveals] == [[FAITH]]
                assert set(scripts).issubset(env.engine.probe.loaded_script_sha256)
                return
    pytest.fail(f"Duo/Night line stalled: Graceful={graceful}/{faith_discarded} "
                f"Duo={duo}/{second_choice} recovered={faith_recovered} "
                f"turn={observation.turn}")
