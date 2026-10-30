"""Synthetic legacy-response playback; no real human replay compatibility claim."""

import hashlib
import json
import os
import random
import struct
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine import native_messages
from goat_ai.engine.decks import Decklist, read_ydk
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.ocgcore_probe import GOAT_FLAGS, OcgcoreProbe
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import VisibilityViolation, audit_decision_visibility
from goat_ai.replay.edopro_container import (
    DUEL_FLAG_64BIT,
    EXTENDED_HEADER,
    HEADER,
    NEW_REPLAY,
    YRP1,
    YRPX,
    parse_edopro_container,
)
from goat_ai.replay.edopro_reconstruct import (
    ReplayReconstructionError,
    _canonical_card_response,
    reconstruct_legacy_responses,
)
from goat_ai.replay.live_mirror import LiveDuelMirror
from scripts.probe_random_decks import generate_deck, write_deck

THUNDER_DRAGON = 504700054
GROUND_COLLAPSE = 90502999


@pytest.mark.parametrize("kind,payload", [
    (1, struct.pack("<IH", 1, 1)),
    (2, struct.pack("<IB", 1, 1)),
    (3, b"\x02"),
])
def test_edopro_compact_card_selection_maps_to_public_choice(kind, payload):
    class Probe:
        _pending_message = (bytes((15, 1, 0)) + struct.pack("<III", 1, 1, 7))

    class Engine:
        probe = Probe()

    response = struct.pack("<I", kind) + payload
    assert _canonical_card_response(Engine(), response) == struct.pack("<III", 0, 1, 1)


def test_edopro_compact_card_selection_rejects_out_of_range_bits():
    class Probe:
        _pending_message = (bytes((15, 1, 0)) + struct.pack("<III", 1, 1, 7))

    class Engine:
        probe = Probe()

    response = struct.pack("<I", 3) + b"\x80"
    assert _canonical_card_response(Engine(), response) == response


@pytest.mark.parametrize("prompt", [
    bytes((20, 1, 0)) + struct.pack("<III", 1, 1, 7),
    bytes((23, 1, 0)) + struct.pack("<IIII", 4, 1, 1, 0) + struct.pack("<I", 7),
])
def test_edopro_compact_tribute_and_sum_selections(prompt):
    class Probe:
        _pending_message = prompt

    class Engine:
        probe = Probe()

    assert _canonical_card_response(Engine(), struct.pack("<I", 3) + b"\x02") \
        == struct.pack("<III", 0, 1, 1)


def _legacy_replay(responses: list[bytes], *, settings=(8000, 5, 1),
                   rule_cards=(), extended=True,
                   decks=(VANILLA_DECK, VANILLA_DECK), seed_words=(43, 44, 45, 46),
                   raw=False):
    names = (struct.pack("<I", 1) + b"\x00" * 40) * 2
    payload = names + struct.pack("<IIIQ", *settings, GOAT_FLAGS)
    for deck in decks:
        payload += struct.pack("<I", len(deck))
        payload += struct.pack(f"<{len(deck)}I", *deck)
        payload += struct.pack("<I", 0)
    payload += struct.pack("<I", len(rule_cards))
    payload += struct.pack(f"<{len(rule_cards)}I", *rule_cards)
    payload += b"".join(bytes((len(response),)) + response for response in responses)
    payload += b"\x00"
    flags = NEW_REPLAY | DUEL_FLAG_64BIT | (EXTENDED_HEADER if extended else 0)
    header = HEADER.pack(YRP1, 1, flags, 12345, len(payload), 0, b"\x00" * 8)
    if extended:
        header += struct.pack("<5Q", 1, *seed_words)
    data = header + payload
    return data if raw else parse_edopro_container(data)


