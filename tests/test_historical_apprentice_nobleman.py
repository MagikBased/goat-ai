"""Nobleman follows Apprentice's publicly revealed face-down Faith recruit."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

APPRENTICE = 504700013
FAITH = 31560081
OLD_VINDICTIVE = 45141844
GEMINI_ELF = 69140098
NOBLEMAN = 504700116


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_nobleman_banishes_recruited_face_down_faith_and_deck_copies(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{APPRENTICE}.lua", f"goat/c{NOBLEMAN}.lua",
                     f"official/c{FAITH}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    attacker_cards = [*([GEMINI_ELF] * 3),
                      *(code for code in VANILLA_DECK if code != GEMINI_ELF)]
    attacker_cards[3] = NOBLEMAN
    attacker = tmp_path / "attacker.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, attacker_cards))
                        + "\n#extra\n!side\n")
    defender = tmp_path / "defender.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        *([APPRENTICE] * 3), *([FAITH] * 3), *([OLD_VINDICTIVE] * 3),
        *VANILLA_DECK[9:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=15,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {GEMINI_ELF, NOBLEMAN} <= {c.code for c in obs.hand}
        assert APPRENTICE in {c.code for c in env.engine.probe.observation(1).hand}
        summoned = apprentice_set = battle = attacked = attack_targeted = False
        accepted = faith_selected = recruited = nobleman_used = nobleman_targeted = False
        for _ in range(120):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == GEMINI_ELF), None)
                summoned = action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not apprentice_set:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == APPRENTICE), None)
                apprentice_set = action is not None
            if obs.turn == 3 and obs.acting_player == 0 \
                    and obs.phase == "main1" and not battle:
                action = next((a for a in actions if a.kind == "battle_phase"), None)
                battle = action is not None
            if battle and obs.turn == 3 and obs.acting_player == 0 \
                    and obs.phase == "battle_start" and not attacked:
                action = next((a for a in actions if a.kind == "attack"
                               and a.parameters.get("code") == GEMINI_ELF), None)
                attacked = action is not None
            if attacked and not attack_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("controller") == 1
                               and "code" not in a.parameters), None)
                attack_targeted = action is not None
            if attack_targeted and not accepted and any(a.kind == "yes" for a in actions):
                action = next(a for a in actions if a.kind == "yes")
                accepted = True
            if accepted and not faith_selected and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == FAITH
                               and a.parameters.get("location") == 1), None)
                faith_selected = action is not None
            if faith_selected and not recruited:
                known = [c for c in env.engine.probe.observation(0)
                         .known_opponent_field_cards if c.code == FAITH]
                recruited = bool(known)
                if recruited:
                    assert len(known) == 1 and known[0].controller == 1
                    assert any(c.controller == 1 and c.zone == "monster"
                               and c.sequence == known[0].sequence
                               and c.position == "facedown" and c.code is None
                               for c in env.engine.probe.observation(0).field)
            if recruited and obs.turn == 3 and obs.acting_player == 0 \
                    and not nobleman_used:
                if obs.phase == "main2":
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == NOBLEMAN), None)
                    nobleman_used = action is not None
                elif action is None:
                    action = next((a for a in actions if a.kind == "main2"), None)
            if nobleman_used and not nobleman_targeted \
                    and actions[0].kind == "select_card":
                known = next(c for c in obs.known_opponent_field_cards if c.code == FAITH)
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("controller") == 1
                               and a.parameters.get("sequence") == known.sequence), None)
                assert action is not None and "code" not in action.parameters
                nobleman_targeted = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "main2", "end_phase")),
                    actions[0])
            obs = env.step(action)
            if nobleman_targeted and NOBLEMAN in {c.code for c in obs.graveyards[0]} \
                    and obs.chain == ():
                owner = env.engine.probe.observation(1)
                attacker_view = env.engine.probe.observation(0)
                faith_in_hand = sum(c.code == FAITH for c in owner.hand)
                assert recruited and faith_selected
                assert sum(c.code == FAITH for c in obs.banished[1]) \
                    == 3 - faith_in_hand
                assert not any(c.code == FAITH for c in obs.graveyards[1])
                assert not attacker_view.known_opponent_field_cards
                assert FAITH not in attacker_view.known_opponent_hand_cards
                assert any(reveal.recipient == 0 and any(card.code == FAITH
                           for card in reveal.cards)
                           for reveal in attacker_view.private_reveals)
                assert any(reveal.recipient == 1 and any(card.location == 1
                           for card in reveal.cards)
                           for reveal in owner.private_reveals)
                assert {f"goat/c{APPRENTICE}.lua", f"goat/c{NOBLEMAN}.lua",
                        f"official/c{FAITH}.lua"} <= (
                            env.engine.probe.loaded_script_sha256.keys())
                return
    pytest.fail(f"Apprentice / Nobleman line did not resolve: "
                f"{summoned=} {apprentice_set=} {battle=} {attacked=} "
                f"{attack_targeted=} {accepted=} {faith_selected=} {recruited=} "
                f"{nobleman_used=} {nobleman_targeted=} "
                f"turn={obs.turn} phase={obs.phase} "
                f"actions={[a.kind for a in env.legal_actions()]}")
