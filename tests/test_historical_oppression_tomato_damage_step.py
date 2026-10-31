"""Face-up Royal Oppression cannot stop Mystic Tomato in the Damage Step.

Archived FAQ: https://www.goatformat.com/rulings6.html (Royal Oppression).
"""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

GEMINI_ELF = 69140098
MYSTIC_TOMATO = 504700142
SANGAN = 504700178
OPPRESSION = 93016201


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
def test_faceup_oppression_cannot_answer_tomato_damage_step_recruit(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{code}.lua" for code in (MYSTIC_TOMATO, SANGAN)} | {
        f"official/c{OPPRESSION}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    attacker = tmp_path / "attacker.ydk"
    defender = tmp_path / "defender.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        *([GEMINI_ELF] * 3),
        *tuple(code for code in VANILLA_DECK if code != GEMINI_ELF)[:37])))
        + "\n#extra\n!side\n")
    defender.write_text("#main\n" + "\n".join(map(str, (
        OPPRESSION, *([MYSTIC_TOMATO] * 3), SANGAN,
        *VANILLA_DECK[5:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=72,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert GEMINI_ELF in {card.code for card in obs.hand}
        assert {OPPRESSION, MYSTIC_TOMATO} <= {card.code for card in
                                               env.engine.probe.observation(1).hand}
        gemini_summoned = tomato_set = oppression_set = oppression_up = False
        battle = attacked = attack_targeted = recruited = sangan_selected = False
        saw_tomato_chain = checked = False
        deck_before = None
        agents = (RandomAgent(72), RandomAgent(73))
        for _ in range(3000):
            if env.is_terminal():
                assert checked and saw_tomato_chain
                path = tmp_path / "oppression_tomato.json"
                write_trajectory(path, env.trajectory())
                replay = read_trajectory(path)
                assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(
                    replay.decisions)
                audit_trajectory_visibility(replay)
                assert scripts <= set(env.engine.probe.loaded_script_sha256)
                return
            actions = env.legal_actions()
            action = None

            def choose(kind, code=None):
                return next((candidate for candidate in actions
                             if candidate.kind == kind and (code is None or
                                candidate.parameters.get("code") == code)), None)

            if not checked and obs.turn == 1 and obs.acting_player == 0 \
                    and not gemini_summoned:
                action = choose("normal_summon", GEMINI_ELF)
                gemini_summoned |= action is not None
            if not checked and obs.turn == 2 and obs.acting_player == 1:
                if not tomato_set:
                    action = choose("set_monster", MYSTIC_TOMATO)
                    tomato_set |= action is not None
                if tomato_set and not oppression_set and action is None:
                    action = choose("set_spell_trap", OPPRESSION)
                    oppression_set |= action is not None
            if not checked and obs.turn == 3 and obs.acting_player == 1 \
                    and oppression_set and not oppression_up:
                action = choose("chain", OPPRESSION)
                oppression_up |= action is not None
            if not checked and obs.turn == 3 and obs.acting_player == 0 \
                    and oppression_up:
                if obs.phase == "main1" and not battle:
                    action = choose("battle_phase")
                    battle |= action is not None
                if obs.phase == "battle_start" and not attacked:
                    action = choose("attack", GEMINI_ELF)
                    attacked |= action is not None
            if attacked and not attack_targeted and actions[0].kind == "select_card":
                action = next((candidate for candidate in actions
                               if candidate.parameters.get("controller") == 1
                               and "code" not in candidate.parameters), None)
                attack_targeted |= action is not None
            if attack_targeted and not checked and obs.phase == "damage_step":
                assert any(card.code == OPPRESSION and card.position == "faceup"
                           for card in obs.field)
                assert not any(candidate.kind in ("activate", "chain")
                               and candidate.parameters.get("code") == OPPRESSION
                               for candidate in actions)
                if [(link.index, link.card_code) for link in obs.chain] == [
                        (1, MYSTIC_TOMATO)]:
                    saw_tomato_chain = True
            if attack_targeted and not recruited and choose("yes", MYSTIC_TOMATO):
                assert obs.phase == "damage_step" and obs.acting_player == 1
                deck_before = obs.deck_counts[1]
                action = choose("yes", MYSTIC_TOMATO)
                recruited = True
            if recruited and not sangan_selected and actions[0].kind == "select_card":
                assert obs.phase == "damage_step" and obs.acting_player == 1
                action = choose("select_card", SANGAN)
                sangan_selected |= action is not None
            if action is None:
                action = (agents[obs.acting_player].select_action(obs, actions)
                          if checked else next((candidate for candidate in actions
                                                if candidate.kind in (
                                                    "place", "pass", "end_phase")),
                                               actions[0]))
            obs = env.step(action)
            if sangan_selected and not checked and obs.phase == "battle_step":
                assert saw_tomato_chain
                assert obs.deck_counts[1] == deck_before - 1
                assert any(card.code == SANGAN and card.controller == 1
                           and card.zone == "monster" for card in obs.field)
                assert any(card.code == MYSTIC_TOMATO for card in obs.graveyards[1])
                assert obs.life_points == (8000, 8000)
                checked = True
    pytest.fail("Oppression/Tomato fixture did not reach a verified terminal duel")