def _wrapped_replay(legacy: bytes, *, duel_flags=GOAT_FLAGS,
                    seed_words=(43, 44, 45, 46), raw=False):
    names = (struct.pack("<I", 1) + b"\x00" * 40) * 2
    packet = bytes((231,)) + struct.pack("<I", len(legacy)) + legacy
    payload = names + struct.pack("<Q", duel_flags) + packet
    flags = NEW_REPLAY | DUEL_FLAG_64BIT | EXTENDED_HEADER
    header = HEADER.pack(YRPX, 1, flags, 12345, len(payload), 0, b"\x00" * 8)
    header += struct.pack("<5Q", 1, *seed_words)
    data = header + payload
    return data if raw else parse_edopro_container(data)


@pytest.fixture
def native_legacy_responses():
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    responses = []
    views = []
    with OcgcoreProbe(root / "build/libocgcore.so", root / "database/cards.cdb",
                      root / "scripts") as probe:
        probe.first_replay_decision((43, 44, 45, 46), VANILLA_DECK, VANILLA_DECK)
        for _ in range(1000):
            prompt = probe.decode_pending()
            views.append(probe.observation(prompt.player))
            value = prompt.choices[0].response
            response = (struct.pack("<I", value & 0xffffffff)
                        if isinstance(value, int) else value)
            responses.append(response)
            if probe.respond(value).terminal:
                break
        else:
            pytest.fail("source duel exceeded decision bound")
    return root, responses, views


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_reconstructs_complete_native_legacy_response_trace(native_legacy_responses):
    root, responses, views = native_legacy_responses
    replay = _legacy_replay(responses)
    trace = reconstruct_legacy_responses(replay, root)
    assert len(trace.decisions) == len(responses) == len(views)
    assert trace.saved_response_count == len(responses)
    # The public adapter adds an attacker-slot hint to the raw native view
    # during attack-target responses; all other visible fields must match.
    assert tuple(replace(record.observation, pending_attack=None)
                 for record in trace.decisions) == tuple(views)
    assert all(record.selected_action in record.legal_actions
               for record in trace.decisions)
    for record in trace.decisions:
        audit_decision_visibility(record)
    assert all(card.code is None
               for record in trace.decisions
               for card in record.observation.field
               if card.controller != record.observation.viewer
               and card.position == "facedown")
    assert trace.winner in (0, 1)
    assert trace.terminal_observation.life_points[trace.winner] > 0
    assert trace.replay_sha256 == replay.sha256
    assert trace.embedded_replay_sha256 is None
    assert "build/libocgcore.so" in trace.asset_sha256


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_live_mirror_tracks_room_responses_and_emits_policy_choice(native_legacy_responses):
    root, responses, views = native_legacy_responses
    mirror = LiveDuelMirror(root, historical_patches=True)
    try:
        mirror.start((43, 44, 45, 46),
                     (Decklist(VANILLA_DECK, ()), Decklist(VANILLA_DECK, ())))
        actor = views[0].viewer
        prompt_type = mirror._engine.probe._pending_message[0]
        mirror.verify_prompt(actor, prompt_type)
        chosen = mirror._engine.action_for_recorded_response(responses[0])

        class FixedAgent:
            def select_action(self, observation, legal_actions):
                assert observation.viewer == actor
                assert all(card.code is None for card in observation.field
                           if card.controller != actor and card.position == "facedown")
                assert chosen in legal_actions
                return chosen

        assert mirror.choose(actor, FixedAgent()) == responses[0]
        mirror.confirm_response(actor, responses[0])
        for response, view in zip(responses[1:], views[1:], strict=True):
            mirror.confirm_response(view.viewer, response)
        assert mirror.response_count == len(responses)
        assert mirror.decision.terminal
        assert len(mirror.records) == len(responses)
    finally:
        mirror.close()


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_reconstructs_staged_field_zones_from_one_saved_response(monkeypatch):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    first = read_ydk("examples/decks/ground_collapse_probe.ydk")
    second = read_ydk("examples/decks/vanilla_probe.ydk")
    decks = (tuple(reversed(first.main)), tuple(reversed(second.main)))
    responses = []
    zone_prompts = 0
    with OcgcoreProbe(root / "build/libocgcore.so", root / "database/cards.cdb",
                      root / "scripts") as probe:
        probe.first_replay_decision((43, 44, 45, 46), *decks)
        for _ in range(2000):
            native = probe.decode_pending()
            zone_prompts += probe._pending_message[0] == 24
            choice = next((item for item in native.choices
                           if item.kind == "activate" and item.code == GROUND_COLLAPSE), None)
            if choice is None:
                choice = next((item for item in native.choices
                               if item.kind in ("pass", "end_phase")), native.choices[0])
            response = (struct.pack("<I", choice.response & 0xffffffff)
                        if isinstance(choice.response, int) else choice.response)
            responses.append(response)
            if probe.respond(choice.response).terminal:
                break
        else:
            pytest.fail("recorded Ground Collapse duel did not finish")
    assert zone_prompts == 1
    replay = _legacy_replay(responses, decks=decks)
    monkeypatch.setattr(native_messages, "MAX_ZONE_SELECTION_COMBINATIONS", 1)
    trace = reconstruct_legacy_responses(replay, root)
    assert trace.saved_response_count == len(responses)
    assert len(trace.decisions) == len(responses) + 1
    zone_actions = [record.selected_action for record in trace.decisions
                    if record.selected_action.kind == "disable_zones"]
    assert len(zone_actions) == 2
    assert [len(action.parameters["zones"]) for action in zone_actions] == [1, 2]
    assert trace.winner in (0, 1)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_reconstruction_fails_closed_when_visible_action_audit_fails(
        native_legacy_responses, monkeypatch, tmp_path, capsys):
    from goat_ai.replay import edopro_reconstruct
    from scripts.inspect_edopro_replay import main

    root, responses, _ = native_legacy_responses

    def reject_hidden_choice(_record):
        raise VisibilityViolation("opponent hand choice reveals unknown identity")

    monkeypatch.setattr(edopro_reconstruct, "audit_decision_visibility",
                        reject_hidden_choice)
    replay = _legacy_replay(responses)
    with pytest.raises(ReplayReconstructionError, match="player-visible action audit failed"):
        reconstruct_legacy_responses(replay, root)

    path = tmp_path / "source.yrp"
    path.write_bytes(_legacy_replay(responses, raw=True))
    monkeypatch.setattr(sys, "argv", ["inspect_edopro_replay.py", str(path),
                                       "--reconstruct-native", str(root)])
    with pytest.raises(SystemExit) as exited:
        main()
    assert exited.value.code == 1
    report = json.loads(capsys.readouterr().out)[0]
    assert report["conditional_native_reconstruction"] == "failed"
    assert report["reconstruction_failure_code"] == "visibility_audit_failed"
    assert "reconstruction_response_index" not in report
    assert report["training_ready"] is False
    assert "opponent hand choice" not in str(report)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_reconstruction_rejects_divergent_and_incomplete_responses(
        native_legacy_responses, tmp_path, monkeypatch, capsys):
    from scripts.inspect_edopro_replay import main

    root, responses, _ = native_legacy_responses
    changed = responses.copy()
    changed[0] = b"\x7f" * 4
    with pytest.raises(ReplayReconstructionError, match="response 0") as failed:
        reconstruct_legacy_responses(_legacy_replay(changed), root)
    assert failed.value.code == "illegal_saved_response"
    assert failed.value.response_index == 0
    path = tmp_path / "divergent.yrp"
    path.write_bytes(_legacy_replay(changed, raw=True))
    monkeypatch.setattr(sys, "argv", ["inspect_edopro_replay.py", str(path),
                                       "--reconstruct-native", str(root)])
    with pytest.raises(SystemExit) as exited:
        main()
    assert exited.value.code == 1
    report = json.loads(capsys.readouterr().out)[0]
    assert report["reconstruction_failure_code"] == "illegal_saved_response"
    assert report["reconstruction_response_index"] == 0
    assert report["training_ready"] is False
    assert changed[0].hex() not in str(report)
    with pytest.raises(ReplayReconstructionError, match="before native terminal"):
        reconstruct_legacy_responses(_legacy_replay(responses[:-1]), root)

    partial = reconstruct_legacy_responses(
        _legacy_replay(responses[:-1]), root, allow_incomplete=True)
    assert partial.saved_response_count == len(responses) - 1
    assert partial.native_terminal is False
    assert partial.winner is None
    assert len(partial.decisions) == len(responses) - 1
    for record in partial.decisions:
        audit_decision_visibility(record)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_reconstructs_embedded_yrpx_with_both_file_hashes(native_legacy_responses):
    root, responses, _ = native_legacy_responses
    legacy = _legacy_replay(responses, raw=True)
    wrapper = _wrapped_replay(legacy)
    trace = reconstruct_legacy_responses(wrapper, root)
    assert trace.replay_sha256 == wrapper.sha256
    assert trace.embedded_replay_sha256 == hashlib.sha256(legacy).hexdigest()
    assert trace.saved_response_count == len(responses)
    assert trace.winner in (0, 1)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_native_inspection_reports_only_conditional_counts_and_hashes(
        native_legacy_responses, tmp_path, monkeypatch, capsys):
    from scripts.inspect_edopro_replay import main

    root, responses, _ = native_legacy_responses
    legacy = _legacy_replay(responses, raw=True)
    path = tmp_path / "source.yrpX"
    path.write_bytes(_wrapped_replay(legacy, raw=True))
    monkeypatch.setattr(sys, "argv", ["inspect_edopro_replay.py", str(path),
                                       "--reconstruct-native", str(root)])
    main()
    report = json.loads(capsys.readouterr().out)[0]
    assert report["conditional_native_reconstruction"] == "matched"
    assert report["reconstructed_decisions"] == len(responses)
    assert report["saved_response_count"] == len(responses)
    assert report["training_ready"] is False
    assert len(report["native_asset_manifest_sha256"]) == 64
    assert all(str(code) not in str(report) for code in VANILLA_DECK)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_unpatched_external_comparison_is_never_strict_intake(
        native_legacy_responses, tmp_path, monkeypatch, capsys):
    from scripts.inspect_edopro_replay import main

    root, responses, _ = native_legacy_responses
    path = tmp_path / "source.yrp"
    path.write_bytes(_legacy_replay(responses, raw=True))
    command = ["inspect_edopro_replay.py", str(path),
               "--reconstruct-native", str(root), "--compare-external-unpatched"]
    monkeypatch.setattr(sys, "argv", command)
    main()
    report = json.loads(capsys.readouterr().out)[0]
    assert report["conditional_native_reconstruction"] == "matched"
    assert report["reconstruction_asset_mode"] == "external_unpatched_comparison"
    assert report["training_ready"] is False
    assert report["native_goat_compatibility_candidate"] is False
    monkeypatch.setattr(sys, "argv", command + ["--require-goat-candidate"])
    with pytest.raises(SystemExit) as rejected:
        main()
    assert rejected.value.code == 2


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_partial_inspection_reports_nonterminal_decisions(
        native_legacy_responses, tmp_path, monkeypatch, capsys):
    from scripts.inspect_edopro_replay import main

    root, responses, _ = native_legacy_responses
    path = tmp_path / "partial.yrp"
    path.write_bytes(_legacy_replay(responses[:-1], raw=True))
    command = ["inspect_edopro_replay.py", str(path),
               "--reconstruct-native", str(root),
               "--allow-partial-reconstruction"]
    monkeypatch.setattr(sys, "argv", command)
    main()
    report = json.loads(capsys.readouterr().out)[0]
    assert report["conditional_native_reconstruction"] == "partial"
    assert report["native_terminal"] is False
    assert report["reconstructed_decisions"] == len(responses) - 1
    assert report["native_goat_compatibility_candidate"] is False
    assert report["training_ready"] is False
    monkeypatch.setattr(sys, "argv", command + ["--require-goat-candidate"])
    with pytest.raises(SystemExit) as rejected:
        main()
    assert rejected.value.code == 2


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_strict_goat_intake_saves_private_summary_and_rejects_failed_deck_screen(
        native_legacy_responses, tmp_path, monkeypatch, capsys):
    from scripts import inspect_edopro_replay as inspect

    root, responses, _ = native_legacy_responses
    path = tmp_path / "source.yrp"
    path.write_bytes(_legacy_replay(responses, raw=True))
    report_path = tmp_path / "intake.json"
    command = ["inspect_edopro_replay.py", str(path),
               "--native-deck-screen", str(root),
               "--reconstruct-native", str(root),
               "--require-goat-candidate", "--report", str(report_path)]
    monkeypatch.setattr(sys, "argv", command)
    inspect.main()
    report = json.loads(report_path.read_text())
    assert report == json.loads(capsys.readouterr().out)
    assert report[0]["native_goat_compatibility_candidate"] is True
    assert report[0]["training_ready"] is False
    assert all(str(code) not in str(report) for code in VANILLA_DECK)

    monkeypatch.setattr(inspect, "goat_native_deck_screen",
                        lambda *_args: {"goat_native_deck_screen": "rejected",
                                        "goat_native_decks_rejected": 1,
                                        "goat_native_side_decks_checked": False})
    with pytest.raises(SystemExit) as rejected:
        inspect.main()
    assert rejected.value.code == 2
    assert json.loads(report_path.read_text())[0][
        "native_goat_compatibility_candidate"] is False
    capsys.readouterr()


