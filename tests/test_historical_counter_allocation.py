"""Anti-Spell pays its cost from two public Pitch-Black Power Stones."""

import os
from importlib.util import find_spec
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

STONE = 34029630
ANTI_SPELL = 53112492
POT = 55144522


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("allocation", [(2, 0), (1, 1), (0, 2)])
def test_native_counter_allocation_negates_pot_and_completes_duel(tmp_path, allocation):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (STONE, ANTI_SPELL, POT):
        assert (root / f"scripts/official/c{code}.lua").is_file()
    counter_deck = tmp_path / "counter_stones.ydk"
    counter_deck.write_text("#main\n" + "\n".join(map(str, (
        STONE, STONE, ANTI_SPELL, *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    pot_deck = tmp_path / "pot.ydk"
    pot_deck.write_text("#main\n" + "\n".join(map(str, (
        POT, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(counter_deck), str(pot_deck), 100,
                         ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        random_agent = RandomAgent(100)
        stone_sets = 0
        pot_activated = counter_selected = cost_resolved = False
        deck_before_pot = None
        for _ in range(3000):
            if env.is_terminal():
                break
            actions = env.legal_actions()
            action = None
            if not counter_selected and observation.turn == 1 \
                    and observation.acting_player == 0:
                if stone_sets < 2:
                    action = next((candidate for candidate in actions
                                   if candidate.kind == "set_spell_trap"
                                   and candidate.parameters.get("code") == STONE), None)
                    stone_sets += action is not None
                if stone_sets == 2 and action is None:
                    action = next((candidate for candidate in actions
                                   if candidate.kind == "set_spell_trap"
                                   and candidate.parameters.get("code") == ANTI_SPELL), None)
            if not counter_selected and observation.turn == 2:
                if observation.acting_player == 1 and not pot_activated:
                    action = next((candidate for candidate in actions
                                   if candidate.kind == "activate"
                                   and candidate.parameters.get("code") == POT), None)
                    if action is not None:
                        deck_before_pot = observation.deck_counts[1]
                        pot_activated = True
                elif observation.acting_player == 0:
                    stones_up = sum(card.code == STONE and card.position == "faceup"
                                    for card in observation.field)
                    code = STONE if stones_up < 2 else ANTI_SPELL
                    action = next((candidate for candidate in actions
                                   if candidate.kind == "chain"
                                   and candidate.parameters.get("code") == code), None)
            if actions[0].kind == "select_counters":
                assert pot_activated and stone_sets == 2
                assert [link.card_code for link in observation.chain] == [POT, ANTI_SPELL]
                stones = sorted((card for card in observation.field if card.code == STONE),
                                key=lambda card: card.sequence)
                assert len(stones) == 2
                assert [card.counters for card in stones] == [((1, 3),), ((1, 3),)]
                opponent_view = env.engine.probe.observation(1)
                assert [card.counters for card in sorted(
                    (card for card in opponent_view.field if card.code == STONE),
                    key=lambda card: card.sequence)] == [((1, 3),), ((1, 3),)]
                assert len(actions) == 3
                offered = {tuple(next((card["amount"] for card in candidate.parameters["cards"]
                                       if card["sequence"] == sequence), 0)
                                 for sequence in (0, 1)) for candidate in actions}
                assert offered == {(2, 0), (1, 1), (0, 2)}
                if allocation == (1, 1) and find_spec("torch") is not None:
                    import torch

                    from goat_ai.training import CardVocabulary, LegalActionPolicy, encode_decision

                    vocabulary = CardVocabulary.from_goat_whitelist(
                        root / "banlist/GOAT.lflist.conf", native_root=root)
                    features = encode_decision(observation, actions, vocabulary, 28)
                    assert features.action_target_context.shape[-1] == 7
                    assert features.action_numbers.shape == (3, 103)
                    assert len({tuple(row.flatten().tolist()) for row in
                                features.action_target_context}) == 3
                    logits = LegalActionPolicy(vocabulary.size, width=8,
                                               feature_version=28)(features)
                    assert logits.shape == (3,)
                    assert torch.isfinite(logits).all()
                action = next(candidate for candidate in actions if tuple(
                    next((card["amount"] for card in candidate.parameters["cards"]
                          if card["sequence"] == sequence), 0)
                    for sequence in (0, 1)) == allocation)
                counter_selected = True
            if action is None:
                action = (next((candidate for candidate in actions
                                if candidate.kind in ("pass", "end_phase")), actions[0])
                          if not cost_resolved else
                          random_agent.select_action(observation, actions))
            observation = env.step(action)
            if action.kind == "select_counters":
                stones = sorted((card for card in observation.field if card.code == STONE),
                                key=lambda card: card.sequence)
                assert [card.counters for card in stones] == [
                    ((1, 3 - amount),) for amount in allocation]
            if counter_selected and not cost_resolved and POT in {
                    card.code for card in observation.graveyards[1]}:
                assert observation.deck_counts[1] == deck_before_pot
                assert ANTI_SPELL in {card.code for card in observation.graveyards[0]}
                cost_resolved = True
        assert counter_selected and cost_resolved and env.is_terminal()
        trajectory = env.trajectory()
        path = tmp_path / "counter_allocation.json"
        write_trajectory(path, trajectory)
        replay = read_trajectory(path)
        assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) == len(replay.decisions)
        assert audit_trajectory_visibility(replay)["decisions"] == len(replay.decisions)
