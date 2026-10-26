"""GOAT Scapegoat token and same-turn Summon restriction regressions."""

import os
from dataclasses import replace
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SCAPEGOAT = 504700123
SOLEMN_JUDGMENT = 41420027
CANNON_SOLDIER = 11384280
DMOC = 511001039
TOKEN_CODES = {73915052, 73915053, 73915054, 73915055}
SCAPEGOAT_RESTRICTION = "player0:cannot_summon_this_turn:scapegoat"
OPPONENT = Path(__file__).resolve().parent.parent / "examples/decks/vanilla_probe.ydk"


@pytest.fixture
def scapegoat_deck(tmp_path):
    deck = tmp_path / "scapegoat.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (SCAPEGOAT, *VANILLA_DECK[1:]))) + "\n")
    return deck


def _native_root():
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/goat/c{SCAPEGOAT}.lua").is_file():
        pytest.skip("GOAT Scapegoat script not installed")
    return root


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_scapegoat_summons_four_tokens_but_still_allows_a_set(scapegoat_deck):
    root = _native_root()
    with GoatEnvironment(str(scapegoat_deck), str(OPPONENT), seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        activated = False
        for _ in range(40):
            choices = env.legal_actions()
            tokens = [card for card in observation.field if card.controller == 0
                      and card.code in TOKEN_CODES]
            if len(tokens) == 4 and observation.acting_player == 0 and any(
                action.kind == "set_monster" for action in choices
            ):
                assert activated
                assert observation.restrictions == (SCAPEGOAT_RESTRICTION,)
                assert {card.code for card in tokens} == TOKEN_CODES
                assert all(card.position == "faceup" and card.orientation == "defense"
                           for card in tokens)
                assert not any(action.kind in ("normal_summon", "special_summon")
                               for action in choices)
                assert "goat/c504700123.lua" in env.engine.probe.loaded_script_sha256
                return
            action = None
            if activated and observation.acting_player == 1 and observation.turn == 1:
                assert observation.restrictions == (SCAPEGOAT_RESTRICTION,)
            if observation.acting_player == 0 and observation.phase == "main1" and not activated:
                action = next((item for item in choices if item.kind == "activate"
                               and item.parameters.get("code") == SCAPEGOAT), None)
                activated = action is not None
            if action is None:
                action = next((item for item in choices if item.kind == "pass"), None)
            if action is None:
                action = next((item for item in choices if item.kind == "place"), None)
            if action is None:
                action = next((item for item in choices if item.kind == "end_phase"), choices[0])
            observation = env.step(action)
        pytest.fail("Scapegoat did not produce four tokens and a post-resolution decision")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_scapegoat_cannot_activate_after_normal_summon(scapegoat_deck):
    root = _native_root()
    with GoatEnvironment(str(scapegoat_deck), str(OPPONENT), seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        normal_summoned = False
        checked_after_summon = False
        for _ in range(30):
            choices = env.legal_actions()
            if observation.turn > 1:
                assert normal_summoned and checked_after_summon
                assert observation.restrictions == ()
                return
            if normal_summoned:
                assert not any(item.kind in ("chain", "activate")
                               and item.parameters.get("code") == SCAPEGOAT
                               for item in choices)
                checked_after_summon = True
            action = None
            if observation.acting_player == 0 and observation.phase == "main1" and not normal_summoned:
                assert any(item.kind == "activate"
                           and item.parameters.get("code") == SCAPEGOAT for item in choices)
                action = next((item for item in choices if item.kind == "normal_summon"), None)
                normal_summoned = action is not None
            if action is None:
                action = next((item for item in choices if item.kind == "pass"), None)
            if action is None:
                action = next((item for item in choices if item.kind == "place"), None)
            if action is None:
                action = next((item for item in choices if item.kind == "end_phase"), choices[0])
            observation = env.step(action)
        pytest.fail("did not reach the turn after the Normal Summon")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_sheep_token_is_cannon_cost_but_not_tribute_summon_material(tmp_path):
    root = _native_root()
    deck = tmp_path / "scapegoat_cannon.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        CANNON_SOLDIER, SCAPEGOAT, DMOC, *VANILLA_DECK[3:]))) + "\n")
    with GoatEnvironment(str(deck), str(OPPONENT), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        goat_activated = cannon_summoned = ignition_activated = token_tributed = False
        checked_tribute_restriction = False
        token_code = None
        for _ in range(60):
            choices = env.legal_actions()
            if token_tributed:
                assert not any(card.code == token_code for zone in
                               (*observation.graveyards, *observation.banished)
                               for card in zone)
                assert not any(card.code == token_code for card in observation.field)
                if observation.life_points[1] == 7500:
                    assert checked_tribute_restriction
                    assert goat_activated and cannon_summoned and ignition_activated
                    return
            action = None
            if observation.turn == 3:
                assert observation.restrictions == ()
            if observation.acting_player == 0:
                if observation.turn == 1 and observation.phase == "main1" and not goat_activated:
                    action = next((item for item in choices if item.kind == "activate"
                                   and item.parameters.get("code") == SCAPEGOAT), None)
                    goat_activated |= action is not None
                if (action is None and observation.turn == 3
                        and observation.phase == "main1" and not cannon_summoned):
                    assert not any(item.kind == "normal_summon"
                                   and item.parameters.get("code") == DMOC for item in choices)
                    checked_tribute_restriction = True
                    action = next((item for item in choices if item.kind == "normal_summon"
                                   and item.parameters.get("code") == CANNON_SOLDIER), None)
                    cannon_summoned |= action is not None
                if action is None and cannon_summoned and not ignition_activated:
                    action = next((item for item in choices if item.kind == "chain"
                                   and item.parameters.get("code") == CANNON_SOLDIER), None)
                    ignition_activated |= action is not None
                if action is None and ignition_activated and not token_tributed:
                    action = next((item for item in choices if item.kind == "select_card"
                                   and item.parameters.get("code") in TOKEN_CODES), None)
                    if action is not None:
                        token_code = action.parameters["code"]
                        token_tributed = True
            if action is None:
                action = next((item for item in choices if item.kind == "place"), None)
            if action is None:
                action = next((item for item in choices if item.kind == "end_phase"), None)
            if action is None:
                action = next((item for item in choices if item.kind == "pass"), choices[0])
            observation = env.step(action)
        pytest.fail("Scapegoat/Cannon Soldier interaction did not resolve")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_public_scapegoat_restriction_replays_in_new_and_old_schemas(
    scapegoat_deck, tmp_path,
):
    root = _native_root()
    with GoatEnvironment(str(scapegoat_deck), str(OPPONENT), seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        agent = RandomAgent(3)
        for _ in range(5000):
            observation = env.step(agent.select_action(observation, env.legal_actions()))
            if env.is_terminal():
                trajectory = env.trajectory()
                break
        else:
            pytest.fail("Scapegoat duel did not finish within 5000 decisions")
    assert any(SCAPEGOAT_RESTRICTION in record.observation.restrictions
               for record in trajectory.decisions)
    path = tmp_path / "scapegoat.json"
    write_trajectory(path, trajectory)
    assert verify_trajectory(read_trajectory(path), ExperimentalOcgcoreEngine(root)) == len(
        trajectory.decisions)
    def legacy_six_view(view):
        def old_cards(cards):
            return tuple(replace(card, attack=None, defense=None, counters=(),
                                 equipped_to=None, race=None) for card in cards)

        return replace(
            view, restrictions=(), public_reveals=(), disabled_zones=(),
            private_reveals=(), own_main_deck=(), known_opponent_hand_cards=(),
            pending_attack=None, turn_player=None,
            chain=tuple(replace(link, targets=()) for link in view.chain),
            hand=old_cards(view.hand), field=old_cards(view.field),
            own_extra_deck=old_cards(view.own_extra_deck),
            graveyards=tuple(old_cards(zone) for zone in view.graveyards),
            banished=tuple(old_cards(zone) for zone in view.banished),
        )

    previous = replace(trajectory, schema_version=6, terminal_observation=None,
                       decisions=tuple(replace(
                           record,
                           observation=legacy_six_view(record.observation),
                           legal_actions=tuple(replace(action, kind="change_position")
                                               if action.kind == "flip_summon" else action
                                               for action in record.legal_actions),
                           selected_action=(replace(record.selected_action, kind="change_position")
                                            if record.selected_action.kind == "flip_summon"
                                            else record.selected_action),
                       )
                                       for record in trajectory.decisions))
    write_trajectory(path, previous)
    assert verify_trajectory(read_trajectory(path), ExperimentalOcgcoreEngine(root)) == len(
        previous.decisions)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("negate", [False, True])
def test_negated_scapegoat_activation_restores_summon_permission(
    scapegoat_deck, tmp_path, negate,
):
    root = _native_root()
    if not (root / f"scripts/official/c{SOLEMN_JUDGMENT}.lua").is_file():
        pytest.skip("Solemn Judgment script not installed")
    opponent = tmp_path / "solemn.ydk"
    opponent.write_text("#main\n" + "\n".join(map(str, (
        SOLEMN_JUDGMENT, *VANILLA_DECK[1:]))) + "\n")
    with GoatEnvironment(str(scapegoat_deck), str(opponent), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        trap_set = scapegoat_activated = response_made = saw_restriction = False
        checked = False
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"solemn_scapegoat_{negate}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    env.trajectory().decisions)
                return
            choices = env.legal_actions()
            if scapegoat_activated and SCAPEGOAT_RESTRICTION in observation.restrictions:
                saw_restriction = True
            if (response_made and not checked and observation.turn == 3
                    and observation.acting_player == 0
                    and observation.phase == "main1" and not observation.chain
                    and any(item.kind == "battle_phase" for item in choices)
                    and SCAPEGOAT in {card.code for card in observation.graveyards[0]}):
                assert trap_set and scapegoat_activated and saw_restriction
                assert observation.life_points == ((8000, 4000) if negate
                                                   else (8000, 8000))
                assert (SOLEMN_JUDGMENT in {card.code for card in
                                            observation.graveyards[1]}) == negate
                assert (SCAPEGOAT_RESTRICTION in observation.restrictions) != negate
                assert any(item.kind == "normal_summon" for item in choices) == negate
                assert sum(card.code in TOKEN_CODES for card in observation.field) \
                    == (0 if negate else 4)
                checked = True
            action = None
            if not checked and observation.acting_player == 1 \
                    and observation.turn == 2 and not trap_set:
                action = next((item for item in choices if item.kind == "set_spell_trap"
                               and item.parameters.get("code") == SOLEMN_JUDGMENT), None)
                trap_set |= action is not None
            if (not checked and action is None and observation.acting_player == 0
                    and observation.turn == 3 and observation.phase == "main1"
                    and not scapegoat_activated):
                action = next((item for item in choices if item.kind == "activate"
                               and item.parameters.get("code") == SCAPEGOAT), None)
                scapegoat_activated |= action is not None
            if (not checked and action is None and observation.acting_player == 1
                    and scapegoat_activated and not response_made):
                option = next((item for item in choices if item.kind == "chain"
                               and item.parameters.get("code") == SOLEMN_JUDGMENT), None)
                if option is not None:
                    assert [link.card_code for link in observation.chain] == [SCAPEGOAT]
                    action = option if negate else next(
                        item for item in choices if item.kind == "pass")
                    response_made = True
            if action is None and not checked:
                action = next((item for item in choices if item.kind == "place"), None)
            if action is None and not checked:
                action = next((item for item in choices if item.kind == "end_phase"), None)
            if action is None and not checked:
                action = next((item for item in choices if item.kind == "pass"), choices[0])
            if action is None:
                action = agents[observation.acting_player].select_action(
                    observation, choices)
            observation = env.step(action)
        pytest.fail("Solemn / Scapegoat duel did not complete")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_scapegoat_needs_four_vacant_monster_zones(scapegoat_deck):
    root = _native_root()
    with GoatEnvironment(str(scapegoat_deck), str(OPPONENT), seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        normal_summons = 0
        for _ in range(60):
            choices = env.legal_actions()
            if (observation.turn == 5 and observation.acting_player == 0
                    and observation.phase == "main1"
                    and any(item.kind == "normal_summon" for item in choices)):
                assert normal_summons == 2
                assert sum(card.controller == 0 and card.zone == "monster"
                           for card in observation.field) == 2
                assert observation.restrictions == ()
                assert any(item.kind == "set_spell_trap"
                           and item.parameters.get("code") == SCAPEGOAT for item in choices)
                assert not any(item.kind in ("activate", "chain")
                               and item.parameters.get("code") == SCAPEGOAT
                               for item in choices)
                return
            action = None
            if (observation.acting_player == 0 and observation.turn in (1, 3)
                    and normal_summons < (observation.turn + 1) // 2):
                action = next((item for item in choices if item.kind == "normal_summon"), None)
                normal_summons += action is not None
            if action is None:
                action = next((item for item in choices if item.kind == "place"), None)
            if action is None:
                action = next((item for item in choices if item.kind == "end_phase"), None)
            if action is None:
                action = next((item for item in choices if item.kind == "pass"), choices[0])
            observation = env.step(action)
        pytest.fail("did not reach the later Main Phase with two monsters")
