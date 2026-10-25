"""Scapegoat, Metamorphosis, Restrict, and Tsukuyomi GOAT Control line."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

SCAPEGOAT = 504700123
METAMORPHOSIS = 46411259
RESTRICT = 504700102
TSUKUYOMI = 34853266
SHEEP_CODES = {73915052, 73915053, 73915054, 73915055}
SOLEMN_JUDGMENT = 41420027


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_goat_control_token_restrict_equip_and_tsukuyomi_reset(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not all((root / path).is_file() for path in (
            f"scripts/goat/c{SCAPEGOAT}.lua",
            f"scripts/official/c{METAMORPHOSIS}.lua",
            f"scripts/goat/c{RESTRICT}.lua",
            f"scripts/official/c{TSUKUYOMI}.lua")):
        pytest.skip("GOAT combo scripts not installed")
    deck = tmp_path / "goat_control_line.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        (SCAPEGOAT, METAMORPHOSIS, TSUKUYOMI) * 3 + VANILLA_DECK[9:])))
        + f"\n#extra\n{RESTRICT}\n!side\n")
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        activated_goat = activated_meta = activated_restrict = False
        paid_token = chosen_fusion = chosen_target = False
        equipped = summoned_tsukuyomi = targeted_restrict = False
        reset_restrict = opponent_second_summoned = flipped_restrict = False
        reactivated_restrict = chosen_second_target = False
        second_target_code = None
        saw_same_turn_block = False
        opponent_summoned = False
        for _ in range(130):
            actions = env.legal_actions()
            if (observation.turn == 1 and observation.acting_player == 0
                    and sum(card.code in SHEEP_CODES for card in observation.field) == 4
                    and any(a.kind == "end_phase" for a in actions)):
                assert not any(a.kind == "activate"
                               and a.parameters.get("code") == METAMORPHOSIS
                               for a in actions)
                saw_same_turn_block = True
            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not activated_goat:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                activated_goat |= action is not None
            if observation.turn == 2 and observation.acting_player == 1 and not opponent_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                opponent_summoned |= action is not None
            if observation.turn == 4 and observation.acting_player == 1 and not opponent_second_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                opponent_second_summoned |= action is not None
                if action is not None:
                    second_target_code = action.parameters["code"]
            if observation.turn == 3 and observation.acting_player == 0 and not activated_meta:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == METAMORPHOSIS), None)
                activated_meta |= action is not None
            if activated_meta and not paid_token:
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") in SHEEP_CODES), action)
                paid_token |= action is not None and action.kind == "select_card"
            if paid_token and not chosen_fusion:
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == RESTRICT), action)
                chosen_fusion |= action is not None and action.kind == "select_card"
            if chosen_fusion and not activated_restrict:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == RESTRICT), action)
                activated_restrict |= action is not None and action.kind == "chain"
            if activated_restrict and not chosen_target:
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 4), action)
                chosen_target |= action is not None and action.kind == "select_card"
            if equipped and not summoned_tsukuyomi and observation.acting_player == 0:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == TSUKUYOMI), action)
                summoned_tsukuyomi |= action is not None and action.kind == "normal_summon"
            if summoned_tsukuyomi and not targeted_restrict:
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("code") == RESTRICT), action)
                targeted_restrict |= action is not None and action.kind == "select_card"
            if (reset_restrict and observation.turn == 5 and observation.acting_player == 0
                    and not flipped_restrict):
                action = next((a for a in actions if a.kind == "flip_summon"
                               and a.parameters.get("code") == RESTRICT), action)
                flipped_restrict |= action is not None and action.kind == "flip_summon"
            if flipped_restrict and not reactivated_restrict:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == RESTRICT), action)
                reactivated_restrict |= action is not None and action.kind == "chain"
            if reactivated_restrict and not chosen_second_target:
                action = next((a for a in actions if a.kind == "select_card"
                               and a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 4), action)
                chosen_second_target |= action is not None and action.kind == "select_card"
            if action is None:
                action = next((a for a in actions if a.kind in ("place", "select_position")), None)
            if action is None:
                action = next((a for a in actions if a.kind == "pass"), None)
            if action is None:
                action = next((a for a in actions if a.kind == "end_phase"), actions[0])
            observation = env.step(action)
            monsters = [card for card in observation.field if card.zone == "monster"]
            sheep = [card for card in monsters if card.code in SHEEP_CODES]
            if activated_goat and not activated_meta and len(sheep) == 4:
                if observation.turn == 1:
                    assert "player0:cannot_summon_this_turn:scapegoat" in observation.restrictions
                elif observation.turn == 3:
                    assert "player0:cannot_summon_this_turn:scapegoat" not in observation.restrictions
            if chosen_target and not equipped and not any(
                    card.controller == 1 for card in monsters):
                assert saw_same_turn_block
                assert activated_goat and opponent_summoned and activated_meta
                assert paid_token and chosen_fusion and activated_restrict
                assert len(sheep) == 3
                assert observation.extra_deck_counts[0] == 0
                assert any(card.code == RESTRICT and card.controller == 0 for card in monsters)
                assert any(card.code == 49003308 and card.controller == 0
                           and card.zone == "spell_trap" for card in observation.field)
                assert not any(card.code in SHEEP_CODES
                               for pile in observation.graveyards for card in pile)
                equipped = True
            if targeted_restrict and equipped and not reset_restrict:
                own = env.engine.probe.observation(0)
                set_restrict = next((card for card in own.field
                                     if card.controller == 0 and card.zone == "monster"
                                     and card.code == RESTRICT and card.position == "facedown"), None)
                if set_restrict is not None:
                    opponent = env.engine.probe.observation(1)
                    hidden = next(card for card in opponent.field
                                  if card.controller == 0 and card.zone == "monster"
                                  and card.sequence == set_restrict.sequence)
                    assert hidden.code is None and hidden.position == "facedown"
                    assert any(card.code == 49003308 for card in own.graveyards[1])
                    assert any(card.code == TSUKUYOMI for card in own.field)
                    reset_restrict = True
            if chosen_second_target and not any(
                    card.controller == 1 for card in monsters):
                own = env.engine.probe.observation(0)
                opponent = env.engine.probe.observation(1)
                assert opponent_second_summoned and flipped_restrict and reactivated_restrict
                assert any(card.code == RESTRICT and card.position != "facedown"
                           for card in own.field)
                assert any(card.code == second_target_code and card.zone == "spell_trap"
                           for card in own.field)
                assert not any(card.code == TSUKUYOMI for card in own.field)
                assert any(card.code == TSUKUYOMI for card in own.hand)
                assert any(card.code == RESTRICT and card.position != "facedown"
                           for card in opponent.field)
                return
    pytest.fail("GOAT Control Restrict/Tsukuyomi line did not resolve")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("negate_activation", [False, True])
def test_solemn_answers_metamorphosis_activation_not_effect_summon(
    tmp_path, negate_activation,
):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{SCAPEGOAT}.lua",
                     f"official/c{METAMORPHOSIS}.lua",
                     f"goat/c{RESTRICT}.lua",
                     f"official/c{SOLEMN_JUDGMENT}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    attacker = tmp_path / "goat_meta.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        (SCAPEGOAT, METAMORPHOSIS, TSUKUYOMI) * 3 + VANILLA_DECK[9:])))
        + f"\n#extra\n{RESTRICT}\n!side\n")
    defender = tmp_path / "solemn.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        *([SOLEMN_JUDGMENT] * 3), *VANILLA_DECK[3:])))
                        + "\n#extra\n!side\n")
    with GoatEnvironment(str(attacker), str(defender), seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {SCAPEGOAT, METAMORPHOSIS}.issubset(c.code for c in obs.hand)
        assert SOLEMN_JUDGMENT in {
            c.code for c in env.engine.probe.observation(1).hand}
        goat = solemn_set = meta = token_paid = responded = fusion_chosen = False
        for _ in range(80):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not goat:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                goat |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not solemn_set:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == SOLEMN_JUDGMENT), None)
                solemn_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not meta:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == METAMORPHOSIS), None)
                meta |= action is not None
            if meta and not token_paid and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               in SHEEP_CODES), None)
                token_paid |= action is not None
            if token_paid and obs.acting_player == 1 and not responded:
                solemn = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SOLEMN_JUDGMENT), None)
                if solemn is not None:
                    assert sum(c.code in SHEEP_CODES for c in obs.field) == 3
                    assert not any(c.code in SHEEP_CODES
                                   for pile in obs.graveyards for c in pile)
                    action = solemn if negate_activation else next(
                        a for a in actions if a.kind == "pass")
                    responded = True
            if responded and not negate_activation and not fusion_chosen \
                    and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == RESTRICT), None)
                fusion_chosen |= action is not None
            if responded and obs.turn == 3 and obs.acting_player == 0 \
                    and obs.phase == "main1" \
                    and any(a.kind == "end_phase" for a in actions):
                own_monsters = {c.code for c in obs.field
                                if c.controller == 0 and c.zone == "monster"}
                assert sum(code in SHEEP_CODES for code in own_monsters) == 3
                assert METAMORPHOSIS in {c.code for c in obs.graveyards[0]}
                assert not any(c.code in SHEEP_CODES
                               for pile in obs.graveyards for c in pile)
                if negate_activation:
                    assert obs.life_points == (8000, 4000)
                    assert RESTRICT not in own_monsters
                    assert obs.extra_deck_counts[0] == 1
                    assert SOLEMN_JUDGMENT in {c.code for c in obs.graveyards[1]}
                else:
                    assert fusion_chosen
                    assert obs.life_points == (8000, 8000)
                    assert RESTRICT in own_monsters
                    assert obs.extra_deck_counts[0] == 0
                    assert SOLEMN_JUDGMENT not in {c.code for c in obs.graveyards[1]}
                    assert any(c.controller == 1 and c.zone == "spell_trap"
                               for c in obs.field)
                loaded = env.engine.probe.loaded_script_sha256
                assert {f"official/c{METAMORPHOSIS}.lua",
                        f"official/c{SOLEMN_JUDGMENT}.lua"}.issubset(loaded)
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
    pytest.fail("Metamorphosis and Solemn did not resolve within 80 decisions")
