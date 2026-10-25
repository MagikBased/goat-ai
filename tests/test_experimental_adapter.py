"""Protocol regressions for the unaudited full-script deck probe."""

import os
import struct
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.decks import read_ydk
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.native_messages import (
    MAX_CARD_SELECTION_COMBINATIONS,
    decode_decision,
)
from goat_ai.engine.ocgcore_probe import (
    LOCATION_EXTRA,
    LOCATION_HAND,
    LOCATION_MZONE,
    LOCATION_SZONE,
)
from goat_ai.engine.protocol import SimulatorUnavailable
from goat_ai.engine.restricted_adapter import RestrictedOcgcoreEngine
from goat_ai.environments.goat import GoatEnvironment

DECK = "examples/decks/control_probe.ydk"
CHAOS_DECK = "examples/decks/chaos_probe.ydk"


def test_card_selection_stages_combinations_above_the_flat_action_bound():
    def prompt(count: int, selected: int) -> bytes:
        return (b"\x0f\x00\x00" + struct.pack("<III", selected, selected, count)
                + b"".join(struct.pack("<IBBII", 100 + index, 0, LOCATION_HAND,
                                       index, 0) for index in range(count)))

    decision = decode_decision(prompt(15, 5))
    assert len(decision.choices) == 3003
    assert decision.choices[0].kind == "select_cards"
    assert len(decision.choices[0].cards) == 5
    assert len(decision.choices[-1].cards) == 5
    assert MAX_CARD_SELECTION_COMBINATIONS >= 3003
    staged = decode_decision(prompt(16, 6))
    assert len(staged.choices) == 16
    assert staged.card_selection is not None
    assert (staged.card_selection.minimum, staged.card_selection.maximum) == (6, 6)
    assert staged.choices[0].kind == "select_card"
    selection = staged.card_selection
    assert selection.accepts(struct.pack("<8I", 0, 6, 0, 1, 2, 3, 4, 5))
    assert not selection.accepts(struct.pack("<8I", 0, 6, 0, 1, 2, 3, 4, 16))
    assert not selection.accepts(struct.pack("<8I", 0, 6, 0, 1, 1, 3, 4, 5))
    assert not selection.accepts(struct.pack("<8I", 0, 6, 1, 0, 2, 3, 4, 5))
    assert not selection.accepts(-1)


