"""A pinned native discrepancy against the pre-errata Last Will ruling."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

LAST_WILL = 504700147
SANGAN = 504700178
CANNON_SOLDIER = 11384280


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.xfail(strict=True, reason=(
    "pinned Last Will custom-event script does not offer the historical "
    "same-controller order choice with Sangan"))
def test_last_will_and_sangan_controller_can_order_same_time_effects(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if any(not (root / "scripts" / "goat" / f"c{code}.lua").is_file()
           for code in (LAST_WILL, SANGAN)):
        pytest.skip("full GOAT card script checkout not installed")
    deck = tmp_path / "last_will_sangan.ydk"
    deck.write_text("#main\n" + "\n".join(map(str, (
        *([LAST_WILL] * 3), SANGAN, *([CANNON_SOLDIER] * 3),
        *VANILLA_DECK[7:]))) + "\n#extra\n!side\n")
    with GoatEnvironment(str(deck), "examples/decks/vanilla_probe.ydk", seed=18,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert {LAST_WILL, SANGAN, CANNON_SOLDIER} <= {
            card.code for card in observation.hand}
        cannon_summoned = sangan_summoned = will_activated = tributed = False
        order_choice_seen = False
        for _ in range(70):
            actions = env.legal_actions()

            def select(kind, code=None):
                return next((action for action in actions if action.kind == kind and (
                    code is None or action.parameters.get("code") == code)), None)

            if tributed and observation.chain and {
                    link.card_code for link in observation.chain} == {LAST_WILL, SANGAN}:
                assert order_choice_seen
                assert tuple(link.card_code for link in observation.chain) == (
                    LAST_WILL, SANGAN)
                return

            action = None
            if tributed and not order_choice_seen and {
                    LAST_WILL, SANGAN} <= {
                    candidate.parameters.get("code") for candidate in actions
                    if candidate.kind == "chain"}:
                order_choice_seen = True
                action = select("chain", LAST_WILL)
            if observation.turn == 1 and observation.acting_player == 0 and not cannon_summoned:
                action = select("normal_summon", CANNON_SOLDIER)
                cannon_summoned |= action is not None
            if observation.turn == 3 and observation.acting_player == 0:
                if not sangan_summoned:
                    action = select("normal_summon", SANGAN)
                    sangan_summoned |= action is not None
                if action is None and sangan_summoned and not will_activated:
                    action = select("activate", LAST_WILL)
                    will_activated |= action is not None
                if action is None and will_activated and not tributed:
                    action = select("activate", CANNON_SOLDIER)
                    tributed |= action is not None
            if action is None:
                action = (select("select_card", SANGAN) or select("place")
                          or select("select_position") or select("pass")
                          or select("end_phase") or actions[0])
            observation = env.step(action)
        pytest.fail("Last Will / Sangan trigger pair was not reached")
