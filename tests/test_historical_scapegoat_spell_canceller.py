"""Call revives Spell Canceller at CL2 to negate Scapegoat's effect."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SCAPEGOAT = 504700123
SPELL_CANCELLER = 84636823
CALL = 97077563
GRACEFUL = 79571449
RESTRICTION = "player0:cannot_summon_this_turn:scapegoat"
SHEEP_TOKENS = {73915052, 73915053, 73915054, 73915055}


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_call_spell_canceller_negates_goats_but_preserves_summon_restriction(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{SCAPEGOAT}.lua", f"official/c{SPELL_CANCELLER}.lua",
               f"official/c{CALL}.lua", f"official/c{GRACEFUL}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required historical card script not installed")
    own = tmp_path / "scapegoat.ydk"
    other = tmp_path / "spell_canceller_call.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        SCAPEGOAT, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    other.write_text("#main\n" + "\n".join(map(str, (
        SPELL_CANCELLER, CALL, GRACEFUL, *VANILLA_DECK[3:])))
                     + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(other), seed=10566,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert SCAPEGOAT in {card.code for card in obs.hand}
        assert {SPELL_CANCELLER, CALL, GRACEFUL} <= {
            card.code for card in env.engine.probe.observation(1).hand}
        graceful_used = canceller_discarded = call_set = goat_used = False
        call_chained = canceller_targeted = checked = False
        agents = (RandomAgent(10566), RandomAgent(10567))
        for _ in range(5000):
            if env.is_terminal():
                break
            actions = env.legal_actions()

            def choose(kind, code=None):
                return next((item for item in actions if item.kind == kind
                             and (code is None or item.parameters.get("code") == code)), None)

            if (canceller_targeted and not checked and obs.turn == 3
                    and obs.acting_player == 0 and obs.phase == "main1"
                    and not obs.chain and SCAPEGOAT in {
                        card.code for card in obs.graveyards[0]
                    } and choose("battle_phase") is not None):
                assert obs.life_points == (8000, 8000)
                assert RESTRICTION in obs.restrictions
                assert not any(item.kind in ("normal_summon", "special_summon")
                               for item in actions)
                assert not any(card.code in SHEEP_TOKENS for card in obs.field)
                assert any(card.code == SPELL_CANCELLER and card.controller == 1
                           for card in obs.field)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True

            action = None
            if obs.turn == 2 and obs.acting_player == 1 and not checked:
                if not graceful_used:
                    action = choose("activate", GRACEFUL)
                    graceful_used |= action is not None
                elif not canceller_discarded and actions[0].kind == "select_cards":
                    action = next((item for item in actions
                                   if item.kind == "select_cards"
                                   and len(item.parameters.get("cards", ())) == 2
                                   and any(card["code"] == SPELL_CANCELLER
                                           for card in item.parameters["cards"])
                                   and all(card["code"] != CALL
                                           for card in item.parameters["cards"])), None)
                    assert action is not None
                    canceller_discarded = True
                elif canceller_discarded and not call_set:
                    action = choose("set_spell_trap", CALL)
                    call_set |= action is not None
            if (obs.turn == 3 and obs.acting_player == 0 and call_set
                    and not goat_used and not checked):
                action = choose("activate", SCAPEGOAT) or action
                goat_used |= action is not None and action.kind == "activate" \
                    and action.parameters.get("code") == SCAPEGOAT
            if goat_used and obs.acting_player == 1 and not call_chained:
                option = choose("chain", CALL)
                if option is not None:
                    assert [link.card_code for link in obs.chain] == [SCAPEGOAT]
                    action = option
                    call_chained = True
            if call_chained and not canceller_targeted \
                    and actions[0].kind == "select_card":
                action = choose("select_card", SPELL_CANCELLER)
                assert action is not None
                canceller_targeted = True
            if action is None:
                action = (choose("place") or choose("select_position") or
                          choose("end_phase") or choose("pass") or
                          agents[obs.acting_player].select_action(obs, actions))
            obs = env.step(action)

        assert graceful_used and canceller_discarded and call_set and goat_used
        assert call_chained and canceller_targeted and checked
        assert env.is_terminal()
        path = tmp_path / "scapegoat_spell_canceller.json"
        write_trajectory(path, env.trajectory())
        replay = read_trajectory(path)
        assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(
            replay.decisions)
        assert audit_trajectory_visibility(replay)["decisions"] == len(replay.decisions)
