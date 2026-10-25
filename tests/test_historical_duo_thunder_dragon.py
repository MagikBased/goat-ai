"""Duo updates knowledge of two publicly searched Thunder Dragons."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

THUNDER = 504700054
DUO = 44763025


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("seed,expected_random_thunder", [(15, False), (98, True)])
def test_duo_discards_searched_thunder_and_updates_known_hand_count(
        tmp_path, seed, expected_random_thunder):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"goat/c{THUNDER}.lua", f"official/c{DUO}.lua")
    for relative in scripts:
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    thunder_deck = tmp_path / "thunder.ydk"
    thunder_deck.write_text("#main\n" + "\n".join(map(str, (
        *([THUNDER] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    duo_deck = tmp_path / "duo.ydk"
    duo_deck.write_text("#main\n" + "\n".join(map(str, (
        DUO, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(thunder_deck), str(duo_deck), seed=seed,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert sum(c.code == THUNDER for c in observation.hand) == 1
        assert DUO in {c.code for c in env.engine.probe.observation(1).hand}
        thunder_used = searched = filler_summoned = duo_used = second_discard = False
        random_thunder = False
        for _ in range(55):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0:
                if not thunder_used:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == THUNDER), None)
                    thunder_used |= action is not None
                if thunder_used and not searched \
                        and any(a.kind == "select_cards" for a in actions):
                    action = next((a for a in actions if a.kind == "select_cards"
                                   and len(a.parameters.get("cards", ())) == 2), None)
                    searched |= action is not None
                if searched and not filler_summoned and action is None \
                        and env.engine.probe.observation(1) \
                        .known_opponent_hand_cards.count(THUNDER) == 2:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") != THUNDER), None)
                    filler_summoned |= action is not None
            if searched and filler_summoned and observation.turn == 2 and not duo_used:
                attacker = env.engine.probe.observation(1)
                assert attacker.known_opponent_hand_cards.count(THUNDER) == 2
                assert [[c.code for c in reveal.cards]
                        for reveal in attacker.private_reveals] == [[THUNDER, THUNDER]]
            if searched and observation.turn == 2 and observation.acting_player == 1 \
                    and not duo_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == DUO), None)
                duo_used |= action is not None
            if searched and duo_used and observation.acting_player == 0 \
                    and not second_discard \
                    and actions[0].kind == "select_card":
                assert [link.card_code for link in observation.chain] == [DUO]
                random_thunder = sum(c.code == THUNDER for c in
                                     observation.graveyards[0]) == 2
                assert random_thunder == expected_random_thunder
                attacker = env.engine.probe.observation(1)
                assert attacker.known_opponent_hand_cards.count(THUNDER) == (
                    1 if random_thunder else 2)
                assert attacker.opponent_hand_count == len(observation.hand)
                assert any(a.parameters.get("code") == THUNDER for a in actions)
                assert all(a.parameters.get("location") == 2 for a in actions)
                action = next(a for a in actions if a.parameters.get("code") == THUNDER)
                second_discard = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if second_discard and DUO in {c.code for c in observation.graveyards[1]}:
                attacker = env.engine.probe.observation(1)
                assert observation.chain == ()
                assert attacker.life_points == (8000, 7000)
                assert attacker.known_opponent_hand_cards.count(THUNDER) == (
                    0 if random_thunder else 1)
                assert sum(c.code == THUNDER for c in observation.graveyards[0]) == (
                    3 if random_thunder else 2)
                assert attacker.opponent_hand_count == len(
                    env.engine.probe.observation(0).hand)
                assert set(scripts).issubset(env.engine.probe.loaded_script_sha256)
                return
    pytest.fail(f"Thunder/Duo line stalled: search={thunder_used}/{searched} "
                f"Duo={duo_used}/{second_discard} turn={observation.turn}")
