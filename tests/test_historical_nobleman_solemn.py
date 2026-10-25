"""Solemn negates Nobleman before a set Faith or Deck copies are revealed."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.observations import TargetSlotView

NOBLEMAN = 504700116
SOLEMN = 41420027
FAITH = 31560081


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("negate", [False, True])
def test_solemn_response_prevents_nobleman_flip_deck_verification(tmp_path, negate):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{NOBLEMAN}.lua", f"official/c{SOLEMN}.lua",
               f"official/c{FAITH}.lua"}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required card script not installed")
    attacker = tmp_path / "nobleman.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        NOBLEMAN, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
    defender_cards = list(VANILLA_DECK)
    for index, code in ((0, SOLEMN), (1, FAITH), (2, FAITH), (6, FAITH)):
        defender_cards[index] = code
    defender = tmp_path / "faith_solemn.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, defender_cards))
                        + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert NOBLEMAN in {c.code for c in obs.hand}
        assert {FAITH, SOLEMN} <= {
            c.code for c in env.engine.probe.observation(1).hand}
        faith_set = solemn_set = nobleman_used = targeted = solemn_chained = False
        deck_before = None
        for _ in range(80):
            actions = env.legal_actions()
            action = None
            if obs.turn == 2 and obs.acting_player == 1:
                if not faith_set:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == FAITH), None)
                    faith_set = action is not None
                if faith_set and not solemn_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == SOLEMN), None)
                    solemn_set = action is not None
            if obs.turn == 3 and obs.acting_player == 0 and solemn_set \
                    and not nobleman_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == NOBLEMAN), None)
                if action is not None:
                    nobleman_used = True
                    deck_before = obs.deck_counts
            if nobleman_used and not targeted and actions[0].kind == "select_card":
                assert any(c.controller == 1 and c.zone == "monster"
                           and c.code is None and c.position == "facedown"
                           for c in obs.field)
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 4
                               and "code" not in a.parameters), None)
                targeted = action is not None
            if targeted and obs.acting_player == 1 and obs.chain \
                    and obs.chain[-1].card_code == NOBLEMAN:
                attacker_view = env.engine.probe.observation(0)
                hidden = next(c for c in attacker_view.field if c.controller == 1
                              and c.zone == "monster" and c.position == "facedown")
                assert hidden.code is None
                assert attacker_view.chain[0].targets == obs.chain[0].targets == (TargetSlotView(
                    1, "monster", hidden.sequence),)
            if negate and targeted and obs.acting_player == 1 \
                    and not solemn_chained:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SOLEMN), None)
                if option is not None:
                    assert [link.card_code for link in obs.chain] == [NOBLEMAN]
                    action = option
                    solemn_chained = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if targeted and NOBLEMAN in {c.code for c in obs.graveyards[0]} \
                    and not obs.chain and obs.turn == 3:
                chooser = env.engine.probe.observation(0)
                owner = env.engine.probe.observation(1)
                if negate:
                    assert solemn_chained and chooser.life_points == (8000, 4000)
                    assert chooser.deck_counts == deck_before
                    assert not chooser.private_reveals and not owner.private_reveals
                    assert not any(c.code == FAITH for c in chooser.banished[1])
                    assert any(c.code is None and c.controller == 1
                               and c.position == "facedown" for c in chooser.field)
                    assert any(c.code == FAITH and c.position == "facedown"
                               for c in owner.field)
                    assert SOLEMN in {c.code for c in chooser.graveyards[1]}
                else:
                    assert not solemn_chained and chooser.life_points == (8000, 8000)
                    assert chooser.deck_counts == (deck_before[0], deck_before[1] - 2)
                    assert sum(c.code == FAITH for c in chooser.banished[1]) == 3
                    assert not any(c.code == FAITH for c in chooser.graveyards[1])
                    assert any(reveal.recipient == 0 for reveal in chooser.private_reveals)
                    assert any(reveal.recipient == 1 for reveal in owner.private_reveals)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                return
    pytest.fail("Nobleman / Solemn response did not resolve")
