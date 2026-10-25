"""D.D. Warrior Lady's optional Damage Step banish against Morphing Jar."""

import os
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

DD_WARRIOR_LADY = 7572887
MORPHING_JAR = 33508719


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("banish", [False, True])
def test_dd_warrior_lady_optional_banish_before_morphing_jar_resolution(tmp_path,
                                                                          banish):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (DD_WARRIOR_LADY, MORPHING_JAR):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    own_deck = tmp_path / "warrior_lady.ydk"
    own_deck.write_text("#main\n" + "\n".join(map(str, (
        DD_WARRIOR_LADY, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    other_deck = tmp_path / "morphing_jar.ydk"
    other_deck.write_text("#main\n" + "\n".join(map(str, (
        MORPHING_JAR, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own_deck), str(other_deck), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        summoned = jar_set = attacked = trigger_seen = choice_made = False
        old_hands = old_deck_counts = None
        for _ in range(55):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 \
                    and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == DD_WARRIOR_LADY), None)
                summoned = action is not None
            if observation.turn == 2 and observation.acting_player == 1 \
                    and not jar_set:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == MORPHING_JAR), None)
                jar_set = action is not None
            if observation.turn == 3 and observation.acting_player == 0 \
                    and summoned and jar_set and not attacked:
                action = next((a for a in actions if a.kind in (
                    "battle_phase", "attack")), None)
                if action is not None and action.kind == "attack":
                    target = next(c for c in observation.field
                                  if c.zone == "monster" and c.controller == 1)
                    assert target.code is None and target.position == "facedown"
                    attacked = True
            if attacked and observation.acting_player == 0 and not choice_made:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == DD_WARRIOR_LADY), None)
                if option is not None:
                    assert observation.phase == "damage_step"
                    assert [(link.card_code, link.controller)
                            for link in observation.chain] == [(MORPHING_JAR, 1)]
                    target = next(c for c in observation.field
                                  if c.zone == "monster" and c.controller == 1)
                    assert target.code == MORPHING_JAR and target.position == "faceup"
                    other = env.engine.probe.observation(1)
                    old_hands = (Counter(c.code for c in observation.hand),
                                 Counter(c.code for c in other.hand))
                    old_deck_counts = observation.deck_counts
                    trigger_seen = True
                    choice_made = True
                    action = option if banish else next(a for a in actions
                                                       if a.kind == "pass")
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "main2", "end_phase")), actions[0])
            observation = env.step(action)
            if trigger_seen and observation.turn == 3 and observation.phase == "main2":
                assert old_hands is not None and old_deck_counts is not None
                own = env.engine.probe.observation(0)
                other = env.engine.probe.observation(1)
                for player in (0, 1):
                    assert Counter(c.code for c in own.graveyards[player]
                                   if c.code != MORPHING_JAR) == old_hands[player]
                assert own.deck_counts == other.deck_counts == (
                    old_deck_counts[0] - 5, old_deck_counts[1] - 5)
                assert len(own.hand) == len(other.hand) == 5
                assert own.opponent_hand_count == other.opponent_hand_count == 5
                assert own.life_points == (8000, 8000)
                assert (DD_WARRIOR_LADY in {c.code for c in own.banished[0]}) == banish
                assert (MORPHING_JAR in {c.code for c in own.banished[1]}) == banish
                assert (MORPHING_JAR in {c.code for c in own.graveyards[1]}) != banish
                assert not any(c.code == MORPHING_JAR for c in own.field)
                if banish:
                    assert not any(c.code == DD_WARRIOR_LADY for c in own.field)
                else:
                    assert any(c.code == DD_WARRIOR_LADY for c in own.field)
                assert "official/c7572887.lua" in env.engine.probe.loaded_script_sha256
                assert "official/c33508719.lua" in env.engine.probe.loaded_script_sha256
                return
    pytest.fail("D.D. Warrior Lady / Morphing Jar battle did not resolve")
