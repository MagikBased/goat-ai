"""Compulsory Evacuation Device returns main and Fusion monsters correctly."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

COMPULSORY = 94192409
BOOK_OF_MOON = 14087893
SCAPEGOAT = 504700123
METAMORPHOSIS = 46411259
RESTRICT = 504700102
SHEEP_CODES = {73915052, 73915053, 73915054, 73915055}


def _deck(path, cards, extra=()):
    path.write_text("#main\n" + "\n".join(map(str, cards))
                    + "\n#extra\n" + "\n".join(map(str, extra)) + "\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_booked_public_monster_returned_by_compulsory_stays_known_in_hand(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (BOOK_OF_MOON, COMPULSORY):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    responder = _deck(tmp_path / "book_compulsory.ydk",
                      (BOOK_OF_MOON, COMPULSORY, *VANILLA_DECK[2:]))
    with GoatEnvironment(responder, "examples/decks/vanilla_probe.ydk", seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {BOOK_OF_MOON, COMPULSORY}.issubset({c.code for c in obs.hand})
        set_cards = set()
        summoned = book_used = book_targeted = compulsory_used = False
        compulsory_targeted = False
        summoned_code = None
        for _ in range(100):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and len(set_cards) < 2:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") in (
                                   {BOOK_OF_MOON, COMPULSORY} - set_cards)), None)
                if action is not None:
                    set_cards.add(action.parameters["code"])
            if obs.turn == 2 and obs.acting_player == 1 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), action)
                if action is not None and action.kind == "normal_summon":
                    summoned = True
                    summoned_code = action.parameters["code"]
            if obs.turn == 3 and obs.acting_player == 0 and not book_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == BOOK_OF_MOON), action)
                book_used |= action is not None and action.parameters.get("code") == BOOK_OF_MOON
            if book_used and not book_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("code") == summoned_code), None)
                book_targeted |= action is not None
            if book_targeted and BOOK_OF_MOON in {c.code for c in obs.graveyards[0]} \
                    and obs.acting_player == 0 and not compulsory_used:
                hidden = next(c for c in obs.field if c.controller == 1
                              and c.zone == "monster")
                assert hidden.code is None and hidden.position == "facedown"
                assert (1, "monster", hidden.sequence, summoned_code) in {
                    (c.controller, c.zone, c.sequence, c.code)
                    for c in obs.known_opponent_field_cards}
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == COMPULSORY), action)
                compulsory_used |= action is not None and action.parameters.get(
                    "code") == COMPULSORY
            if compulsory_used and not compulsory_targeted \
                    and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 4), None)
                if action is not None:
                    assert "code" not in action.parameters
                    compulsory_targeted = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if compulsory_targeted and COMPULSORY in {
                    c.code for c in obs.graveyards[0]}:
                owner = env.engine.probe.observation(1)
                chooser = env.engine.probe.observation(0)
                assert summoned_code in {c.code for c in owner.hand}
                assert not any(c.controller == 1 and c.zone == "monster"
                               for c in chooser.field)
                assert chooser.known_opponent_hand_cards == (summoned_code,)
                assert not chooser.known_opponent_field_cards
                agents = (RandomAgent(18), RandomAgent(19))
                for _ in range(3000):
                    if env.is_terminal():
                        break
                    obs = env.step(agents[obs.acting_player].select_action(
                        obs, env.legal_actions()))
                else:
                    pytest.fail("Book/Compulsory duel did not terminate")
                trajectory = env.trajectory()
                assert any(record.observation.known_opponent_hand_cards
                           == (summoned_code,) for record in trajectory.decisions)
                path = tmp_path / "book_compulsory.json"
                write_trajectory(path, trajectory)
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) \
                    == len(trajectory.decisions)
                return
    pytest.fail("Book and Compulsory did not return the known monster")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("fusion", [False, True])
def test_compulsory_return_destination_and_hidden_hand(tmp_path, fusion):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    required = [f"scripts/official/c{COMPULSORY}.lua"]
    if fusion:
        required += [f"scripts/goat/c{SCAPEGOAT}.lua",
                     f"scripts/official/c{METAMORPHOSIS}.lua",
                     f"scripts/goat/c{RESTRICT}.lua"]
    if not all((root / script).is_file() for script in required):
        pytest.skip("required card scripts not installed")
    own = _deck(tmp_path / "compulsory.ydk",
                (*([COMPULSORY] * 3), *VANILLA_DECK[3:]))
    other = _deck(tmp_path / "opponent.ydk",
                  (*([SCAPEGOAT] * 3), *([METAMORPHOSIS] * 3),
                   *VANILLA_DECK[6:]) if fusion else VANILLA_DECK,
                  (RESTRICT,) if fusion else ())
    with GoatEnvironment(own, other, seed=11 if fusion else 15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        trap_set = goat = metamorphosis = paid_token = selected_fusion = False
        summoned = activated = target_selected = False
        target_code = None
        hand_before = None
        for _ in range(90):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not trap_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == COMPULSORY), None)
                trap_set |= action is not None
            if fusion and obs.turn == 2 and obs.acting_player == 1 and not goat:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                goat |= action is not None
            if fusion and obs.turn == 4 and obs.acting_player == 1 and not metamorphosis:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == METAMORPHOSIS), None)
                metamorphosis |= action is not None
            if fusion and metamorphosis and not paid_token and action is None:
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") in SHEEP_CODES), None)
                paid_token |= action is not None
            if fusion and paid_token and not selected_fusion and action is None:
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == RESTRICT), None)
                selected_fusion |= action is not None
            if not fusion and obs.turn == 2 and obs.acting_player == 1 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    target_code = action.parameters["code"]
                    summoned = True
            target_on_field = any(c.controller == 1 and c.zone == "monster"
                                  and c.code == (RESTRICT if fusion else target_code)
                                  for c in obs.field)
            if trap_set and target_on_field and obs.acting_player == 0 and not activated:
                action = next((a for a in actions if a.kind in ("activate", "chain")
                               and a.parameters.get("code") == COMPULSORY), action)
                activated |= action is not None and action.parameters.get("code") == COMPULSORY
                if activated:
                    hand_before = len(env.engine.probe.observation(1).hand)
            if activated and not target_selected and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("controller") == 1
                               and a.parameters.get("code")
                               == (RESTRICT if fusion else target_code)), None)
                target_selected = action is not None
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "select_position", "pass", "end_phase")),
                    actions[0])
            obs = env.step(action)
            if target_selected and COMPULSORY in {c.code for c in obs.graveyards[0]}:
                assert not any(c.controller == 1 and c.zone == "monster"
                               and c.code == (RESTRICT if fusion else target_code)
                               for c in obs.field)
                owner_view = env.engine.probe.observation(1)
                chooser_view = env.engine.probe.observation(0)
                assert len(owner_view.hand) == hand_before + (0 if fusion else 1)
                assert chooser_view.opponent_hand_count == len(owner_view.hand)
                assert chooser_view.known_opponent_hand_cards == (
                    () if fusion else (target_code,))
                assert obs.extra_deck_counts[1] == (1 if fusion else 0)
                assert not any(c.code == (RESTRICT if fusion else target_code)
                               for c in obs.graveyards[1])
                assert all(c.controller == 0 for c in chooser_view.hand)
                assert f"official/c{COMPULSORY}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Compulsory did not return the selected monster")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("bounce_attacker", [False, True])
def test_compulsory_battle_step_bounce_and_replay(tmp_path, bounce_attacker):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{COMPULSORY}.lua").is_file():
        pytest.skip("Compulsory script not installed")
    attacker = _deck(tmp_path / "attacker.ydk", VANILLA_DECK)
    defender = _deck(tmp_path / "defender.ydk",
                     (*([COMPULSORY] * 3), *VANILLA_DECK[3:]))
    with GoatEnvironment(attacker, defender, seed=11,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        first_summoned = second_summoned = trap_set = battle = attacked = False
        activated = targeted = resolved = False
        attacker_code = defender_code = None
        for _ in range(90):
            actions = env.legal_actions()
            action = None
            if obs.acting_player == 0 and obs.turn == 1 and not first_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    attacker_code = action.parameters["code"]
                    first_summoned = True
            if obs.acting_player == 1 and obs.turn == 2:
                if not trap_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == COMPULSORY), None)
                    trap_set |= action is not None
                if trap_set and not second_summoned and action is None:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        defender_code = action.parameters["code"]
                        second_summoned = True
            if obs.acting_player == 0 and obs.turn == 3:
                if obs.phase == "main1" and not battle:
                    action = next((a for a in actions if a.kind == "battle_phase"), None)
                    battle |= action is not None
                if battle and not attacked and obs.phase == "battle_start":
                    action = next((a for a in actions if a.kind == "attack"
                                   and a.parameters.get("code") == attacker_code), None)
                    attacked |= action is not None
            if attacked and obs.acting_player == 1 and not activated:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == COMPULSORY), None)
                if action is not None:
                    assert obs.phase == "battle_step"
                    activated = True
            if activated and not targeted and actions[0].kind == "select_card":
                target = attacker_code if bounce_attacker else defender_code
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == target
                               and a.parameters.get("controller")
                               == (0 if bounce_attacker else 1)), None)
                targeted = action is not None
            if resolved and not bounce_attacker:
                assert obs.phase == "battle_step"
                if any(a.kind == "attack" and a.parameters.get("code")
                       == attacker_code for a in actions):
                    assert obs.acting_player == 0
                    return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "select_position", "pass", "end_phase")),
                    actions[0])
            obs = env.step(action)
            if targeted and not resolved and COMPULSORY in {
                    c.code for c in obs.graveyards[1]}:
                resolved = True
                bounced_player = 0 if bounce_attacker else 1
                bounced_code = attacker_code if bounce_attacker else defender_code
                bounced = env.engine.probe.observation(bounced_player)
                assert bounced_code in {c.code for c in bounced.hand}
                assert not any(c.controller == bounced_player and c.zone == "monster"
                               for c in obs.field)
                assert obs.life_points == (8000, 8000)
                if bounce_attacker:
                    assert not any(a.kind == "attack" for a in env.legal_actions())
                    return
    pytest.fail("Compulsory Battle Step bounce did not resolve")
