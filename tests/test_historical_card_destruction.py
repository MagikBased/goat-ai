"""Card Destruction hand reset precedes Night Assailant discard triggers."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

CARD_DESTRUCTION = 72892473
NIGHT_ASSAILANT = 16226796  # pre-errata GOAT variant
BANISHER_OF_THE_LIGHT = 61528025
SCAPEGOAT = 504700123  # GOAT variant
PROTECTOR = 24221739
EXTRA_VANILLAS = (
    32864, 549481, 1184620, 1761063, 1784619, 2118022, 2311603, 2468169,
    2483611, 2863439, 2964201, 3134241, 3170832, 3573512, 3797883,
    4035199, 4042268, 4179849, 4920010, 5265750,
)
PATCHED_CARD_DESTRUCTION_SHA256 = (
    "b58db8925866782d8b1876fe2965888e5bdf77b2d693351b60ba1413d1403b07"
)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_card_destruction_overdraw_patch_keeps_draw_prohibition(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck = tmp_path / "card_destruction_protector.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        CARD_DESTRUCTION, PROTECTOR, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {CARD_DESTRUCTION, PROTECTOR} <= {card.code for card in obs.hand}
        summoned = checked = False
        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / "card_destruction_protector.json"
                write_trajectory(path, env.trajectory())
                trajectory = read_trajectory(path)
                assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) == len(
                    trajectory.decisions)
                audit_trajectory_visibility(trajectory)
                assert env.engine.probe.loaded_script_sha256[
                    f"official/c{CARD_DESTRUCTION}.lua"] == PATCHED_CARD_DESTRUCTION_SHA256
                return
            actions = env.legal_actions()
            if not checked and obs.acting_player == 0 and obs.phase == "main1":
                if not summoned:
                    action = next((candidate for candidate in actions
                                   if candidate.kind == "normal_summon" and
                                   candidate.parameters.get("code") == PROTECTOR), None)
                    if action is not None:
                        summoned = True
                else:
                    action = None
                    if (any(card.code == PROTECTOR and card.zone == "monster"
                            for card in obs.field)
                            and any(candidate.kind == "end_phase" for candidate in actions)):
                        assert CARD_DESTRUCTION in {card.code for card in obs.hand}
                        assert not any(candidate.kind == "activate" and
                                       candidate.parameters.get("code") == CARD_DESTRUCTION
                                       for candidate in actions)
                        checked = True
                if action is None:
                    action = next((candidate for candidate in actions
                                   if candidate.kind in ("place", "pass", "end_phase")),
                                  actions[0])
            else:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
    pytest.fail("Protector draw-prohibition fixture did not finish")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("draw_shortfall", [0, 5])
def test_card_destruction_near_empty_deck_draw_result(tmp_path, draw_shortfall):
    """A short draw loses immediately; exactly enough cards loses next Draw Phase."""
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    script = f"official/c{CARD_DESTRUCTION}.lua"
    if not (root / "scripts" / script).is_file():
        pytest.skip(f"script {script} not installed")
    own = tmp_path / "card_destruction_40.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        CARD_DESTRUCTION, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    other = tmp_path / "vanilla_60.ydk"
    other.write_text("#main\n" + "\n".join(map(str, (
        *VANILLA_DECK, *EXTRA_VANILLAS))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(own), str(other), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert CARD_DESTRUCTION in {card.code for card in obs.hand}
        activated = resolved = False
        for _ in range(800):
            if env.is_terminal():
                assert activated and resolved
                assert env.result() == 1
                assert obs.deck_counts[0] == 0 < obs.deck_counts[1]
                assert obs.life_points == (8000, 8000)
                assert obs.phase == ("main1" if draw_shortfall else "draw")
                path = tmp_path / f"card_destruction_deckout_{draw_shortfall}.json"
                write_trajectory(path, env.trajectory())
                trajectory = read_trajectory(path)
                assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) == len(
                    trajectory.decisions)
                audit_trajectory_visibility(trajectory)
                assert env.engine.probe.loaded_script_sha256[script] == (
                    PATCHED_CARD_DESTRUCTION_SHA256)
                return
            actions = env.legal_actions()
            action = None
            if (obs.acting_player == 0 and obs.phase == "main1" and not activated
                    and any(candidate.kind == "end_phase" for candidate in actions)
                    and obs.deck_counts[0] == len(obs.hand) - 1 - draw_shortfall):
                action = next((candidate for candidate in actions
                               if candidate.kind == "activate" and
                               candidate.parameters.get("code") == CARD_DESTRUCTION), None)
                assert action is not None
                activated = True
            if action is None and actions[0].kind == "select_card":
                action = next((candidate for candidate in actions
                               if candidate.parameters.get("code") != CARD_DESTRUCTION),
                              actions[0])
            if action is None:
                action = next((candidate for candidate in actions
                               if candidate.kind in ("end_phase", "pass")), actions[0])
            obs = env.step(action)
            if activated and not resolved and obs.deck_counts[0] == 0:
                resolved = True
                assert env.is_terminal() == bool(draw_shortfall)
    pytest.fail("Card Destruction did not reach the expected draw boundary")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_card_destruction_opponent_empty_deck_draw_result(tmp_path):
    """The opponent may be the first player unable to complete the redraw."""
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    own = tmp_path / "card_destruction_60.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        CARD_DESTRUCTION, *VANILLA_DECK[1:], *EXTRA_VANILLAS))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(own), "examples/decks/vanilla_probe.ydk", seed=5,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert CARD_DESTRUCTION in {card.code for card in obs.hand}
        activated = False
        for _ in range(800):
            if env.is_terminal():
                assert activated and env.result() == 0
                assert obs.deck_counts[0] > 0 and obs.deck_counts[1] == 0
                assert obs.phase == "main1"
                path = tmp_path / "card_destruction_opponent_deckout.json"
                write_trajectory(path, env.trajectory())
                trajectory = read_trajectory(path)
                assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) == len(
                    trajectory.decisions)
                audit_trajectory_visibility(trajectory)
                assert env.engine.probe.loaded_script_sha256[
                    f"official/c{CARD_DESTRUCTION}.lua"] == PATCHED_CARD_DESTRUCTION_SHA256
                return
            actions = env.legal_actions()
            action = None
            if (not activated and obs.acting_player == 0 and obs.phase == "main1"
                    and obs.deck_counts[1] == 0
                    and any(candidate.kind == "end_phase" for candidate in actions)):
                action = next((candidate for candidate in actions
                               if candidate.kind == "activate" and
                               candidate.parameters.get("code") == CARD_DESTRUCTION), None)
                assert action is not None
                activated = True
            if action is None and actions[0].kind == "select_card":
                action = next((candidate for candidate in actions
                               if candidate.parameters.get("code") != CARD_DESTRUCTION),
                              actions[0])
            if action is None:
                action = next((candidate for candidate in actions
                               if candidate.kind in ("end_phase", "pass")), actions[0])
            obs = env.step(action)
    pytest.fail("opponent did not reach the empty-Deck draw boundary")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_scapegoat", [False, True])
def test_card_destruction_counts_hand_at_resolution_after_chain(tmp_path, chain_scapegoat):
    """A Quick-Play card spent as Chain Link 2 is absent from the later discard."""
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for script in (f"official/c{CARD_DESTRUCTION}.lua", f"goat/c{SCAPEGOAT}.lua"):
        if not (root / "scripts" / script).is_file():
            pytest.skip(f"script {script} not installed")
    deck = tmp_path / "card_destruction_goat.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        CARD_DESTRUCTION, SCAPEGOAT, *VANILLA_DECK[2:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {CARD_DESTRUCTION, SCAPEGOAT} <= {card.code for card in obs.hand}
        activated = response_chosen = resolved = False
        deck_counts_before = None
        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(5000):
            if env.is_terminal():
                assert resolved
                path = tmp_path / f"card_destruction_goat_{chain_scapegoat}.json"
                write_trajectory(path, env.trajectory())
                trajectory = read_trajectory(path)
                assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) == len(
                    trajectory.decisions)
                audit_trajectory_visibility(trajectory)
                loaded = env.engine.probe.loaded_script_sha256
                assert f"official/c{CARD_DESTRUCTION}.lua" in loaded
                if chain_scapegoat:
                    assert f"goat/c{SCAPEGOAT}.lua" in loaded
                return
            actions = env.legal_actions()
            action = None
            if not activated and obs.acting_player == 0 and obs.phase == "main1":
                action = next((candidate for candidate in actions
                               if candidate.kind == "activate" and
                               candidate.parameters.get("code") == CARD_DESTRUCTION), None)
                if action is not None:
                    activated = True
                    deck_counts_before = obs.deck_counts
                    assert len(obs.hand) == 6 and obs.opponent_hand_count == 5
            if activated and not response_chosen and action is None:
                goat = next((candidate for candidate in actions
                             if candidate.kind == "chain" and
                             candidate.parameters.get("code") == SCAPEGOAT), None)
                if goat is not None:
                    action = goat if chain_scapegoat else next(
                        candidate for candidate in actions if candidate.kind == "pass")
                    response_chosen = True
            if action is None:
                action = (agents[obs.acting_player].select_action(obs, actions) if resolved
                          else next((candidate for candidate in actions if candidate.kind in (
                              "pass", "place", "end_phase")), actions[0]))
            obs = env.step(action)
            if activated and response_chosen and not resolved and not obs.chain and (
                    CARD_DESTRUCTION in {card.code for card in obs.graveyards[0]}):
                assert deck_counts_before is not None
                expected_own_draw = 4 if chain_scapegoat else 5
                assert obs.deck_counts == (deck_counts_before[0] - expected_own_draw,
                                           deck_counts_before[1] - 5)
                assert len(obs.hand) == expected_own_draw
                assert obs.opponent_hand_count == 5
                assert sum(card.zone == "monster" and card.controller == 0
                           for card in obs.field) == (4 if chain_scapegoat else 0)
                assert not obs.known_opponent_hand_cards
                resolved = True
    pytest.fail("Card Destruction/Scapegoat fixture did not finish")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("seed,opponent_empty", [(92, False), (1142, True)])
def test_card_destruction_empty_hand_activation_gate(tmp_path, seed, opponent_empty):
    """At least one player needs another hand card at activation."""
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{CARD_DESTRUCTION}.lua").is_file():
        pytest.skip("Card Destruction script not installed")
    # Set four cards and activate Scapegoat from hand to leave an open
    # Spell/Trap Zone. The opponent can later empty a monster plus five cards.
    settable = (
        *([14087893] * 3), *([46411259] * 3), *([SCAPEGOAT] * 3),
        *([56120475] * 3), *([64697231] * 3), *([504700116] * 2),
        44763025, 79571449, 19613556, 5318639, 55144522,
        45986603, 44095762, 53582587, *([60082869] * 3),
    )
    deck = tmp_path / "card_destruction_gate.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        CARD_DESTRUCTION, *VANILLA_DECK[:12], *settable,
    ))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(deck), str(deck), seed=seed,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        asserted = False
        activated = False
        own_card_gate_checked = False
        original_decks = None
        agents = (RandomAgent(seed), RandomAgent(seed + 1))
        for _ in range(5000):
            if env.is_terminal():
                assert asserted
                trajectory = env.trajectory()
                path = tmp_path / f"card_destruction_gate_{seed}.json"
                write_trajectory(path, trajectory)
                restored = read_trajectory(path)
                assert verify_trajectory(restored, ExperimentalOcgcoreEngine(root)) == len(
                    restored.decisions)
                audit_trajectory_visibility(restored)
                assert f"official/c{CARD_DESTRUCTION}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                return
            actions = env.legal_actions()
            action = None
            if not asserted:
                if obs.turn == 1 and obs.acting_player == 0:
                    goats = sum(card.code == SCAPEGOAT for card in obs.hand)
                    if len(obs.hand) > 2:
                        action = next((a for a in actions if a.kind == "set_spell_trap"
                                       and a.parameters.get("code") != CARD_DESTRUCTION
                                       and (a.parameters.get("code") != SCAPEGOAT
                                            or goats > 1)), None)
                    if action is None and goats:
                        action = next((a for a in actions if a.kind == "activate"
                                       and a.parameters.get("code") == SCAPEGOAT), None)
                    offered = next((a for a in actions if a.kind == "activate"
                                    and a.parameters.get("code") == CARD_DESTRUCTION), None)
                    if not opponent_empty and len(obs.hand) == 1 and not activated \
                            and offered is not None:
                        assert obs.hand[0].code == CARD_DESTRUCTION
                        assert env.engine.probe.observation(1).opponent_hand_count == 1
                        assert env.engine.probe.observation(0).opponent_hand_count == 5
                        action = offered
                        original_decks = obs.deck_counts
                        activated = True
                elif obs.turn == 2 and obs.acting_player == 1 and opponent_empty:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is None:
                        action = next((a for a in actions
                                       if a.kind == "set_spell_trap"), None)
                elif obs.turn == 3 and obs.acting_player == 0 and opponent_empty:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None and not own_card_gate_checked:
                        assert len(obs.hand) == 2
                        assert CARD_DESTRUCTION in {card.code for card in obs.hand}
                        assert env.engine.probe.observation(0).opponent_hand_count == 0
                        assert any(a.kind == "activate" and
                                   a.parameters.get("code") == CARD_DESTRUCTION
                                   for a in actions)
                        own_card_gate_checked = True
                    if len(obs.hand) == 1 and obs.hand[0].code == CARD_DESTRUCTION:
                        assert own_card_gate_checked
                        assert env.engine.probe.observation(0).opponent_hand_count == 0
                        assert sum(card.controller == 0 and card.zone == "spell_trap"
                                   for card in obs.field) < 5
                        assert not any(a.kind == "activate" and
                                       a.parameters.get("code") == CARD_DESTRUCTION
                                       for a in actions)
                        asserted = True
                if action is None:
                    action = next((a for a in actions if a.kind in (
                        "place", "pass", "end_phase", "main2")), actions[0])
            else:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if activated and not asserted and not obs.chain and CARD_DESTRUCTION in {
                    card.code for card in obs.graveyards[0]}:
                assert original_decks is not None
                assert obs.deck_counts == (original_decks[0], original_decks[1] - 5)
                assert obs.hand == ()
                assert obs.opponent_hand_count == 5
                asserted = True
    pytest.fail("Card Destruction empty-hand fixture did not terminate")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_card_destruction_draws_before_night_assailant_triggers(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for script in (f"official/c{CARD_DESTRUCTION}.lua",
                   f"pre-errata/c{NIGHT_ASSAILANT}.lua"):
        if not (root / "scripts" / script).is_file():
            pytest.skip(f"script {script} not installed")
    deck = tmp_path / "card_destruction.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        CARD_DESTRUCTION, NIGHT_ASSAILANT, NIGHT_ASSAILANT,
        *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        activated = checked_reset = False
        target_slots = []
        before_hands = before_decks = None
        for _ in range(18):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not activated:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == CARD_DESTRUCTION), None)
                if action is not None:
                    own = env.engine.probe.observation(0)
                    other = env.engine.probe.observation(1)
                    before_hands = (Counter(c.code for c in own.hand
                                            if c.code != CARD_DESTRUCTION),
                                    Counter(c.code for c in other.hand))
                    before_decks = own.deck_counts
                    assert len(own.hand) == 6 and len(other.hand) == 5
                    activated = True
            if activated and actions[0].kind == "chain":
                assert len(actions) == 2
                assert all(a.parameters.get("code") == NIGHT_ASSAILANT
                           for a in actions)
                action = actions[0]
            if activated and actions[0].kind == "select_card":
                assert len(actions) == 1
                assert actions[0].parameters["code"] == NIGHT_ASSAILANT
                assert actions[0].parameters["location"] == 16
                target_slots.append(actions[0].parameters["sequence"])
                action = actions[0]
            if action is None:
                action = next((a for a in actions if a.kind in ("pass", "place")),
                              actions[0])
            obs = env.step(action)
            own = env.engine.probe.observation(0)
            other = env.engine.probe.observation(1)
            if activated and not checked_reset and len(own.graveyards[1]) == 5:
                assert before_hands is not None and before_decks is not None
                assert own.deck_counts == other.deck_counts == (
                    before_decks[0] - 5, before_decks[1] - 5)
                assert Counter(c.code for c in own.graveyards[0]
                               if c.code != CARD_DESTRUCTION) == before_hands[0]
                assert Counter(c.code for c in own.graveyards[1]) == before_hands[1]
                assert len(own.hand) == len(other.hand) == 5
                assert own.opponent_hand_count == other.opponent_hand_count == 5
                assert not own.private_reveals and not other.private_reveals
                checked_reset = True
            if len(other.private_reveals) == 2:
                assert checked_reset and target_slots == [0, 2]
                assert sum(c.code == NIGHT_ASSAILANT for c in own.hand) == 2
                assert all(c.code != NIGHT_ASSAILANT for c in own.graveyards[0])
                assert len(own.hand) == 7 and other.opponent_hand_count == 7
                assert len(other.hand) == 5 and own.opponent_hand_count == 5
                assert [[c.code for c in reveal.cards]
                        for reveal in other.private_reveals] == [
                            [NIGHT_ASSAILANT], [NIGHT_ASSAILANT]]
                assert not own.private_reveals
                loaded = env.engine.probe.loaded_script_sha256
                assert f"official/c{CARD_DESTRUCTION}.lua" in loaded
                assert f"pre-errata/c{NIGHT_ASSAILANT}.lua" in loaded
                return
    pytest.fail("Card Destruction / Night Assailant line did not finish")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_card_destruction_draws_full_count_under_banisher(tmp_path):
    """GOAT Netrep: replacement of the discards does not reduce either draw."""
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (CARD_DESTRUCTION, BANISHER_OF_THE_LIGHT):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"official script for {code} not installed")
    deck = tmp_path / "card_destruction_banisher.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        CARD_DESTRUCTION, BANISHER_OF_THE_LIGHT, *VANILLA_DECK[2:])))
        + "\n#extra\n!side\n")
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {CARD_DESTRUCTION, BANISHER_OF_THE_LIGHT} <= {c.code for c in obs.hand}
        summoned = activated = checked = False
        before_hands = before_decks = None
        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / "card_destruction_banisher.json"
                write_trajectory(path, env.trajectory())
                restored = read_trajectory(path)
                assert verify_trajectory(restored, ExperimentalOcgcoreEngine(root)) == len(
                    restored.decisions)
                audit_trajectory_visibility(restored)
                return
            actions = env.legal_actions()
            action = None
            if not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == BANISHER_OF_THE_LIGHT), None)
                summoned = action is not None
            if summoned and not activated and action is None:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == CARD_DESTRUCTION), None)
                if action is not None:
                    own = env.engine.probe.observation(0)
                    other = env.engine.probe.observation(1)
                    before_hands = (
                        Counter(c.code for c in own.hand if c.code != CARD_DESTRUCTION),
                        Counter(c.code for c in other.hand))
                    before_decks = own.deck_counts
                    assert len(own.hand) == 5 and len(other.hand) == 5
                    activated = True
            if action is None and not checked:
                action = next((a for a in actions if a.kind in (
                    "place", "pass", "end_phase")), actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if activated and not checked and CARD_DESTRUCTION in {
                    c.code for c in obs.banished[0]} and not obs.chain:
                assert before_hands is not None and before_decks is not None
                assert obs.deck_counts == (before_decks[0] - 4, before_decks[1] - 5)
                assert len(obs.hand) == 4 and obs.opponent_hand_count == 5
                assert obs.graveyards == ((), ())
                assert Counter(c.code for c in obs.banished[0]
                               if c.code != CARD_DESTRUCTION) == before_hands[0]
                assert Counter(c.code for c in obs.banished[1]) == before_hands[1]
                assert all(c.position == "faceup" for pile in obs.banished
                           for c in pile)
                assert not obs.private_reveals
                assert not env.engine.probe.observation(1).private_reveals
                loaded = env.engine.probe.loaded_script_sha256
                assert f"official/c{CARD_DESTRUCTION}.lua" in loaded
                assert f"official/c{BANISHER_OF_THE_LIGHT}.lua" in loaded
                checked = True
    pytest.fail("Card Destruction / Banisher line did not finish")