def test_reconstruction_rejects_mismatched_yrpx_wrapper():
    legacy = _legacy_replay([b"\xff" * 4], raw=True)
    wrapper = _wrapped_replay(legacy, duel_flags=0)
    with pytest.raises(ReplayReconstructionError, match="wrapper disagrees"):
        reconstruct_legacy_responses(wrapper, ".cache/goat-ai")
    wrapper = _wrapped_replay(legacy, seed_words=(1, 2, 3, 4))
    with pytest.raises(ReplayReconstructionError, match="wrapper disagrees"):
        reconstruct_legacy_responses(wrapper, ".cache/goat-ai")


def test_native_inspection_fails_closed_without_exposing_replay_values(
        tmp_path, monkeypatch, capsys):
    from scripts.inspect_edopro_replay import main

    path = tmp_path / "mismatched.yrpX"
    legacy = _legacy_replay([b"\xff" * 4], raw=True)
    path.write_bytes(_wrapped_replay(legacy, duel_flags=0, raw=True))
    monkeypatch.setattr(sys, "argv", ["inspect_edopro_replay.py", str(path),
                                       "--reconstruct-native", ".cache/goat-ai"])
    with pytest.raises(SystemExit) as exited:
        main()
    assert exited.value.code == 1
    report = json.loads(capsys.readouterr().out)[0]
    assert report["conditional_native_reconstruction"] == "failed"
    assert report["reconstruction_failure_code"] == "wrapper_mismatch"
    assert "reconstruction_response_index" not in report
    assert report["training_ready"] is False
    assert all(str(code) not in str(report) for code in VANILLA_DECK)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("copy_count", (0, 1, 2))
