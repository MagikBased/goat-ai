"""Solemn Judgment negates a Serpent Summon without stopping its later return."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import verify_trajectory

SINISTER_SERPENT = 511000818
SOLEMN_JUDGMENT = 41420027


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
@pytest.mark.parametrize("negate", (False, True))
def test_solemn_on_serpent_summon_and_next_standby(tmp_path, negate):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"scripts/pre-errata/c{SINISTER_SERPENT}.lua",
                     f"scripts/official/c{SOLEMN_JUDGMENT}.lua"):
        if not (root / relative).is_file():
            pytest.skip(f"required script not installed: {relative}")
    serpent_deck = tmp_path / "serpent.ydk"
    solemn_deck = tmp_path / "solemn.ydk"
    serpent_deck.write_text("#main\n" + "\n".join(map(str, (
        SINISTER_SERPENT, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    solemn_deck.write_text("#main\n" + "\n".join(map(str, (
        SOLEMN_JUDGMENT, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(serpent_deck), str(solemn_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert SINISTER_SERPENT in {card.code for card in obs.hand}
        assert SOLEMN_JUDGMENT in {
            card.code for card in env.engine.probe.observation(1).hand}
        set_solemn = summoned = responded = resolved = returned = return_resolved = False
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(3000):
            if env.is_terminal():
                assert set_solemn and summoned and responded and resolved
                assert returned is negate
                assert return_resolved is negate
                replay = env.trajectory()
                assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(
                    replay.decisions)
                audit_trajectory_visibility(replay)
                assert {f"pre-errata/c{SINISTER_SERPENT}.lua",
                        f"official/c{SOLEMN_JUDGMENT}.lua"}.issubset(
                            env.engine.probe.loaded_script_sha256)
                return
            legal = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1 and not set_solemn:
                action = next((candidate for candidate in legal
                               if candidate.kind == "set_spell_trap"
                               and candidate.parameters.get("code") == SOLEMN_JUDGMENT), None)
                set_solemn |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not summoned:
                action = next((candidate for candidate in legal
                               if candidate.kind == "normal_summon"
                               and candidate.parameters.get("code") == SINISTER_SERPENT), None)
                summoned |= action is not None
            if summoned and obs.acting_player == 1 and not responded:
                solemn = next((candidate for candidate in legal
                               if candidate.kind == "chain"
                               and candidate.parameters.get("code") == SOLEMN_JUDGMENT), None)
                if solemn is not None:
                    action = solemn if negate else next(
                        candidate for candidate in legal if candidate.kind == "pass")
                    responded = True
            if responded and not resolved and obs.chain == () and obs.turn == 3:
                own = env.engine.probe.observation(0)
                if negate and SINISTER_SERPENT in {card.code for card in own.graveyards[0]}:
                    assert own.life_points == (8000, 4000)
                    assert not any(card.code == SINISTER_SERPENT
                                   for card in own.field)
                    resolved = True
                elif not negate and any(card.code == SINISTER_SERPENT
                                        for card in own.field):
                    assert own.life_points == (8000, 8000)
                    assert any(card.controller == 1 and card.zone == "spell_trap"
                               and card.position == "facedown" and card.code is None
                               for card in own.field)
                    assert any(card.code == SOLEMN_JUDGMENT
                               and card.position == "facedown" for card in
                               env.engine.probe.observation(1).field)
                    resolved = True
            if negate and resolved and not returned and obs.turn == 5 \
                    and obs.phase == "standby" and obs.acting_player == 0:
                action = next((candidate for candidate in legal
                               if candidate.kind == "yes"
                               and candidate.parameters.get("code") == SINISTER_SERPENT), None)
                assert action is not None
                returned = True
            if action is None:
                action = (agents[obs.acting_player].select_action(obs, legal)
                          if resolved and (not negate or return_resolved) else
                          next((candidate for candidate in legal
                                if candidate.kind in ("place", "pass", "end_phase")),
                               legal[0]))
            obs = env.step(action)
            if negate and returned and not return_resolved and obs.chain == () \
                    and SINISTER_SERPENT in {
                        card.code for card in env.engine.probe.observation(0).hand}:
                own = env.engine.probe.observation(0)
                assert SINISTER_SERPENT not in {card.code for card in own.graveyards[0]}
                assert SINISTER_SERPENT in \
                    env.engine.probe.observation(1).known_opponent_hand_cards
                return_resolved = True
    pytest.fail("Solemn/Sinister Serpent duel exceeded the decision cap")
