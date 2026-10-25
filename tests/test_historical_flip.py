"""Source-backed Flip Effect regression on a real GOAT-mode duel."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

DEKOICHI = 87621407
BOOK_OF_MOON = 14087893
TSUKUYOMI = 34853266


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_dekoichi_flip_summon_draws_one_without_bokoichi(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / "scripts/official/c87621407.lua").is_file():
        pytest.skip("full card script checkout not installed")
    cards = (DEKOICHI,) + VANILLA_DECK[1:]
    deck = tmp_path / "dekoichi.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, cards)) + "\n")
    with GoatEnvironment(str(deck), str(deck), seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        set_card = False
        flipped = False
        before: tuple[int, int] | None = None
        for _ in range(40):
            choices = env.legal_actions()
            action = None
            if observation.acting_player == 0 and observation.turn == 1 and not set_card:
                action = next((choice for choice in choices if choice.kind == "set_monster"
                               and choice.parameters.get("code") == DEKOICHI), None)
                set_card |= action is not None
            if observation.acting_player == 0 and observation.turn == 3 and not flipped:
                action = next((choice for choice in choices if choice.kind == "flip_summon"
                               and choice.parameters.get("code") == DEKOICHI), None)
                if action is not None:
                    assert set_card
                    flipped = True
                    before = (observation.deck_counts[0], len(observation.hand))
            if action is None:
                action = next((choice for choice in choices
                               if choice.kind == "end_phase"), None)
            if action is None:
                action = next((choice for choice in choices if choice.kind == "pass"),
                              choices[0])
            observation = env.step(action)
            if flipped and before is not None and observation.deck_counts[0] == before[0] - 1:
                assert len(observation.hand) == before[1] + 1
                assert any(card.code == DEKOICHI and card.position == "faceup"
                           for card in observation.field)
                return
        pytest.fail("Dekoichi Flip Effect did not resolve within 40 decisions")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_dekoichi_draws_again_after_book_of_moon_resets_it(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (DEKOICHI, BOOK_OF_MOON):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    cards = (DEKOICHI,) * 3 + (BOOK_OF_MOON,) * 3 + VANILLA_DECK[6:]
    deck = tmp_path / "dekoichi_book.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        set_card = first_flip = book_used = second_flip = False
        first_draw_count = None
        before_first = before_second = None
        for _ in range(100):
            actions = env.legal_actions()
            action = None
            if observation.acting_player == 0:
                if observation.turn == 1 and not set_card:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == DEKOICHI), None)
                    set_card |= action is not None
                elif observation.turn == 3:
                    if not first_flip:
                        action = next((a for a in actions if a.kind == "flip_summon"
                                       and a.parameters.get("code") == DEKOICHI), None)
                        if action is not None:
                            first_flip = True
                            before_first = observation.deck_counts[0]
                    elif first_draw_count is None and observation.deck_counts[0] == before_first - 1:
                        first_draw_count = observation.deck_counts[0]
                    if first_draw_count is not None and not book_used and action is None:
                        action = next((a for a in actions if a.kind == "activate"
                                       and a.parameters.get("code") == BOOK_OF_MOON), None)
                        book_used |= action is not None
                elif observation.turn == 5 and book_used and not second_flip:
                    action = next((a for a in actions if a.kind == "flip_summon"
                                   and a.parameters.get("code") == DEKOICHI), None)
                    if action is not None:
                        second_flip = True
                        before_second = observation.deck_counts[0]
            if book_used and actions[0].kind == "select_card" and action is None:
                action = next((a for a in actions if a.parameters.get("code") == DEKOICHI
                               and a.parameters.get("controller") == 0), None)
            if book_used and observation.turn == 3 and observation.acting_player == 0 \
                    and BOOK_OF_MOON in {c.code for c in observation.graveyards[0]}:
                own = next(c for c in observation.field if c.controller == 0
                           and c.zone == "monster")
                other = env.engine.probe.observation(1)
                hidden = next(c for c in other.field if c.controller == 0
                              and c.zone == "monster")
                assert own.code == DEKOICHI and own.position == "facedown"
                assert hidden.code is None and hidden.position == "facedown"
                assert not any(a.kind == "flip_summon" and a.parameters.get("code")
                               == DEKOICHI for a in actions)
            if second_flip and before_second is not None \
                    and observation.deck_counts[0] == before_second - 1:
                assert first_draw_count == before_first - 1
                assert observation.deck_counts[0] == first_draw_count - 2
                assert any(c.code == DEKOICHI and c.position == "faceup"
                           for c in observation.field)
                loaded = env.engine.probe.loaded_script_sha256
                assert f"official/c{DEKOICHI}.lua" in loaded
                assert f"official/c{BOOK_OF_MOON}.lua" in loaded
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "select_position", "pass", "end_phase")),
                              actions[0])
            observation = env.step(action)
    pytest.fail("Dekoichi did not draw twice after Book of Moon reset it")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_tsukuyomi_resets_dekoichi_then_returns_for_another_flip(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for code in (DEKOICHI, TSUKUYOMI):
        if not (root / f"scripts/official/c{code}.lua").is_file():
            pytest.skip(f"script for {code} not installed")
    deck = tmp_path / "dekoichi_tsukuyomi.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        *([DEKOICHI] * 3), *([TSUKUYOMI] * 3),
        *VANILLA_DECK[6:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        dekoichi_set = first_flip = tsuk_summoned = tsuk_targeted = False
        tsuk_returned = second_flip = False
        deck_before_first = deck_before_second = None
        for _ in range(115):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not dekoichi_set:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == DEKOICHI), None)
                dekoichi_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0:
                if not first_flip:
                    action = next((a for a in actions if a.kind == "flip_summon"
                                   and a.parameters.get("code") == DEKOICHI), None)
                    if action is not None:
                        deck_before_first = obs.deck_counts[0]
                        first_flip = True
                if first_flip and not tsuk_summoned \
                        and obs.deck_counts[0] == deck_before_first - 1 \
                        and action is None:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == TSUKUYOMI), None)
                    tsuk_summoned |= action is not None
            if tsuk_summoned and not tsuk_targeted and actions[0].kind == "select_card":
                assert any(link.card_code == TSUKUYOMI for link in obs.chain)
                action = next((a for a in actions if a.parameters.get("code") == DEKOICHI
                               and a.parameters.get("controller") == 0), None)
                tsuk_targeted |= action is not None
            if tsuk_targeted and obs.turn == 3 and obs.acting_player == 0 \
                    and any(c.code == DEKOICHI and c.position == "facedown"
                            for c in obs.field):
                assert not any(a.kind == "flip_summon" and a.parameters.get("code")
                               == DEKOICHI for a in actions)
                opponent = env.engine.probe.observation(1)
                assert any(c.controller == 0 and c.zone == "monster" and c.code is None
                           for c in opponent.field)
            if tsuk_targeted and obs.turn >= 4 and not tsuk_returned:
                own = env.engine.probe.observation(0)
                assert TSUKUYOMI in {c.code for c in own.hand}
                assert not any(c.code == TSUKUYOMI for c in own.field)
                tsuk_returned = True
            if obs.turn == 5 and obs.acting_player == 0 and tsuk_returned \
                    and not second_flip:
                action = next((a for a in actions if a.kind == "flip_summon"
                               and a.parameters.get("code") == DEKOICHI), None)
                if action is not None:
                    deck_before_second = obs.deck_counts[0]
                    second_flip = True
            if second_flip and obs.deck_counts[0] == deck_before_second - 1:
                assert first_flip and tsuk_summoned and tsuk_targeted and tsuk_returned
                assert deck_before_second == deck_before_first - 2
                assert any(c.code == DEKOICHI and c.position == "faceup"
                           for c in obs.field)
                assert TSUKUYOMI in {c.code for c in env.engine.probe.observation(0).hand}
                assert {f"official/c{code}.lua" for code in (
                    DEKOICHI, TSUKUYOMI)}.issubset(
                        env.engine.probe.loaded_script_sha256)
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "select_position", "pass", "end_phase")),
                    actions[0])
            obs = env.step(action)
    pytest.fail("Tsukuyomi/Dekoichi repeat-Flip line did not finish")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_tsukuyomi_only_faceup_monster_must_set_itself_and_stays(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/official/c{TSUKUYOMI}.lua").is_file():
        pytest.skip("Tsukuyomi script not installed")
    deck = tmp_path / "tsukuyomi_self.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        *([TSUKUYOMI] * 3), *VANILLA_DECK[3:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=3,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert TSUKUYOMI in {c.code for c in obs.hand}
        summoned = targeted = set_self = False
        for _ in range(40):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == TSUKUYOMI), None)
                summoned |= action is not None
            if summoned and not targeted and actions[0].kind == "select_card":
                assert [link.card_code for link in obs.chain] == [TSUKUYOMI]
                assert len(actions) == 1
                assert actions[0].parameters["code"] == TSUKUYOMI
                assert actions[0].parameters["controller"] == 0
                action = actions[0]
                targeted = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "select_position", "pass", "end_phase")),
                    actions[0])
            obs = env.step(action)
            own = env.engine.probe.observation(0)
            facedown = next((c for c in own.field if c.code == TSUKUYOMI
                             and c.zone == "monster" and c.position == "facedown"), None)
            if targeted and facedown is not None and not set_self:
                other = env.engine.probe.observation(1)
                hidden = next(c for c in other.field if c.controller == 0
                              and c.zone == "monster" and c.sequence == facedown.sequence)
                assert hidden.code is None and hidden.position == "facedown"
                assert (0, "monster", facedown.sequence, TSUKUYOMI) in {
                    (c.controller, c.zone, c.sequence, c.code)
                    for c in other.known_opponent_field_cards}
                set_self = True
            if obs.turn == 2 and obs.phase == "main1" and set_self:
                assert facedown is not None
                assert not any(c.code == TSUKUYOMI and c.position == "faceup"
                               for c in own.field)
                assert f"official/c{TSUKUYOMI}.lua" in (
                    env.engine.probe.loaded_script_sha256)
                return
    pytest.fail("Tsukuyomi self-target did not persist through End Phase")
