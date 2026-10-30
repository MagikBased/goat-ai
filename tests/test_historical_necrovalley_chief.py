"""Gravekeeper's Chief exempts its controller from Necrovalley's GY lock."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

GRACEFUL = 79571449
PREMATURE = 70828912
CHIEF = 62473983
NECROVALLEY = 511002998
MYSTICAL_ELF = 15025844
MAD_DOG = 79182538
TRIBUTE = 23771716


def _deck(path: Path, cards: list[int]) -> str:
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_chief_allows_premature_revival_while_necrovalley_is_active(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (GRACEFUL, PREMATURE, CHIEF)}
    scripts.add(f"pre-errata/c{NECROVALLEY}.lua")
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required historical card scripts not installed")
    owner = _deck(tmp_path / "chief_owner.ydk",
                  [GRACEFUL, PREMATURE, CHIEF, *VANILLA_DECK[3:]])
    opponent = _deck(tmp_path / "necrovalley.ydk",
                     [NECROVALLEY, *VANILLA_DECK[1:]])

    with GoatEnvironment(owner, opponent, seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        assert {GRACEFUL, PREMATURE, CHIEF, MYSTICAL_ELF, MAD_DOG, TRIBUTE} <= {
            card.code for card in observation.hand}
        assert NECROVALLEY in {card.code for card in
                               env.engine.probe.observation(1).hand}
        graceful = discarded = tribute_summoned = valley = chief = premature = False
        target_chosen = False
        for _ in range(100):
            actions = env.legal_actions()

            def find(options, kind, code=None):
                return next((candidate for candidate in options
                             if candidate.kind == kind
                             and (code is None or candidate.parameters.get("code") == code)),
                            None)

            action = None
            if observation.turn == 1 and observation.acting_player == 0:
                if not graceful:
                    action = find(actions, "activate", GRACEFUL)
                    graceful |= action is not None
                if graceful and not discarded and action is None:
                    action = next((candidate for candidate in actions
                                   if candidate.kind == "select_cards"
                                   and {card["code"] for card in
                                        candidate.parameters["cards"]}
                                   == {MYSTICAL_ELF, MAD_DOG}), None)
                    discarded |= action is not None
                if discarded and not tribute_summoned and action is None:
                    action = find(actions, "normal_summon", TRIBUTE)
                    tribute_summoned |= action is not None
            if observation.turn == 2 and observation.acting_player == 1 and not valley:
                action = find(actions, "activate", NECROVALLEY)
                valley |= action is not None
            if observation.turn == 3 and observation.acting_player == 0:
                if not chief:
                    action = find(actions, "normal_summon", CHIEF)
                    chief |= action is not None
                if chief and not premature and action is None:
                    action = find(actions, "activate", PREMATURE)
                    if action is not None:
                        assert valley
                        assert MYSTICAL_ELF in {card.code for card in
                                                observation.graveyards[0]}
                        assert any(card.code == CHIEF and card.zone == "monster"
                                   for card in observation.field)
                        assert any(card.code == NECROVALLEY and card.position == "faceup"
                                   for card in observation.field)
                        premature = True
                if premature and not target_chosen and action is None:
                    action = next((candidate for candidate in actions
                                   if candidate.kind == "select_card"
                                   and candidate.parameters.get("code") == MYSTICAL_ELF
                                   and candidate.parameters.get("location") == 16), None)
                    target_chosen |= action is not None
            if action is None:
                action = next((candidate for candidate in actions
                               if candidate.kind in ("tribute", "place", "pass",
                                                     "end_phase")), actions[0])
            observation = env.step(action)
            if target_chosen and not observation.chain and any(
                    card.code == MYSTICAL_ELF and card.zone == "monster"
                    for card in observation.field):
                break
        else:
            pytest.fail("Chief/Necrovalley/Premature revival did not resolve")

        assert observation.life_points == (7200, 8000)
        assert {CHIEF, MYSTICAL_ELF} <= {card.code for card in observation.field
                                         if card.controller == 0 and card.zone == "monster"}
        assert PREMATURE in {card.code for card in observation.field
                             if card.controller == 0 and card.zone == "spell_trap"}
        assert NECROVALLEY in {card.code for card in observation.field
                               if card.controller == 1 and card.zone == "spell_trap"}
        assert scripts <= env.engine.probe.loaded_script_sha256.keys()

        agents = (RandomAgent(100), RandomAgent(101))
        for _ in range(3000):
            if env.is_terminal():
                break
            observation = env.step(agents[observation.acting_player].select_action(
                observation, env.legal_actions()))
        assert env.is_terminal()
        path = tmp_path / "chief_necrovalley.json"
        write_trajectory(path, env.trajectory())
        trajectory = read_trajectory(path)
        audit_trajectory_visibility(trajectory)
        assert verify_trajectory(trajectory, ExperimentalOcgcoreEngine(root)) \
            == len(trajectory.decisions)