def test_reconstructs_saved_thunder_search_as_staged_visible_actions(monkeypatch,
                                                                     copy_count):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/goat/c{THUNDER_DRAGON}.lua").is_file():
        pytest.skip("GOAT Thunder Dragon script not installed")
    seed = 4
    main = (THUNDER_DRAGON,) * 3 + VANILLA_DECK[3:]
    ordered = []
    for team, deck in enumerate((main, VANILLA_DECK)):
        cards = list(deck)
        random.Random(seed * 2 + team).shuffle(cards)
        ordered.append(tuple(cards))
    responses = []
    activated = searched = False
    with OcgcoreProbe(root / "build/libocgcore.so", root / "database/cards.cdb",
                      root / "scripts") as probe:
        probe.first_replay_decision((5, 6, 7, 8), *ordered)
        for _ in range(3000):
            prompt = probe.decode_pending()
            action = prompt.choices[0]
            if not activated:
                activation = next((choice for choice in prompt.choices
                                   if choice.kind == "activate"
                                   and choice.code == THUNDER_DRAGON), None)
                if activation is not None:
                    action = activation
                    activated = True
            elif not searched:
                search = next((choice for choice in prompt.choices
                               if (choice.kind == "select_cards"
                                   and len(choice.cards) == copy_count
                                   and all(card[0] == THUNDER_DRAGON
                                           for card in choice.cards))
                               or (copy_count == 1 and choice.kind == "select_card"
                                   and choice.code == THUNDER_DRAGON
                                   and choice.location == 1)), None)
                if search is not None:
                    action = search
                    searched = True
            value = action.response
            responses.append(struct.pack("<I", value & 0xffffffff)
                             if isinstance(value, int) else value)
            if probe.respond(value).terminal:
                break
        else:
            pytest.fail("Thunder Dragon source duel did not reach terminal")
    assert activated and searched
    replay = _legacy_replay(responses, decks=tuple(ordered),
                            seed_words=(5, 6, 7, 8))
    monkeypatch.setattr(native_messages, "MAX_CARD_SELECTION_COMBINATIONS", 1)
    trace = reconstruct_legacy_responses(replay, root)
    assert trace.saved_response_count == len(responses)
    assert len(trace.decisions) == len(responses) + (1 if copy_count else 0)
    for record in trace.decisions:
        audit_decision_visibility(record)
    if copy_count:
        assert any(record.selected_action.kind == "select_card"
                   and record.selected_action.parameters.get("code") == THUNDER_DRAGON
                   for record in trace.decisions)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_reconstructs_saved_sum_choice_as_staged_visible_actions(tmp_path, monkeypatch):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    seed = 10097
    paths = (tmp_path / "sum_first.ydk", tmp_path / "sum_second.ydk")
    write_deck(paths[0], generate_deck(root, seed))
    write_deck(paths[1], generate_deck(root, seed + 1_000_000))
    responses = []
    saw_sum = False
    with GoatEnvironment(*(str(path) for path in paths), seed=seed,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        agent = RandomAgent(seed)
        for _ in range(3000):
            actions = env.legal_actions()
            if env.engine.probe._pending_message[0] == 23 and not saw_sum:
                action = actions[0]
                saw_sum = True
            else:
                action = agent.select_action(observation, actions)
            assert not env.engine.recorded_selection_in_progress()
            choice = env.engine._choices[actions.index(action)]
            value = choice.response
            responses.append(struct.pack("<I", value & 0xffffffff)
                             if isinstance(value, int) else value)
            observation = env.step(action)
            if env.is_terminal():
                break
        else:
            pytest.fail("sum source duel did not reach terminal")
    assert saw_sum
    ordered = []
    for team, path in enumerate(paths):
        cards = list(read_ydk(path).main)
        random.Random(seed * 2 + team).shuffle(cards)
        ordered.append(tuple(cards))
    replay = _legacy_replay(responses, decks=tuple(ordered),
                            seed_words=tuple(seed + i + 1 for i in range(4)))
    monkeypatch.setattr(native_messages, "MAX_SUM_SELECTION_COMBINATIONS", 1)
    trace = reconstruct_legacy_responses(replay, root)
    assert trace.saved_response_count == len(responses)
    assert len(trace.decisions) > len(responses)
    for record in trace.decisions:
        audit_decision_visibility(record)
    assert any(record.selected_action.kind == "finish_selection"
               and "selection_sum_target" in record.selected_action.parameters
               for record in trace.decisions)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_reconstructs_saved_counter_allocation_as_staged_visible_actions(tmp_path, monkeypatch):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    stone, anti_spell, pot = 34029630, 53112492, 55144522
    own = tmp_path / "counter_stones.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        stone, stone, anti_spell, *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    opponent = tmp_path / "pot.ydk"
    opponent.write_text("#main\n" + "\n".join(map(str, (
        pot, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    responses = []
    stone_sets = 0
    pot_activated = counter_selected = False
    with GoatEnvironment(str(own), str(opponent), 100,
                         ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        agent = RandomAgent(100)
        for _ in range(3000):
            actions = env.legal_actions()
            action = None
            if not counter_selected and obs.turn == 1 and obs.acting_player == 0:
                if stone_sets < 2:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == stone), None)
                    stone_sets += action is not None
                if stone_sets == 2 and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == anti_spell), None)
            if not counter_selected and obs.turn == 2:
                if obs.acting_player == 1 and not pot_activated:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == pot), None)
                    pot_activated |= action is not None
                elif obs.acting_player == 0:
                    stones_up = sum(card.code == stone and card.position == "faceup"
                                    for card in obs.field)
                    code = stone if stones_up < 2 else anti_spell
                    action = next((a for a in actions if a.kind == "chain"
                                   and a.parameters.get("code") == code), None)
            if actions[0].kind == "select_counters":
                assert len(actions) == 3
                action = next(a for a in actions if sorted(
                    card["amount"] for card in a.parameters["cards"]) == [1, 1])
                counter_selected = True
            if action is None:
                action = (next((a for a in actions if a.kind in ("pass", "end_phase")),
                               actions[0]) if not counter_selected else
                          agent.select_action(obs, actions))
            choice = env.engine._choices[actions.index(action)]
            value = choice.response
            responses.append(struct.pack("<I", value & 0xffffffff)
                             if isinstance(value, int) else value)
            obs = env.step(action)
            if env.is_terminal():
                break
        else:
            pytest.fail("counter source duel did not reach terminal")
    assert counter_selected
    ordered = []
    for team, path in enumerate((own, opponent)):
        cards = list(read_ydk(path).main)
        random.Random(100 * 2 + team).shuffle(cards)
        ordered.append(tuple(cards))
    replay = _legacy_replay(responses, decks=tuple(ordered),
                            seed_words=(101, 102, 103, 104))
    monkeypatch.setattr(native_messages, "MAX_COUNTER_SELECTION_COMBINATIONS", 1)
    trace = reconstruct_legacy_responses(replay, root)
    assert trace.saved_response_count == len(responses)
    assert len(trace.decisions) == len(responses) + 1
    staged = [record for record in trace.decisions
              if record.selected_action.parameters.get("counter_stage")]
    assert len(staged) == 2
    assert [record.selected_action.parameters["counter_index"]
            for record in staged] == [0, 1]
    assert [record.selected_action.parameters["counter_remaining"]
            for record in staged] == [1, 0]
    for record in trace.decisions:
        audit_decision_visibility(record)


def test_reconstruction_rejects_non_goat_or_unreproducible_startup():
    replay = _legacy_replay([b"\xff" * 4])
    bad = [
        _legacy_replay([b"\xff" * 4], settings=(4000, 5, 1)),
        _legacy_replay([b"\xff" * 4], rule_cards=(123,)),
        _legacy_replay([b"\xff" * 4], extended=False),
        replace(replay, duel_flags=0),
    ]
    for item in bad:
        with pytest.raises(ReplayReconstructionError, match="startup"):
            reconstruct_legacy_responses(item, ".cache/goat-ai")
