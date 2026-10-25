"""GOAT Bottomless chains to Breaker's summon-trigger Spell Counter placement."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

BREAKER = 71413901
BOTTOMLESS = 504700052
BOOK = 14087893


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("response", ["pass", "bottomless", "bottomless_book"])
def test_bottomless_chains_to_breaker_counter_placement(tmp_path, response):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{BREAKER}.lua", f"goat/c{BOTTOMLESS}.lua"}
    if response == "bottomless_book":
        scripts.add(f"official/c{BOOK}.lua")
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    attacker = tmp_path / "breaker.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        BREAKER, BOOK, *VANILLA_DECK[2:]) if response == "bottomless_book" else (
            BREAKER, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    defender = tmp_path / "bottomless.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        BOTTOMLESS, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert BREAKER in {c.code for c in obs.hand}
        if response == "bottomless_book":
            assert BOOK in {c.code for c in obs.hand}
        assert BOTTOMLESS in {c.code for c in env.engine.probe.observation(1).hand}
        own_summoned = trap_set = defender_summoned = breaker_summoned = False
        trap_offered = trap_chained = False
        book_set = book_chained = book_targeted = False
        own_code = defender_code = None
        for _ in range(95):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not own_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") != BREAKER), None)
                if action is not None:
                    own_code = action.parameters["code"]
                    own_summoned = True
            if response == "bottomless_book" and obs.turn == 1 \
                    and obs.acting_player == 0 and own_summoned \
                    and not book_set and action is None:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == BOOK), None)
                book_set |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not trap_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == BOTTOMLESS), None)
                    trap_set |= action is not None
                if trap_set and not defender_summoned and action is None:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        defender_code = action.parameters["code"]
                        defender_summoned = True
            if obs.turn == 3 and obs.acting_player == 0 and not breaker_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == BREAKER), action)
                breaker_summoned |= action is not None and action.kind == "normal_summon"
            if breaker_summoned and obs.acting_player == 1 and obs.chain \
                    and obs.chain[0].card_code == BREAKER and not trap_offered:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOTTOMLESS), None)
                assert option is not None
                assert [link.card_code for link in obs.chain] == [BREAKER]
                breaker = next(c for c in obs.field if c.code == BREAKER)
                assert (breaker.attack, breaker.counters) == (1600, ())
                trap_offered = True
                if response != "pass":
                    action = option
                    trap_chained = True
            if response == "bottomless_book" and trap_chained \
                    and obs.acting_player == 0 and not book_chained \
                    and [link.card_code for link in obs.chain] == [BREAKER, BOTTOMLESS]:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == BOOK), None)
                book_chained |= action is not None
            if book_chained and not book_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == BREAKER
                               and a.parameters.get("controller") == 0), None)
                book_targeted |= action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            resolved = (trap_chained and BOTTOMLESS in {
                c.code for c in obs.graveyards[1]}
                and (response != "bottomless_book" or BOOK in {
                    c.code for c in obs.graveyards[0]})
                or trap_offered and not trap_chained and any(
                    c.code == BREAKER and c.counters == ((1, 1),)
                    for c in obs.field))
            if resolved and not obs.chain and obs.turn == 3:
                assert all((own_summoned, trap_set, defender_summoned,
                            breaker_summoned, trap_offered))
                assert any(c.code == own_code and c.controller == 0
                           and c.zone == "monster" for c in obs.field)
                assert any(c.code == defender_code and c.controller == 1
                           and c.zone == "monster" for c in obs.field)
                assert obs.life_points == (8000, 8000)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                if response == "bottomless":
                    assert BREAKER in {c.code for c in obs.banished[0]}
                    assert BREAKER not in {c.code for c in obs.graveyards[0]}
                    assert not any(c.code == BREAKER for c in obs.field)
                elif response == "bottomless_book":
                    assert book_set and book_chained and book_targeted
                    assert not obs.banished[0]
                    breaker = next(c for c in obs.field if c.code == BREAKER)
                    assert breaker.controller == 0 and breaker.position == "facedown"
                    assert breaker.counters == ()
                    other_view = env.engine.probe.observation(1)
                    hidden = next(c for c in other_view.field if c.zone == "monster"
                                  and c.controller == 0 and c.sequence == breaker.sequence)
                    assert hidden.code is None and hidden.position == "facedown"
                    assert (0, "monster", hidden.sequence, BREAKER) in {
                        (c.controller, c.zone, c.sequence, c.code)
                        for c in other_view.known_opponent_field_cards}
                else:
                    breaker = next(c for c in obs.field if c.code == BREAKER)
                    assert (breaker.attack, breaker.counters) == (1900, ((1, 1),))
                    assert not obs.banished[0]
                    assert any(c.code == BOTTOMLESS and c.controller == 1
                               for c in env.engine.probe.observation(1).field)
                    assert any(c.zone == "spell_trap" and c.controller == 1
                               and c.code is None for c in obs.field)
                agents = (RandomAgent(52), RandomAgent(53))
                for _ in range(3000):
                    if env.is_terminal():
                        break
                    obs = env.step(agents[obs.acting_player].select_action(
                        obs, env.legal_actions()))
                else:
                    pytest.fail("Breaker / Bottomless continuation exceeded 3000 decisions")
                trajectory = env.trajectory()
                path = tmp_path / f"breaker_bottomless_{response}.json"
                write_trajectory(path, trajectory)
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                                             trajectory.decisions)
                return
        pytest.fail(f"Breaker / Bottomless line stalled: first={own_summoned} "
                    f"defender={trap_set}/{defender_summoned} breaker={breaker_summoned} "
                    f"trap={trap_offered}/{trap_chained} "
                    f"book={book_set}/{book_chained}/{book_targeted} "
                    f"turn={obs.turn} phase={obs.phase}")
