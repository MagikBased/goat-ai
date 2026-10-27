"""Competitive Set monsters must have identical Nobleman target views."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from scripts.audit_hidden_opening_pool import candidate_deck
from scripts.audit_hidden_set_pool import CardCannotBeSet, reach_next_main_phase

NOBLEMAN = 504700116
HIDDEN_MONSTERS = (
    31560081,  # Magician of Faith
    87621407,  # Dekoichi
    504700044,  # Gravekeeper's Spy (GOAT)
    504700038,  # Spirit Reaper (GOAT)
    88240808,  # Kycoo
    16226796,  # Night Assailant (GOAT)
)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
def test_common_set_monsters_have_identical_next_main_phase_choices(tmp_path):
    snapshots = []
    for code in HIDDEN_MONSTERS:
        opponent = tmp_path / f"set_monster_{code}.ydk"
        opponent.write_text("#main\n" + "\n".join(map(str, candidate_deck(code)))
                            + "\n#extra\n!side\n")
        opening, slot, next_main = reach_next_main_phase(
            Path("examples/decks/nobleman_probe.ydk"), opponent,
            Path(os.environ["GOAT_AI_NATIVE_ROOT"]), 52, code, "monster")
        assert slot == ("monster", 0)
        assert len(next_main[1]) > 1
        snapshots.append((opening, next_main))
    assert all(snapshot == snapshots[0] for snapshot in snapshots[1:])


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
@pytest.mark.parametrize("code", (504700118, 504700054))
def test_boss_or_tribute_monster_has_no_empty_field_set_action(tmp_path, code):
    opponent = tmp_path / f"no_set_{code}.ydk"
    opponent.write_text("#main\n" + "\n".join(map(str, candidate_deck(code)))
                        + "\n#extra\n!side\n")
    with pytest.raises(CardCannotBeSet, match=str(code)):
        reach_next_main_phase(Path("examples/decks/nobleman_probe.ydk"), opponent,
                              Path(os.environ["GOAT_AI_NATIVE_ROOT"]), 52, code,
                              "monster")


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"),
                    reason="native assets not installed")
def test_common_hidden_monsters_do_not_change_nobleman_target_choice(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    if not (root / f"scripts/goat/c{NOBLEMAN}.lua").is_file():
        pytest.skip("GOAT Nobleman script not installed")

    snapshots = []
    for hidden_code in HIDDEN_MONSTERS:
        opponent = tmp_path / f"hidden_{hidden_code}.ydk"
        opponent.write_text(
            "#main\n" + "\n".join(map(str, (hidden_code, *VANILLA_DECK[1:])))
            + "\n#extra\n!side\n")
        with GoatEnvironment("examples/decks/nobleman_probe.ydk", str(opponent),
                             seed=52, engine=ExperimentalOcgcoreEngine(root)) as env:
            obs = env.reset()
            assert hidden_code in {card.code for card in
                                   env.engine.probe.observation(1).hand}
            set_done = activated = False
            for _ in range(60):
                actions = env.legal_actions()
                action = None
                if obs.turn == 2 and obs.acting_player == 1 and not set_done:
                    action = next((a for a in actions if a.kind == "set_monster"
                                   and a.parameters.get("code") == hidden_code), None)
                    set_done |= action is not None
                if obs.turn == 3 and obs.acting_player == 0 and set_done:
                    if not activated:
                        action = next((a for a in actions if a.kind == "activate"
                                       and a.parameters.get("code") == NOBLEMAN), None)
                        activated |= action is not None
                    elif actions[0].kind == "select_card":
                        assert obs.viewer == obs.acting_player == 0
                        assert obs.known_opponent_field_cards == ()
                        assert obs.private_reveals == ()
                        assert len(actions) == 1
                        assert actions[0].parameters == {
                            "location": 4, "sequence": 0, "controller": 1}
                        assert any(card.controller == 1 and card.zone == "monster"
                                   and card.position == "facedown" and card.code is None
                                   for card in obs.field)
                        assert env.engine.probe._query_location(1, 4)[0].code == hidden_code
                        snapshots.append((obs, actions))
                        break
                if action is None:
                    action = next((a for a in actions if a.kind in ("pass", "end_phase")),
                                  actions[0])
                obs = env.step(action)
            else:
                pytest.fail(f"Nobleman target was not reached for {hidden_code}")

    assert len(snapshots) == len(HIDDEN_MONSTERS)
    assert all(snapshot == snapshots[0] for snapshot in snapshots[1:])
