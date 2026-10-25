"""MST destroys an activated Mirror Force without negating its attack response."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

MIRROR_FORCE = 44095762
MYSTICAL_SPACE_TYPHOON = 5318639


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_mst_chained_to_mirror_force_does_not_save_attacker(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (MIRROR_FORCE, MYSTICAL_SPACE_TYPHOON)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required official card script not installed")
    decks = []
    for name, code in (("attacker", MYSTICAL_SPACE_TYPHOON),
                       ("defender", MIRROR_FORCE)):
        deck = tmp_path / f"{name}.ydk"
        deck.write_text("#main\n" + "\n".join(map(str, (
            code, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")
        decks.append(deck)

    with GoatEnvironment(*(str(deck) for deck in decks), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        summoned = set_mirror = attacked = chained_mirror = chained_mst = targeted = False
        attacker_code = None
        for _ in range(70):
            actions = env.legal_actions()
            action = None
            if observation.turn == 1 and observation.acting_player == 0 and not summoned:
                action = next((a for a in actions if a.kind == "normal_summon"), None)
                if action is not None:
                    summoned = True
                    attacker_code = action.parameters["code"]
            if observation.turn == 2 and observation.acting_player == 1 and not set_mirror:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == MIRROR_FORCE), action)
                set_mirror |= action is not None and action.kind == "set_spell_trap"
            if observation.turn == 3 and observation.acting_player == 0 and not attacked:
                action = next((a for a in actions if a.kind in ("battle_phase", "attack")
                               and (a.kind != "attack"
                                    or a.parameters.get("code") == attacker_code)), action)
                attacked |= action is not None and action.kind == "attack"
            if attacked and observation.acting_player == 1 and not chained_mirror:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == MIRROR_FORCE), action)
                chained_mirror |= action is not None and action.kind == "chain"
                if chained_mirror:
                    assert observation.phase == "battle_step"
            if chained_mirror and observation.acting_player == 0 and not chained_mst:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == MYSTICAL_SPACE_TYPHOON),
                              action)
                chained_mst |= action is not None and action.kind == "chain"
                if chained_mst:
                    assert [link.card_code for link in observation.chain] == [MIRROR_FORCE]
            if chained_mst and not targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("controller") == 1
                               and a.parameters.get("location") == 8), action)
                targeted |= action is not None and action.kind == "select_card"
                if targeted:
                    assert action.parameters.get("code") == MIRROR_FORCE
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "place", "select_position", "pass", "end_phase")), actions[0])
            observation = env.step(action)
            if targeted and {MIRROR_FORCE, MYSTICAL_SPACE_TYPHOON}.issubset(
                    {card.code for pile in observation.graveyards for card in pile}
            ) and not observation.chain:
                assert summoned and set_mirror and attacked and chained_mirror and chained_mst
                assert any(card.code == attacker_code for card in observation.graveyards[0])
                assert not any(card.controller == 0 and card.zone == "monster"
                               for card in observation.field)
                assert observation.life_points == (8000, 8000)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                return
    pytest.fail("MST / Mirror Force chain did not resolve")
