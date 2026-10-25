"""Nobleman's target decision must not disclose a hidden Flip identity."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

NOBLEMAN = 504700116
DEKOICHI = 87621407
VANILLA = VANILLA_DECK[0]


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_nobleman_target_observation_is_identical_for_hidden_flip_or_normal(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{NOBLEMAN}.lua", f"official/c{DEKOICHI}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")

    def run(hidden_code):
        opponent = tmp_path / f"hidden_{hidden_code}.ydk"
        opponent.write_text("#main\n" + "\n".join(map(str, (
            hidden_code, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
        with GoatEnvironment("examples/decks/nobleman_probe.ydk", str(opponent), seed=52,
                             engine=ExperimentalOcgcoreEngine(root)) as env:
            obs = env.reset()
            assert hidden_code in {c.code for c in env.engine.probe.observation(1).hand}
            set_done = activated = targeted = False
            decision = resolution = None
            for _ in range(55):
                actions = env.legal_actions()
                action = None
                if obs.turn == 2 and obs.acting_player == 1 and not set_done:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == hidden_code), None)
                    set_done |= action is not None
                if obs.turn == 3 and obs.acting_player == 0 and not activated:
                    action = next((a for a in actions if a.kind == "activate"
                                   and a.parameters.get("code") == NOBLEMAN), None)
                    activated |= action is not None
                if activated and not targeted and actions[0].kind == "select_card":
                    assert obs.viewer == obs.acting_player == 0
                    assert obs.known_opponent_field_cards == ()
                    assert not obs.private_reveals
                    assert all("code" not in a.parameters for a in actions)
                    decision = (obs, actions)
                    action = actions[0]
                    targeted = True
                if action is None:
                    action = next((a for a in actions if a.kind in ("pass", "end_phase")),
                                  actions[0])
                obs = env.step(action)
                if targeted and hidden_code in {c.code for c in obs.banished[1]}:
                    resolution = obs
                    break
            assert set_done and activated and targeted and resolution is not None
            assert decision is not None
            assert f"goat/c{NOBLEMAN}.lua" in env.engine.probe.loaded_script_sha256
            return decision, resolution

    (flip_obs, flip_actions), flip_resolved = run(DEKOICHI)
    (normal_obs, normal_actions), normal_resolved = run(VANILLA)
    assert flip_obs == normal_obs
    assert flip_actions == normal_actions
    assert any(c.code == DEKOICHI for c in flip_resolved.banished[1])
    assert any(c.code == VANILLA for c in normal_resolved.banished[1])
    assert flip_resolved.private_reveals
    assert not normal_resolved.private_reveals