def test_new_native_choice_formats():
    effect_yes_no = decode_decision(
        b"\x0c\x01" + struct.pack("<IBBIIQ", 87621407, 1, 4, 0, 1, 95))
    assert [(choice.kind, choice.code, choice.controller, choice.location,
             choice.sequence, choice.prompt_id) for choice in effect_yes_no.choices] == [
        ("no", 87621407, 1, 4, 0, 95), ("yes", 87621407, 1, 4, 0, 95)]
    yes_no = decode_decision(b"\x0d\x00" + struct.pack("<Q", 123))
    assert [choice.kind for choice in yes_no.choices] == ["no", "yes"]
    assert [choice.prompt_id for choice in yes_no.choices] == [123, 123]
    options = decode_decision(b"\x0e\x01\x02" + struct.pack("<QQ", 17, 23))
    assert [(choice.response, choice.prompt_id) for choice in options.choices] == [
        (0, 17), (1, 23)]
    positions = decode_decision(b"\x13\x00" + struct.pack("<I", 123) + b"\x05")
    assert [choice.position for choice in positions.choices] == [1, 4]
    races = decode_decision(b"\x8c\x00\x01" + struct.pack("<Q", 0b101))
    assert [choice.race for choice in races.choices] == [1, 4]
    attributes = decode_decision(b"\x8d\x00\x01" + struct.pack("<I", 0x6f))
    assert [choice.attribute for choice in attributes.choices] == [1, 2, 4, 8, 32, 64]
    assert [choice.response for choice in attributes.choices] == [
        struct.pack("<I", bit) for bit in (1, 2, 4, 8, 32, 64)]
    numbers = decode_decision(b"\x8f\x00\x02" + struct.pack("<QQ", 1000, 2000))
    assert [(choice.kind, choice.number, choice.response) for choice in numbers.choices] == [
        ("announce_number", 1000, 0), ("announce_number", 2000, 1)]
    with pytest.raises(ValueError, match="truncated"):
        decode_decision(b"\x8f\x00\x02" + struct.pack("<Q", 1000))
    with pytest.raises(ValueError, match="invalid attribute"):
        decode_decision(b"\x8d\x00\x01" + struct.pack("<I", 0x80))
    card_prompt = b"\x8e\x00\x02" + struct.pack("<QQ", 1, 0x4000010200000000)
    announced = decode_decision(card_prompt, (100, 200))
    assert [(choice.kind, choice.announced_card, choice.response)
            for choice in announced.choices] == [
                ("announce_card", 100, 100), ("announce_card", 200, 200)]
    with pytest.raises(NotImplementedError, match="catalog"):
        decode_decision(card_prompt)
    with pytest.raises(NotImplementedError, match="expression"):
        decode_decision(b"\x8e\x00\x01" + struct.pack("<Q", 1), (100,))
    sort = b"\x19\x01" + struct.pack("<I", 3) + b"".join(
        struct.pack("<IBII", code, 1, 1, sequence)
        for code, sequence in ((100, 2), (200, 1), (300, 0)))
    sorted_cards = decode_decision(sort)
    assert len(sorted_cards.choices) == 6
    assert sorted_cards.choices[0].response == b"\x00\x01\x02"
    assert sorted_cards.choices[-1].response == b"\x02\x01\x00"
    assert [card[0] for card in sorted_cards.choices[-1].cards] == [300, 200, 100]
    with pytest.raises(NotImplementedError, match="sorting bounds"):
        decode_decision(b"\x19\x00" + struct.pack("<I", 7))
    tribute = (b"\x14\x00\x01" + struct.pack("<III", 1, 2, 2)
               + struct.pack("<IBBIB", 111, 0, 4, 0, 1)
               + struct.pack("<IBBIB", 222, 0, 4, 1, 1))
    assert [choice.kind for choice in decode_decision(tribute).choices] == [
        "tribute", "tribute", "tribute_cards", "cancel"]


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("code,kind,parameter,chosen", [
    (17078030, "announce_number", "number", 2000),
    (40410110, "announce_attribute", "attribute", 32),
])
def test_native_announcement_resolves_in_real_duel(tmp_path, code, kind, parameter, chosen):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{code}.lua").is_file():
        pytest.skip("card script not installed")
    deck_lines = Path("examples/decks/vanilla_probe.ydk").read_text().splitlines()
    deck_lines[2] = str(code)
    deck = tmp_path / "announcement.ydk"
    deck.write_text("\n".join(deck_lines) + "\n")
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        for _ in range(20):
            actions = env.legal_actions()
            if actions[0].kind == kind:
                selected = next(action for action in actions
                                if action.parameters[parameter] == chosen)
                observation = env.step(selected)
                assert observation.life_points == ((6000, 8000) if kind == "announce_number"
                                                   else (8000, 8000))
                assert env.legal_actions()
                return
            selected = next((action for action in actions
                             if action.kind in ("activate", "chain")
                             and action.parameters.get("code") == code), None)
            if selected is None:
                selected = next((action for action in actions
                                 if action.kind in ("set_spell_trap", "normal_summon")
                                 and action.parameters.get("code") == code), None)
            if selected is None:
                selected = next((action for action in actions if action.kind == "place"), None)
            if selected is None:
                selected = next((action for action in actions
                                 if action.kind in ("pass", "end_phase")), actions[0])
            observation = env.step(selected)
    pytest.fail(f"{kind} prompt was not reached")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("seed,correct_name,bottom_card", [
    (6, 22609617, 22609617),
    (11, 76812113, 54415063),
])
def test_question_card_name_prompt_hides_graveyard_and_resolves(
        seed, correct_name, bottom_card):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / "scripts/official/c38723936.lua").is_file():
        pytest.skip("Question script not installed")
    deck = "examples/decks/question_probe.ydk"
    with GoatEnvironment(deck, deck, seed=seed,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        agent = RandomAgent(seed=seed)
        for _ in range(300):
            actions = env.legal_actions()
            if any(link.card_code == 38723936 and link.controller != observation.viewer
                   for link in observation.chain):
                assert all(card.code is None for card in observation.graveyards[1])
            if actions[0].kind == "announce_card":
                assert observation.acting_player == 0
                assert len(actions) > 1000
                assert all(card.code is None for card in observation.graveyards[1])
                assert all(card.code is not None for card in observation.graveyards[0])
                announced_names = {action.parameters["code"] for action in actions}
                assert 47507260 in announced_names  # Original ID of a GOAT variant.
                assert 504700077 not in announced_names  # Alias variant is not a name.
                correct = next(action for action in actions
                               if action.parameters["code"] == correct_name)
                observation = env.step(correct)
                assert any(card.code == bottom_card for card in observation.banished[1])
                assert env.legal_actions()
                return
            observation = env.step(agent.select_action(observation, actions))
    pytest.fail("Question did not reach a card-name announcement")


def test_native_multi_zone_selection_uses_exact_three_byte_locations():
    # Only own Monster Zones 0, 1 and 2 are available.
    forbidden = 0xFFFFFFFF ^ 0b111
    decision = decode_decision(bytes((24, 0, 2)) + struct.pack("<I", forbidden))
    assert [choice.zones for choice in decision.choices] == [
        ((0, 4, 0), (0, 4, 1)),
        ((0, 4, 0), (0, 4, 2)),
        ((0, 4, 1), (0, 4, 2)),
    ]
    assert decision.choices[0].response == bytes((0, 4, 0, 0, 4, 1))
    assert {choice.kind for choice in decision.choices} == {"disable_zones"}
    place = decode_decision(bytes((18, 0, 2)) + struct.pack("<I", forbidden))
    assert {choice.kind for choice in place.choices} == {"place_zones"}
    with pytest.raises(ValueError, match="too few legal zones"):
        decode_decision(bytes((24, 0, 4)) + struct.pack("<I", forbidden))


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_ground_collapse_disables_two_chosen_monster_zones():
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    ground_collapse = 90502999
    if not (root / f"scripts/official/c{ground_collapse}.lua").is_file():
        pytest.skip("Ground Collapse script not installed")
    with GoatEnvironment("examples/decks/ground_collapse_probe.ydk",
                         "examples/decks/vanilla_probe.ydk", seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        env.reset()
        activated = disabled = summoned = False
        for _ in range(25):
            actions = env.legal_actions()
            action = None
            if not activated:
                action = next((choice for choice in actions if choice.kind == "activate"
                               and choice.parameters.get("code") == ground_collapse), None)
                activated |= action is not None
            if action is None and actions[0].kind == "disable_zones":
                action = next(choice for choice in actions if choice.parameters["zones"] == [
                    {"controller": 0, "location": 4, "sequence": 0},
                    {"controller": 0, "location": 4, "sequence": 1},
                ])
                disabled = True
            if action is None and disabled and not summoned:
                action = next((choice for choice in actions
                               if choice.kind == "normal_summon"), None)
                summoned |= action is not None
            if action is None:
                action = next((choice for choice in actions if choice.kind == "place"), None)
            if action is None:
                action = next((choice for choice in actions if choice.kind == "pass"), None)
            if action is None:
                action = next((choice for choice in actions if choice.kind == "end_phase"),
                              actions[0])
            observation = env.step(action)
            if summoned:
                slots = {choice.parameters["sequence"] for choice in env.legal_actions()
                         if choice.kind == "place"}
                assert activated and disabled and slots == {2, 3, 4}
                assert {(slot.player, slot.zone, slot.sequence)
                        for slot in observation.disabled_zones} == {
                            (0, "monster", 0), (0, "monster", 1)}
                return
        pytest.fail("Ground Collapse did not reach the zone selection")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_control_probe_complete_and_seeded():
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / "scripts/official/c79571449.lua").is_file():
        pytest.skip("full card script checkout not installed")
    with pytest.raises(SimulatorUnavailable, match="cannot simulate card"):
        RestrictedOcgcoreEngine(root)._load_deck(DECK)

    def run():
        with GoatEnvironment(DECK, DECK, 42, ExperimentalOcgcoreEngine(root)) as env:
            observation = env.reset()
            agent = RandomAgent(seed=42)
            trace = []
            for _ in range(3000):
                if env.is_terminal():
                    break
                action = agent.select_action(observation, env.legal_actions())
                trace.append((observation.acting_player, observation.phase,
                              action.kind, action.id))
                observation = env.step(action)
            assert env.is_terminal(), "probe exceeded 3000 decisions"
            return env.result(), tuple(trace)

    first = run()
    assert first[0] == 1
    assert len(first[1]) == 1116
    assert first == run()


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_control_probe_twelve_seed_protocol_coverage():
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / "scripts/official/c79571449.lua").is_file():
        pytest.skip("full card script checkout not installed")
    effect_yes_no_seen = False
    for seed in range(12):
        with GoatEnvironment(DECK, DECK, seed,
                             ExperimentalOcgcoreEngine(root)) as env:
            observation = env.reset()
            agent = RandomAgent(seed=seed)
            for _ in range(5000):
                if env.is_terminal():
                    break
                actions = env.legal_actions()
                effect_yes_no_seen |= any(
                    action.kind == "yes" and "code" in action.parameters
                    and "prompt_id" in action.parameters for action in actions)
                observation = env.step(agent.select_action(observation, actions))
            assert env.is_terminal(), f"seed {seed} exceeded 5000 decisions"
            assert env.result() in (0, 1), f"seed {seed} ended without a winner"
    assert effect_yes_no_seen


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_control_chaos_matchup_both_seats_complete():
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / "scripts/goat/c504700054.lua").is_file():
        pytest.skip("full card script checkout not installed")
    for decks in ((DECK, CHAOS_DECK), (CHAOS_DECK, DECK)):
        for seed in (0, 1, 2, 3):
            with GoatEnvironment(*decks, seed, ExperimentalOcgcoreEngine(root)) as env:
                observation = env.reset()
                agent = RandomAgent(seed)
                for _ in range(5000):
                    if env.is_terminal():
                        break
                    observation = env.step(agent.select_action(
                        observation, env.legal_actions()))
                assert env.is_terminal(), f"{decks} seed {seed} exceeded 5000 decisions"


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_opponent_extra_deck_identity_is_hidden(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / "scripts/goat/c504700054.lua").is_file():
        pytest.skip("full card script checkout not installed")
    original = read_ydk(CHAOS_DECK)
    changed = tmp_path / "alternate_extra.ydk"
    changed.write_text(
        "#main\n" + "\n".join(map(str, original.main)) + "\n#extra\n"
        + "\n".join(map(str, (86805855, *original.extra[1:]))) + "\n!side\n")

    def initial_view(opponent_deck):
        engine = ExperimentalOcgcoreEngine(root)
        try:
            decision = engine.reset(DECK, str(opponent_deck), 42)
            private_extra = tuple(card.code for card in engine.probe._query_location(
                1, LOCATION_EXTRA) if card is not None)
            return decision, private_extra
        finally:
            engine.close()

    first, first_private = initial_view(CHAOS_DECK)
    second, second_private = initial_view(changed)
    assert first_private != second_private
    assert first.observation.extra_deck_counts == (0, 3)
    assert first.observation.own_extra_deck == ()
    assert first.observation == second.observation
    assert first.legal_actions == second.legal_actions


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_experimental_duel_loads_fusion_and_41_card_main(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / "scripts/goat/c504700102.lua").is_file():
        pytest.skip("full card script checkout not installed")
    sample = read_ydk(DECK)
    deck_path = tmp_path / "expanded.ydk"
    deck_path.write_text(
        "#main\n" + "\n".join(map(str, (*sample.main, 87621407)))
        + "\n#extra\n504700102\n80071763\n!side\n",
        encoding="utf-8",
    )
    with GoatEnvironment(str(deck_path), DECK, 42,
                         ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert observation.deck_counts == (35, 35)
        assert observation.extra_deck_counts == (2, 0)
        assert {card.code for card in observation.own_extra_deck} == {504700102, 80071763}
        assert all(card.controller == 0 and card.zone == "extra"
                   for card in observation.own_extra_deck)
        assert observation.opponent_hand_count == 5
        assert len(observation.hand) == 6


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_hidden_opponent_effect_card_cannot_change_opening_view_or_actions(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / "scripts/official/c79571449.lua").is_file():
        pytest.skip("full card script checkout not installed")
    original = read_ydk(DECK)
    changed = list(original.main)
    changed[changed.index(2134346)] = 39507162  # Asura Priest -> Blade Knight
    alternate = tmp_path / "alternate.ydk"
    alternate.write_text("#main\n" + "\n".join(map(str, changed)) + "\n")

    def first_decision(opponent_deck):
        engine = ExperimentalOcgcoreEngine(root)
        try:
            decision = engine.reset(DECK, str(opponent_deck), 42)
            # Private query is test-only evidence that the hidden hand changed.
            hidden_hand = tuple(card.code for card in engine.probe._query_location(1, LOCATION_HAND)
                                if card is not None)
            return decision, hidden_hand
        finally:
            engine.close()

    baseline, first_hidden = first_decision(DECK)
    alternate_view, second_hidden = first_decision(alternate)
    assert first_hidden != second_hidden
    assert 2134346 in first_hidden and 39507162 in second_hidden
    assert baseline.observation == alternate_view.observation
    assert baseline.legal_actions == alternate_view.legal_actions


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_different_opponent_set_effect_cards_have_identical_visible_decisions(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / "scripts/official/c79571449.lua").is_file():
        pytest.skip("full card script checkout not installed")
    original = read_ydk(DECK)
    changed = list(original.main)
    changed[changed.index(2134346)] = 39507162
    alternate = tmp_path / "alternate.ydk"
    alternate.write_text("#main\n" + "\n".join(map(str, changed)) + "\n")

    def after_set(opponent_deck, target):
        with GoatEnvironment(DECK, str(opponent_deck), 42,
                             ExperimentalOcgcoreEngine(root)) as env:
            observation = env.reset()
            set_target = False
            for _ in range(40):
                if observation.viewer == 0 and observation.turn == 3:
                    assert set_target
                    private_code = env.engine.probe._query_location(1, LOCATION_MZONE)[0].code
                    return observation, env.legal_actions(), private_code
                actions = env.legal_actions()
                action = None
                if observation.acting_player == 1 and not set_target:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == target), None)
                    if action is not None:
                        set_target = True
                if action is None:
                    action = next((a for a in actions if a.kind == "end_phase"), None)
                if action is None:
                    action = next((a for a in actions if a.kind == "pass"), actions[0])
                observation = env.step(action)
            pytest.fail("did not reach the next player-zero draw phase")

    first_view, first_actions, first_private = after_set(DECK, 2134346)
    next_view, next_actions, next_private = after_set(alternate, 39507162)
    assert (first_private, next_private) == (2134346, 39507162)
    assert first_view.field[0].code is None
    assert first_view.known_opponent_cards == ()
    assert first_view == next_view
    assert first_actions == next_actions


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_different_opponent_set_traps_have_identical_visible_decisions(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / "scripts/official/c60082869.lua").is_file():
        pytest.skip("full card script checkout not installed")
    original = read_ydk(DECK)
    changed = list(original.main)
    # Seed 2 draws the last Dust Tornado copy in the opponent's opening hand.
    changed[len(changed) - 1 - changed[::-1].index(60082869)] = 56120475
    alternate = tmp_path / "alternate_trap.ydk"
    alternate.write_text("#main\n" + "\n".join(map(str, changed)) + "\n")

    def after_set(opponent_deck, target):
        with GoatEnvironment(DECK, str(opponent_deck), 2,
                             ExperimentalOcgcoreEngine(root)) as env:
            observation = env.reset()
            set_target = False
            for _ in range(80):
                if observation.viewer == 0 and observation.turn == 3:
                    assert set_target
                    private_code = next(card.code for card in env.engine.probe._query_location(
                        1, LOCATION_SZONE) if card is not None)
                    return observation, env.legal_actions(), private_code
                actions = env.legal_actions()
                action = None
                if observation.acting_player == 1 and not set_target:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == target), None)
                    if action is not None:
                        set_target = True
                if action is None:
                    action = next((a for a in actions if a.kind == "end_phase"), None)
                if action is None:
                    action = next((a for a in actions if a.kind == "pass"), actions[0])
                observation = env.step(action)
            pytest.fail("did not reach the next player-zero decision")

    first_view, first_actions, first_private = after_set(DECK, 60082869)
    next_view, next_actions, next_private = after_set(alternate, 56120475)
    assert (first_private, next_private) == (60082869, 56120475)
    assert any(card.controller == 1 and card.zone == "spell_trap"
               and card.position == "facedown" and card.code is None
               for card in first_view.field)
    assert first_view.known_opponent_cards == ()
    assert first_view == next_view
    assert first_actions == next_actions


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_dust_tornado_target_choice_hides_opponent_set_trap_identity(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / "scripts/official/c60082869.lua").is_file():
        pytest.skip("full card script checkout not installed")
    original = read_ydk(DECK)
    changed = list(original.main)
    # Seed 1 draws the last Sakuretsu copy in the opponent's opening hand.
    changed[len(changed) - 1 - changed[::-1].index(56120475)] = 60082869
    alternate = tmp_path / "alternate_target.ydk"
    alternate.write_text("#main\n" + "\n".join(map(str, changed)) + "\n")

    def target_decision(opponent_deck, target):
        with GoatEnvironment(DECK, str(opponent_deck), 1,
                             ExperimentalOcgcoreEngine(root)) as env:
            observation = env.reset()
            own_set = False
            opponent_sets = 0
            for _ in range(80):
                actions = env.legal_actions()
                action = None
                if observation.acting_player == 0:
                    if observation.turn == 1 and not own_set:
                        action = next((a for a in actions if a.kind == "set_spell_trap"
                                       and a.parameters.get("code") == 60082869), None)
                        own_set |= action is not None
                    if observation.turn == 3 and own_set and opponent_sets == 2:
                        action = next((a for a in actions if a.kind == "activate"
                                       and a.parameters.get("code") == 60082869), None)
                        if action is not None:
                            private_code = env.engine.probe._query_location(
                                1, LOCATION_SZONE)[1].code
                            observation = env.step(action)
                            target_view, target_actions = observation, env.legal_actions()
                            assert len(target_actions) == 2
                            target_action = next(a for a in target_actions
                                                 if a.parameters.get("sequence") == 1)
                            observation = env.step(target_action)
                            for _ in range(12):
                                if any(card.code == target
                                       for card in observation.graveyards[1]):
                                    return target_view, target_actions, private_code
                                responses = env.legal_actions()
                                response = next((a for a in responses if a.kind == "pass"),
                                                responses[0])
                                observation = env.step(response)
                            pytest.fail("Dust Tornado target did not reach opponent Graveyard")
                elif observation.turn == 2 and opponent_sets < 2:
                    set_code = 44095762 if opponent_sets == 0 else target  # Mirror Force first
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == set_code), None)
                    opponent_sets += action is not None
                if action is None:
                    action = next((a for a in actions if a.kind == "end_phase"), None)
                if action is None:
                    action = next((a for a in actions if a.kind == "pass"), actions[0])
                observation = env.step(action)
            pytest.fail("Dust Tornado target decision not reached")

    first_view, first_actions, first_private = target_decision(DECK, 56120475)
    next_view, next_actions, next_private = target_decision(alternate, 60082869)
    assert (first_private, next_private) == (56120475, 60082869)
    assert first_view == next_view
    assert first_actions == next_actions
    assert [action.kind for action in first_actions] == ["select_card", "select_card"]
    assert [action.parameters for action in first_actions] == [
        {"controller": 1, "location": 8, "sequence": 0},
        {"controller": 1, "location": 8, "sequence": 1},
    ]
