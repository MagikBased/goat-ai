"""A player can order simultaneous mandatory Flip Effects in GOAT and MR1."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.mr1_synchro_probe import Mr1SynchroProbeEngine
from goat_ai.engine.ocgcore_probe import MR1_FLAGS
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

DEKOICHI = 87621407
SPY = 504700044  # GOAT variant
MR1_SPY = 24317029
DESERT_SUNLIGHT = 93747864


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("first_trigger", [DEKOICHI, SPY])
@pytest.mark.parametrize("engine_type", [ExperimentalOcgcoreEngine,
                                          Mr1SynchroProbeEngine])
def test_owner_selects_simultaneous_mandatory_trigger_order(tmp_path, first_trigger,
                                                             engine_type):
    """Desert Sunlight flips both monsters in one effect resolution."""
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    spy = SPY if engine_type is ExperimentalOcgcoreEngine else MR1_SPY
    first = spy if first_trigger == SPY else DEKOICHI
    required = (f"official/c{DEKOICHI}.lua",
                f"{'goat' if spy == SPY else 'official'}/c{spy}.lua",
                f"official/c{DESERT_SUNLIGHT}.lua")
    if any(not (root / "scripts" / name).is_file() for name in required):
        pytest.skip("full card script checkout not installed")
    deck = tmp_path / "two_flips.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        *([DEKOICHI] * 3), *([spy] * 3), *([DESERT_SUNLIGHT] * 3),
        *VANILLA_DECK[9:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=70,
                         engine=engine_type(root)) as env:
        obs = env.reset()
        if engine_type is Mr1SynchroProbeEngine:
            assert env.engine.probe.flags == MR1_FLAGS
        assert {DEKOICHI, spy, DESERT_SUNLIGHT} <= {card.code for card in obs.hand}
        deko_set = spy_set = desert_set = desert_activated = choice_seen = False
        two_link_seen = False
        before_deck = None
        for _ in range(100):
            actions = env.legal_actions()

            def choose(kind, code=None, choices=actions):
                return next((a for a in choices if a.kind == kind and (
                    code is None or a.parameters.get("code") == code)), None)

            if two_link_seen and not obs.chain and obs.deck_counts[0] == before_deck - 2:
                assert choice_seen
                assert sum(card.code == spy and card.controller == 0
                           for card in obs.field) == 2
                break
            if len(obs.chain) == 2 and {link.card_code for link in obs.chain} == {
                    DEKOICHI, spy}:
                assert tuple(link.card_code for link in obs.chain) == (
                    first, spy if first == DEKOICHI else DEKOICHI)
                two_link_seen = True

            action = None
            if obs.acting_player == 0 and obs.turn == 1:
                if not deko_set:
                    action = choose("set_monster", DEKOICHI)
                    deko_set = action is not None
                if action is None and not desert_set:
                    action = choose("set_spell_trap", DESERT_SUNLIGHT)
                    desert_set = action is not None
            if obs.acting_player == 0 and obs.turn == 3:
                if not spy_set:
                    action = choose("set_monster", spy)
                    spy_set = action is not None
                if action is None and spy_set and not desert_activated:
                    action = choose("chain", DESERT_SUNLIGHT)
                    desert_activated = action is not None
                    if desert_activated:
                        before_deck = obs.deck_counts[0]
            if desert_activated and not choice_seen and {
                    DEKOICHI, spy} <= {
                    a.parameters.get("code") for a in actions if a.kind == "chain"}:
                choice_seen = True
                action = choose("chain", first)
                assert action is not None
            if action is None:
                action = (choose("place") or choose("select_position")
                          or choose("pass") or choose("end_phase") or actions[0])
            obs = env.step(action)
        else:
            pytest.fail("same-time Flip Effect chain did not finish")

        agents = (RandomAgent(70), RandomAgent(71))
        for _ in range(3000):
            if env.is_terminal():
                break
            obs = env.step(agents[obs.acting_player].select_action(
                obs, env.legal_actions()))
        assert env.is_terminal()
        path = tmp_path / f"trigger_choice_{first}.json"
        write_trajectory(path, env.trajectory())
        trajectory = read_trajectory(path)
        audit_trajectory_visibility(trajectory)
        assert verify_trajectory(trajectory, engine_type(root)) == len(
            trajectory.decisions)
