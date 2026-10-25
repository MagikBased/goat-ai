"""Pre-errata Night Assailant discard recovery and trigger timing."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

NIGHT_ASSAILANT = 16226796  # Pre-errata GOAT variant
GRACEFUL_CHARITY = 79571449
RAIGEKI_BREAK = 4178474
MAGICIAN_OF_FAITH = 31560081


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_two_night_assailants_discarded_together_recover_each_other(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for script in (f"pre-errata/c{NIGHT_ASSAILANT}.lua",
                   f"official/c{GRACEFUL_CHARITY}.lua"):
        if not (root / "scripts" / script).is_file():
            pytest.skip(f"script {script} not installed")
    deck = tmp_path / "night_assailants.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        NIGHT_ASSAILANT, NIGHT_ASSAILANT, GRACEFUL_CHARITY,
        *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        activated = discarded = False
        first_trigger = second_trigger = 0
        targets = []
        for _ in range(20):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not activated:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == GRACEFUL_CHARITY), None)
                activated |= action is not None
            if activated and not discarded and actions[0].kind == "select_cards":
                action = next((a for a in actions if [
                    c["code"] for c in a.parameters["cards"]].count(NIGHT_ASSAILANT) == 2),
                              None)
                assert action is not None
                discarded = True
            if discarded and actions[0].kind == "chain":
                assert len(actions) == 2
                assert all(a.parameters.get("code") == NIGHT_ASSAILANT for a in actions)
                assert sum(c.code == NIGHT_ASSAILANT for c in obs.graveyards[0]) == 2
                action = actions[0]
                first_trigger += 1
            if discarded and actions[0].kind == "select_card":
                assert len(actions) == 1
                assert actions[0].parameters["code"] == NIGHT_ASSAILANT
                assert actions[0].parameters["location"] == 16
                targets.append(actions[0].parameters["sequence"])
                action = actions[0]
                second_trigger += 1
            if action is None:
                action = next((a for a in actions if a.kind in ("pass", "place")),
                              actions[0])
            obs = env.step(action)
            own = env.engine.probe.observation(0)
            other = env.engine.probe.observation(1)
            if len(other.private_reveals) == 2:
                assert activated and discarded
                assert first_trigger == 1 and second_trigger == 2
                assert targets == [1, 0]
                assert sum(c.code == NIGHT_ASSAILANT for c in own.hand) == 2
                assert all(c.code != NIGHT_ASSAILANT for c in own.graveyards[0])
                assert other.opponent_hand_count == len(own.hand) == 8
                assert [reveal.recipient for reveal in other.private_reveals] == [1, 1]
                assert [[card.code for card in reveal.cards]
                        for reveal in other.private_reveals] == [
                            [NIGHT_ASSAILANT], [NIGHT_ASSAILANT]]
                assert not own.private_reveals
                loaded = env.engine.probe.loaded_script_sha256
                assert f"pre-errata/c{NIGHT_ASSAILANT}.lua" in loaded
                assert f"official/c{GRACEFUL_CHARITY}.lua" in loaded
                return
    pytest.fail("two Night Assailants did not recover each other")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_raigeki_break_discard_recovers_magician_after_trap_resolves(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for script in (f"pre-errata/c{NIGHT_ASSAILANT}.lua",
                   f"official/c{GRACEFUL_CHARITY}.lua",
                   f"official/c{RAIGEKI_BREAK}.lua"):
        if not (root / "scripts" / script).is_file():
            pytest.skip(f"script {script} not installed")
    deck = tmp_path / "night_break.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        GRACEFUL_CHARITY, *([RAIGEKI_BREAK] * 3), NIGHT_ASSAILANT,
        *([MAGICIAN_OF_FAITH] * 3), *VANILLA_DECK[8:])))
                    + "\n#extra\n!side\n")
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=418,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        graceful = charity_discard = trap_set = opponent_set = False
        break_activated = night_discarded = break_targeted = faith_targeted = False
        target_code = None
        for _ in range(55):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0:
                if not graceful:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == GRACEFUL_CHARITY), None)
                    graceful |= action is not None
                if graceful and not trap_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == RAIGEKI_BREAK), None)
                    trap_set |= action is not None
            if graceful and not charity_discard and actions[0].kind == "select_cards":
                action = next((a for a in actions if sum(
                    c["code"] == MAGICIAN_OF_FAITH for c in a.parameters["cards"]) == 1
                    and all(c["code"] not in (RAIGEKI_BREAK, NIGHT_ASSAILANT)
                            for c in a.parameters["cards"])), None)
                assert action is not None
                charity_discard = True
            if obs.turn == 2 and obs.acting_player == 1 and not opponent_set:
                action = next((a for a in actions if a.kind == "set_monster"), None)
                if action is not None:
                    target_code = action.parameters["code"]
                    opponent_set = True
            if obs.turn == 3 and obs.acting_player == 0 and not break_activated:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == RAIGEKI_BREAK), None)
                break_activated |= action is not None
            if break_activated and not night_discarded and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == NIGHT_ASSAILANT and a.parameters.get("location") == 2),
                              None)
                night_discarded = action is not None
            if night_discarded and not break_targeted and action is None \
                    and actions[0].kind == "select_card":
                assert NIGHT_ASSAILANT in {c.code for c in obs.graveyards[0]}
                hidden = next(c for c in obs.field if c.controller == 1
                              and c.zone == "monster")
                assert hidden.code is None
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 4
                               and a.parameters.get("sequence") == hidden.sequence), None)
                assert action is not None and "code" not in action.parameters
                break_targeted = True
            if break_targeted and not faith_targeted and action is None \
                    and actions[0].kind == "select_card":
                assert RAIGEKI_BREAK in {c.code for c in obs.graveyards[0]}
                assert target_code in {c.code for c in obs.graveyards[1]}
                assert NIGHT_ASSAILANT in {c.code for c in obs.graveyards[0]}
                action = next((a for a in actions if a.parameters.get("code")
                               == MAGICIAN_OF_FAITH
                               and a.parameters.get("location") == 16), None)
                faith_targeted = action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            other = env.engine.probe.observation(1)
            if other.private_reveals:
                own = env.engine.probe.observation(0)
                assert faith_targeted and break_targeted and charity_discard
                assert MAGICIAN_OF_FAITH in {c.code for c in own.hand}
                assert MAGICIAN_OF_FAITH not in {c.code for c in own.graveyards[0]}
                assert NIGHT_ASSAILANT in {c.code for c in own.graveyards[0]}
                assert target_code in {c.code for c in own.graveyards[1]}
                assert [[c.code for c in reveal.cards]
                        for reveal in other.private_reveals] == [[MAGICIAN_OF_FAITH]]
                assert not own.private_reveals
                loaded = env.engine.probe.loaded_script_sha256
                assert f"pre-errata/c{NIGHT_ASSAILANT}.lua" in loaded
                assert f"official/c{RAIGEKI_BREAK}.lua" in loaded
                return
    pytest.fail("Night Assailant did not recover Magician of Faith")
