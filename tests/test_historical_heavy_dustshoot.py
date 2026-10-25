"""A Set Dustshoot can respond to Heavy Storm before back-row destruction."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

DUSTSHOOT = 64697231
HEAVY = 19613556


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("respond", [False, True])
def test_dustshoot_can_chain_to_heavy_before_other_set_trap_is_destroyed(
        tmp_path, respond):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (DUSTSHOOT, HEAVY)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("Dustshoot or Heavy Storm script not installed")
    dust_deck = tmp_path / "dustshoot.ydk"
    dust_deck.write_text("#main\n" + "\n".join(map(str, (
        *([DUSTSHOOT] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    heavy_deck = tmp_path / "heavy.ydk"
    heavy_deck.write_text("#main\n" + "\n".join(map(str, (
        HEAVY, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(dust_deck), str(heavy_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert sum(card.code == DUSTSHOOT for card in obs.hand) >= 2
        assert HEAVY in {card.code for card in env.engine.probe.observation(1).hand}
        set_count = 0
        heavy_used = response_seen = monster_chosen = checked = False
        hand_before = deck_before = selected_code = None
        revealed = Counter()
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(5000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"heavy_dustshoot_{respond}.json"
                write_trajectory(path, env.trajectory())
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                                             env.trajectory().decisions)
                return
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and set_count < 2:
                action = next((candidate for candidate in actions
                               if candidate.kind == "set_spell_trap"
                               and candidate.parameters.get("code") == DUSTSHOOT), None)
                set_count += action is not None
            if obs.turn == 2 and obs.acting_player == 1 \
                    and set_count == 2 and not heavy_used:
                action = next((candidate for candidate in actions
                               if candidate.kind == "activate"
                               and candidate.parameters.get("code") == HEAVY), None)
                if action is not None:
                    assert sum(card.controller == 0 and card.zone == "spell_trap"
                               and card.position == "facedown" and card.code is None
                               for card in obs.field) == 2
                    deck_before = obs.deck_counts[1]
                    heavy_used = True
            if heavy_used and obs.acting_player == 0 and not response_seen:
                chain = next((candidate for candidate in actions
                              if candidate.kind == "chain"
                              and candidate.parameters.get("code") == DUSTSHOOT), None)
                if chain is not None:
                    assert [link.card_code for link in obs.chain] == [HEAVY]
                    hand_before = obs.opponent_hand_count
                    assert hand_before >= 4
                    assert not obs.private_reveals
                    action = chain if respond else next(
                        candidate for candidate in actions if candidate.kind == "pass")
                    response_seen = True
            if respond and response_seen and not monster_chosen \
                    and actions[0].kind == "select_card":
                assert [link.card_code for link in obs.chain] == [HEAVY, DUSTSHOOT]
                revealed = Counter(card.code for event in obs.private_reveals
                                   if event.recipient == 0 for card in event.cards
                                   if card.controller == 1 and card.location == 2)
                assert sum(revealed.values()) == hand_before
                assert Counter(obs.known_opponent_hand_cards) == revealed
                assert not env.engine.probe.observation(1).private_reveals
                assert all("sequence" not in candidate.parameters for candidate in actions)
                action = next((candidate for candidate in actions
                               if candidate.parameters.get("code") in revealed), None)
                assert action is not None
                selected_code = action.parameters["code"]
                monster_chosen = True
            if action is None and not checked:
                action = next((candidate for candidate in actions
                               if candidate.kind in ("place", "pass", "end_phase")),
                              actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if response_seen and not checked \
                    and sum(card.code == DUSTSHOOT for card in obs.graveyards[0]) == 2 \
                    and HEAVY in {card.code for card in obs.graveyards[1]}:
                chooser = env.engine.probe.observation(0)
                storm_player = env.engine.probe.observation(1)
                assert not obs.chain
                assert not any(card.zone == "spell_trap" for card in obs.field)
                assert chooser.deck_counts[1] == deck_before + int(respond)
                assert chooser.opponent_hand_count == hand_before - int(respond)
                if respond:
                    assert monster_chosen
                    assert Counter(chooser.known_opponent_hand_cards) == (
                        revealed - Counter((selected_code,)))
                else:
                    assert not chooser.private_reveals
                    assert not chooser.known_opponent_hand_cards
                assert not storm_player.private_reveals
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail("Heavy Storm / Dustshoot duel did not finish")
