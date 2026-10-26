"""Play preferences must use only the player-visible action contract."""

from dataclasses import replace

from goat_ai.actions import Action
from goat_ai.agents.tactical_guard import admissible_action_indices
from goat_ai.observations import CardView, ChainLinkView, Observation


def board(*cards, phase="main1", turn=1, viewer=0, chain=(), turn_player=None):
    return Observation(
        viewer=viewer, acting_player=viewer, turn=turn, phase=phase,
        life_points=(8000, 8000), hand=(), field=tuple(cards),
        graveyards=((), ()), banished=((), ()), opponent_hand_count=5,
        deck_counts=(35, 35), extra_deck_counts=(0, 0), chain=chain,
        turn_player=turn_player,
    )


def kept(observation, actions):
    return tuple(actions[i] for i in admissible_action_indices(observation, actions))


def test_heavy_storm_avoids_solely_damaging_own_backrow():
    storm = Action("storm", "activate", 0, {"code": 19613556})
    wait = Action("wait", "end_phase", 0)
    own_set = CardView(0, "spell_trap", "facedown", 45986603, 0)
    opponent_set = CardView(1, "spell_trap", "facedown", None, 0)
    assert kept(board(own_set), (storm, wait)) == (wait,)
    assert kept(board(own_set, opponent_set), (storm, wait)) == (storm, wait)
    assert kept(board(), (storm, wait)) == (storm, wait)
    # The rule cannot examine the unknown identity of the opponent's Set card.
    assert kept(board(own_set, opponent_set), (storm, wait)) == kept(
        board(own_set, replace(opponent_set, sequence=0)), (storm, wait))


def test_scapegoat_waits_for_end_or_battle_and_can_answer_removal():
    goat = Action("goat", "chain", 0, {"code": 504700123})
    decline = Action("pass", "pass", 0)
    assert kept(board(phase="draw"), (goat, decline)) == (decline,)
    assert kept(board(phase="main1"), (goat, decline)) == (decline,)
    assert kept(board(phase="end"), (goat, decline)) == (goat, decline)
    assert kept(board(phase="battle_start"), (goat, decline)) == (goat, decline)
    assert kept(board(phase="end", turn_player=0), (goat, decline)) == (decline,)
    assert kept(board(phase="end", turn_player=1), (goat, decline)) == (
        goat, decline)
    assert kept(board(phase="battle_start", turn_player=0),
                (goat, decline)) == (decline,)
    assert kept(board(phase="battle_start", turn_player=1),
                (goat, decline)) == (goat, decline)
    harmless = (ChainLinkView(1, 72302403, 1, 8, 0),)
    assert kept(board(phase="main1", chain=harmless), (goat, decline)) == (decline,)
    pending = (ChainLinkView(1, 19613556, 1, 8, 0),)
    assert kept(board(phase="main1", chain=pending), (goat, decline)) == (
        goat, decline)
    own_main = Action("goat", "activate", 0, {"code": 504700123})
    assert kept(board(phase="main1"), (own_main, decline)) == (decline,)
    set_goat = Action("set", "set_spell_trap", 0, {"code": 504700123})
    end = Action("end", "end_phase", 0)
    assert kept(board(phase="main1"), (own_main, set_goat, end)) == (set_goat, end)


def test_guard_never_eliminates_every_legal_action():
    goat = Action("goat", "chain", 0, {"code": 504700123})
    assert kept(board(phase="draw"), (goat,)) == (goat,)


def test_tribe_requires_visible_enemy_and_names_the_best_race():
    tribe_code = 33184167
    races = {504700044: 2, 32362575: 2048, 17881964: 8192, tribe_code: 64}
    own = CardView(0, "monster", "faceup", 504700044, 0, "attack", 1200, 2000)
    weak_enemy = CardView(1, "monster", "faceup", 32362575, 0,
                          "attack", 200, 700)
    strong_enemy = CardView(1, "monster", "faceup", 17881964, 1,
                            "attack", 1500, 1300)
    activate = Action("tribe", "chain", 0, {"code": tribe_code})
    decline = Action("decline", "pass", 0)
    assert tuple((activate, decline)[i] for i in admissible_action_indices(
        board(own), (activate, decline), races)) == (decline,)
    chain = (ChainLinkView(1, tribe_code, 0, 4, 0),)
    options = tuple(Action(str(race), "announce_race", 0, {"race": race})
                    for race in (2, 2048, 8192))
    observed = board(own, own, weak_enemy, strong_enemy, chain=chain)
    assert tuple(options[i] for i in admissible_action_indices(
        observed, options, races)) == (options[2],)


def test_breaker_targets_opponent_backrow_and_controller_waits_until_needed():
    breaker = (ChainLinkView(1, 71413901, 0, 4, 0),)
    own = Action("own", "select_card", 0, {"location": 8, "controller": 0,
                                            "sequence": 0, "code": 38275183})
    enemy = Action("enemy", "select_card", 0, {"location": 8, "controller": 1,
                                                "sequence": 0})
    assert kept(board(chain=breaker), (own, enemy)) == (enemy,)
    controller = Action("controller", "chain", 0, {"code": 98045062})
    decline = Action("decline", "pass", 0)
    assert kept(board(phase="draw"), (controller, decline)) == (decline,)
    assert kept(board(phase="battle_start"), (controller, decline)) == (
        controller, decline)
