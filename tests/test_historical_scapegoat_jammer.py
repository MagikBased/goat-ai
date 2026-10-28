"""Magic Jammer negates GOAT Scapegoat's activation and its Summon restriction."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SCAPEGOAT = 504700123  # GOAT variant
MAGIC_JAMMER = 77414722
RESTRICTION = "player0:cannot_summon_this_turn:scapegoat"
SHEEP_TOKENS = {73915052, 73915053, 73915054, 73915055}


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_magic_jammer_negates_scapegoat_activation_and_restores_summon_permission(
    tmp_path,
):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{SCAPEGOAT}.lua", f"official/c{MAGIC_JAMMER}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required historical card script not installed")
    own = tmp_path / "scapegoat.ydk"
    other = tmp_path / "response.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        SCAPEGOAT, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    other.write_text("#main\n" + "\n".join(map(str, (
        MAGIC_JAMMER, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(other), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert SCAPEGOAT in {card.code for card in obs.hand}
        assert MAGIC_JAMMER in {card.code for card in env.engine.probe.observation(1).hand}
        trap_set = goat_used = responded = discarded = checked = False
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(3000):
            if env.is_terminal():
                break
            actions = env.legal_actions()

            def choose(kind, code=None):
                return next((item for item in actions if item.kind == kind
                             and (code is None or item.parameters.get("code") == code)), None)

            if (responded and not checked and obs.turn == 3
                    and obs.acting_player == 0 and obs.phase == "main1"
                    and not obs.chain and SCAPEGOAT in {
                        card.code for card in obs.graveyards[0]
                    } and choose("battle_phase") is not None):
                assert obs.life_points == (8000, 8000)
                assert sum(card.code in SHEEP_TOKENS for card in obs.field) == 0
                assert RESTRICTION not in obs.restrictions
                assert choose("normal_summon") is not None
                assert discarded
                assert MAGIC_JAMMER in {card.code for card in obs.graveyards[1]}
                assert len(obs.graveyards[1]) >= 2
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True

            action = None
            if not checked and obs.turn == 2 and obs.acting_player == 1 \
                    and not trap_set:
                action = choose("set_spell_trap", MAGIC_JAMMER)
                trap_set |= action is not None
            if not checked and obs.turn == 3 and obs.acting_player == 0 \
                    and obs.phase == "main1" and trap_set and not goat_used:
                action = choose("activate", SCAPEGOAT) or action
                goat_used |= action is not None and action.kind == "activate" \
                    and action.parameters.get("code") == SCAPEGOAT
            if not checked and goat_used and obs.acting_player == 1 \
                    and not responded:
                option = choose("chain", MAGIC_JAMMER)
                if option is not None:
                    assert [link.card_code for link in obs.chain] == [SCAPEGOAT]
                    action = option
                    responded = True
            if not checked and responded \
                    and actions[0].kind == "select_card":
                # Its discard is an activation cost, chosen from its own hand.
                action = choose("select_card")
                assert action is not None and obs.acting_player == 1
                discarded = True
            if action is None:
                action = (choose("place") or choose("select_position") or
                          choose("end_phase") or choose("pass") or
                          agents[obs.acting_player].select_action(obs, actions))
            obs = env.step(action)

        assert trap_set and goat_used and responded and checked
        assert env.is_terminal()
        path = tmp_path / "scapegoat_jammer.json"
        write_trajectory(path, env.trajectory())
        replay = read_trajectory(path)
        assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(
            replay.decisions)
        assert audit_trajectory_visibility(replay)["decisions"] == len(replay.decisions)
