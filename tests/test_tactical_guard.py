"""Play preferences must use only the player-visible action contract."""

from dataclasses import replace

from goat_ai.actions import Action
from goat_ai.agents import TacticalHeuristicAgent
from goat_ai.agents.tactical_guard import (
    admissible_action_indices,
    safe_position_indices,
    safe_target_indices,
    weak_flip_set_substitute,
)
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


def test_position_guard_avoids_empty_field_attack_defense_oscillation():
    attacker = CardView(0, "monster", "faceup", 87621407, 2,
                        "attack", 1400, 1000)
    defender = replace(attacker, orientation="defense")
    switch = Action("switch", "change_position", 0,
                    {"controller": 0, "location": 4, "sequence": 2,
                     "code": 87621407})
    end = Action("end", "end_phase", 0)
    assert safe_position_indices(board(attacker), (switch, end), range(2)) == (1,)
    assert safe_position_indices(board(defender), (switch, end), range(2)) == (0, 1)
    assert safe_position_indices(board(attacker), (switch,), range(1)) == (0,)
    enemy = CardView(1, "monster", "facedown", None, 0, "defense")
    assert safe_position_indices(board(attacker, enemy), (switch, end), range(2)) == (0, 1)
    weaker_attacker = replace(attacker, attack=1000, defense=1400)
    assert safe_position_indices(board(weaker_attacker), (switch, end), range(2)) == (0, 1)
    agent = TacticalHeuristicAgent()
    assert agent.select_action(board(attacker), (switch, end)) == end
    assert agent.select_action(board(defender), (switch, end)) == switch


def test_optional_self_target_guard_uses_public_source_and_target_slots():
    bls = 504700118
    mst = 5318639
    own_bls = Action("bls", "select_card", 0,
                     {"code": bls, "controller": 0, "location": 4, "sequence": 0})
    own_other = Action("other", "select_card", 0,
                       {"code": 123, "controller": 0, "location": 4, "sequence": 1})
    unknown_enemy = Action("enemy", "select_card", 0,
                           {"controller": 1, "location": 4, "sequence": 0})
    actions = (own_bls, own_other, unknown_enemy)
    snapshot = board(chain=(ChainLinkView(1, bls, 0, 4, 0),))
    assert safe_target_indices(snapshot, actions, range(3)) == (2,)
    assert safe_target_indices(snapshot, actions[:2], range(2)) == (0, 1)
    assert safe_target_indices(board(chain=(ChainLinkView(1, bls, 1, 4, 0),)),
                               actions, range(3)) == (0, 1, 2)
    own_spell = Action("own-spell", "select_card", 0,
                       {"code": 41420027, "controller": 0,
                        "location": 8, "sequence": 2})
    enemy_spell = Action("enemy-spell", "select_card", 0,
                         {"controller": 1, "location": 8, "sequence": 1})
    spell_actions = (own_spell, enemy_spell)
    assert safe_target_indices(board(chain=(ChainLinkView(1, mst, 0, 8, 0),)),
                               spell_actions, range(2)) == (1,)
    # The opponent's hidden identity is unavailable in both observations.
    assert safe_target_indices(board(chain=(ChainLinkView(1, mst, 0, 8, 0),)),
                               spell_actions[:1], range(1)) == (0,)


def test_optional_weak_flip_guard_prefers_set_except_visible_direct_lethal():
    faith = 31560081
    summon = Action("summon", "normal_summon", 0, {"code": faith})
    set_faith = Action("set", "set_monster", 0, {"code": faith})
    actions = (summon, set_faith)
    weak = {faith: 300}
    assert kept(board(), actions) == actions  # Existing guard v3 stays unchanged.
    assert weak_flip_set_substitute(board(), actions, summon, weak) == set_faith
    opponent = CardView(1, "monster", "facedown", None, 0, "defense")
    assert weak_flip_set_substitute(board(opponent), actions, summon, weak) == set_faith
    lethal = replace(board(), life_points=(8000, 300))
    battle = Action("battle", "battle_phase", 0)
    assert weak_flip_set_substitute(lethal, (*actions, battle), summon, weak) is None
    assert weak_flip_set_substitute(replace(lethal, phase="main2"),
                                    (*actions, battle), summon, weak) == set_faith
    assert weak_flip_set_substitute(board(opponent), (summon,), summon, weak) is None


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


def test_v8_tribe_defers_discard_when_all_visible_type_trades_lose():
    tribe = 33184167
    enemy = CardView(1, "monster", "faceup", 25262697, 0,
                     "attack", 2000, 2000, race=2)
    own_a = CardView(0, "monster", "faceup", 504700102, 0,
                     "attack", 0, 0, race=2)
    own_b = CardView(0, "monster", "faceup", 504700044, 1,
                     "attack", 1700, 2500, race=2)
    own_tribe = CardView(0, "monster", "faceup", tribe, 2,
                         "attack", 1600, 1000, race=64)
    activate = Action("tribe", "activate", 0, {"code": tribe})
    end = Action("end", "end_phase", 0)
    actions = (activate, end)
    snapshot = board(enemy, own_a, own_b, own_tribe)
    assert admissible_action_indices(snapshot, actions) == (0, 1)
    assert admissible_action_indices(snapshot, actions,
                                     tactical_v8_guards=True) == (1,)
    assert TacticalHeuristicAgent().select_action(snapshot, actions) == end
    assert TacticalHeuristicAgent(v8_guards=False).select_action(
        snapshot, actions) == activate
    profitable = board(enemy, replace(enemy, sequence=1), own_a, own_tribe)
    assert admissible_action_indices(profitable, actions,
                                     tactical_v8_guards=True) == (0, 1)


def test_v8_prefers_recoverable_serpent_for_duo_discard():
    chain = (ChainLinkView(1, 44763025, 1, 8, 0),)
    snatch = Action("snatch", "select_card", 0,
                    {"code": 45986603, "controller": 0, "location": 2})
    serpent = Action("serpent", "select_card", 0,
                      {"code": 511000818, "controller": 0, "location": 2})
    snapshot = board(chain=chain)
    assert TacticalHeuristicAgent().select_action(snapshot, (snatch, serpent)) == serpent
    assert TacticalHeuristicAgent(v8_guards=False).select_action(
        snapshot, (snatch, serpent)) == snatch


def test_v8_thunder_search_takes_available_copies():
    chain = (ChainLinkView(1, 504700054, 0, 2, 0),)
    cancel = Action("cancel", "cancel", 0)
    empty = Action("empty", "select_cards", 0)
    two = Action("two", "select_cards", 0,
                 {"cards": [{"code": 504700054}, {"code": 504700054}]})
    snapshot = board(chain=chain)
    assert TacticalHeuristicAgent().select_action(snapshot, (cancel, empty, two)) == two
    assert TacticalHeuristicAgent(v8_guards=False).select_action(
        snapshot, (cancel, empty, two)) == cancel


def test_v8_nobleman_defers_own_only_target_and_prefers_enemy_slot():
    nobleman = 504700116
    own_set = CardView(0, "monster", "facedown", 511000818, 0, "defense")
    enemy_set = CardView(1, "monster", "facedown", None, 1, "defense")
    activate = Action("nobleman", "activate", 0, {"code": nobleman})
    end = Action("end", "end_phase", 0)
    assert TacticalHeuristicAgent().select_action(
        board(own_set), (activate, end)) == end
    assert TacticalHeuristicAgent(v8_guards=False).select_action(
        board(own_set), (activate, end)) == activate
    own = Action("own", "select_card", 0,
                 {"controller": 0, "location": 4, "sequence": 0})
    enemy = Action("enemy", "select_card", 0,
                   {"controller": 1, "location": 4, "sequence": 1})
    snapshot = board(own_set, enemy_set,
                     chain=(ChainLinkView(1, nobleman, 0, 8, 0),))
    assert TacticalHeuristicAgent().select_action(snapshot, (own, enemy)) == enemy


def test_v8_defers_dust_tornado_chain_to_book_of_moon():
    dust = Action("dust", "chain", 0, {"code": 60082869})
    decline = Action("decline", "pass", 0)
    snapshot = board(chain=(ChainLinkView(1, 14087893, 1, 8, 0),))
    assert TacticalHeuristicAgent().select_action(snapshot, (dust, decline)) == decline
    assert TacticalHeuristicAgent(v8_guards=False).select_action(
        snapshot, (dust, decline)) == dust


def test_v8_saves_serpent_normal_summon_when_another_monster_is_available():
    serpent = Action("serpent", "normal_summon", 0, {"code": 511000818})
    assailant = Action("assailant", "normal_summon", 0, {"code": 70074904})
    actions = (serpent, assailant)
    assert TacticalHeuristicAgent().select_action(board(), actions) == assailant
    assert TacticalHeuristicAgent(v8_guards=False).select_action(
        board(), actions) == serpent


def test_v9_holds_thunder_when_all_initial_copies_are_known_outside_deck():
    thunder = 504700054
    activate = Action("thunder", "chain", 0, {"code": thunder})
    decline = Action("decline", "pass", 0)
    view = replace(board(), own_main_deck=(thunder,) * 3,
                   hand=(CardView(0, "hand", "hidden", thunder),),
                   graveyards=((CardView(0, "graveyard", "faceup", thunder),
                                CardView(0, "graveyard", "faceup", thunder)), ()))
    assert TacticalHeuristicAgent().select_action(view, (activate, decline)) == decline
    assert TacticalHeuristicAgent(v9_guards=False).select_action(
        view, (activate, decline)) == activate
    one_left = replace(view, graveyards=((view.graveyards[0][0],), ()))
    assert TacticalHeuristicAgent().select_action(
        one_left, (activate, decline)) == activate


def test_v9_defers_weak_vanilla_metamorphosis_but_keeps_effect_fusion():
    newdoria = CardView(0, "monster", "faceup", 4335645, 0,
                        "attack", 1200, 800)
    darkfire = CardView(0, "extra", "facedown", 17881964)
    restrict = CardView(0, "extra", "facedown", 504700102)
    metamorphosis = Action("meta", "activate", 0, {"code": 46411259})
    end = Action("end", "end_phase", 0)
    facts = {4335645: (33, 4, 1200), 17881964: (65, 4, 1500),
             73915052: (16401, 1, 0), 504700102: (97, 1, 0)}
    weak = replace(board(newdoria), own_extra_deck=(darkfire, restrict))
    assert TacticalHeuristicAgent(card_facts=facts).select_action(
        weak, (metamorphosis, end)) == end
    assert TacticalHeuristicAgent(card_facts=facts, v9_guards=False).select_action(
        weak, (metamorphosis, end)) == metamorphosis
    sheep = CardView(0, "monster", "faceup", 73915052, 1,
                     "defense", 0, 0)
    assert TacticalHeuristicAgent(card_facts=facts).select_action(
        replace(weak, field=(newdoria, sheep)), (metamorphosis, end)) == metamorphosis


def test_v9_preserves_breaker_counter_and_removal_when_only_own_cards_are_targets():
    breaker = Action("breaker", "chain", 0, {"code": 71413901})
    decline = Action("decline", "pass", 0)
    own_backrow = CardView(0, "spell_trap", "facedown", 19613556, 0)
    assert TacticalHeuristicAgent().select_action(
        board(own_backrow), (breaker, decline)) == decline
    enemy_backrow = CardView(1, "spell_trap", "facedown", None, 0)
    assert TacticalHeuristicAgent().select_action(
        board(own_backrow, enemy_backrow), (breaker, decline)) == breaker
    own = Action("own", "select_card", 0,
                 {"controller": 0, "location": 8, "sequence": 0})
    enemy = Action("enemy", "select_card", 0,
                   {"controller": 1, "location": 8, "sequence": 0})
    target_view = board(own_backrow, enemy_backrow,
                        chain=(ChainLinkView(1, 71413901, 0, 4, 0),))
    assert safe_target_indices(target_view, (own, enemy), range(2),
                               protect_removal_targets=True) == (1,)


def test_v9_saves_book_and_raigeki_break_during_own_draw_phase():
    breaker = CardView(1, "monster", "faceup", 71413901, 0,
                       "attack", 1900, 1000)
    book = Action("book", "chain", 0, {"code": 14087893})
    break_card = Action("break", "chain", 0, {"code": 4178474})
    decline = Action("decline", "pass", 0)
    view = board(breaker, phase="draw", turn_player=0)
    for action in (book, break_card):
        assert TacticalHeuristicAgent().select_action(view, (action, decline)) == decline
        assert TacticalHeuristicAgent(v9_guards=False).select_action(
            view, (action, decline)) == action


def test_v9_prefers_opponent_for_chaos_and_raigeki_removal_targets():
    own = Action("own", "select_card", 0,
                 {"controller": 0, "location": 4, "sequence": 0})
    enemy = Action("enemy", "select_card", 0,
                   {"controller": 1, "location": 4, "sequence": 0})
    for source in (9596126, 4178474):
        snapshot = board(chain=(ChainLinkView(1, source, 0, 4, 0),))
        assert safe_target_indices(snapshot, (own, enemy), range(2),
                                   protect_removal_targets=True) == (1,)
        assert TacticalHeuristicAgent().select_action(snapshot, (own, enemy)) == enemy
    assert safe_target_indices(snapshot, (own,), range(1),
                               protect_removal_targets=True) == (0,)


def test_v9_defers_own_only_chaos_and_bls_banish_activation():
    own = CardView(0, "monster", "faceup", 9596126, 0,
                   "attack", 2300, 2000)
    enemy = CardView(1, "monster", "faceup", 17881964, 0,
                     "attack", 1500, 1250)
    decline = Action("decline", "pass", 0)
    for code in (9596126, 504700118):
        activate = Action("banish", "chain", 0,
                          {"code": code, "controller": 0, "sequence": 0})
        assert TacticalHeuristicAgent().select_action(
            board(replace(own, code=code)), (activate, decline)) == decline
        assert TacticalHeuristicAgent().select_action(
            board(replace(own, code=code), enemy), (activate, decline)) == activate


def test_v10_main_phase_open_actions_do_not_require_a_pass_option():
    own_chaos = CardView(0, "monster", "faceup", 9596126, 0,
                         "attack", 2300, 2000)
    own_trap = CardView(0, "spell_trap", "facedown", 511000824, 0)
    own_breaker = CardView(0, "monster", "faceup", 71413901, 1,
                           "attack", 1900, 1000)
    end = Action("end", "end_phase", 0)
    for code, cards in ((9596126, (own_chaos,)),
                        (71413901, (own_breaker, own_trap))):
        activate = Action("activate", "activate", 0,
                          {"code": code, "controller": 0, "sequence": 0})
        actions = (activate, end)
        view = board(*cards, turn_player=0)
        assert TacticalHeuristicAgent().select_action(view, actions) == end
        assert TacticalHeuristicAgent(v10_guards=False).select_action(
            view, actions) == activate


def test_v10_book_waits_when_own_main_phase_has_no_monster():
    enemy = CardView(1, "monster", "faceup", 4335645, 0,
                     "attack", 1200, 800)
    book = Action("book", "chain", 0,
                  {"code": 14087893, "location": 2, "controller": 0})
    decline = Action("decline", "pass", 0)
    view = board(enemy, turn_player=0)
    assert TacticalHeuristicAgent().select_action(view, (book, decline)) == decline
    assert TacticalHeuristicAgent(v10_guards=False).select_action(
        view, (book, decline)) == book
    assert TacticalHeuristicAgent().select_action(
        board(enemy, turn_player=1), (book, decline)) == book
    open_book = Action("open-book", "activate", 0,
                       {"code": 14087893, "location": 2, "controller": 0})
    end = Action("end", "end_phase", 0)
    assert TacticalHeuristicAgent().select_action(
        view, (open_book, end)) == end
    assert TacticalHeuristicAgent(v10_guards=False).select_action(
        view, (open_book, end)) == open_book
    own_chaos = CardView(0, "monster", "faceup", 9596126, 0,
                         "attack", 2300, 2000)
    assert TacticalHeuristicAgent().select_action(
        board(own_chaos, enemy, turn_player=0), (book, decline)) == decline
    restrict = replace(enemy, code=504700102, attack=0, defense=0)
    assert TacticalHeuristicAgent().select_action(
        board(own_chaos, restrict, turn_player=0), (book, decline)) == book
    own_effect = board(own_chaos, enemy, turn_player=0,
                       chain=(ChainLinkView(1, 9596126, 0, 4, 0),))
    assert TacticalHeuristicAgent().select_action(
        own_effect, (book, decline)) == decline
    assert TacticalHeuristicAgent(v10_guards=False).select_action(
        own_effect, (book, decline)) == book


def test_v10_position_changes_need_visible_combat_value():
    attacker = CardView(0, "monster", "faceup", 71413901, 0,
                        "attack", 1900, 1000)
    enemy = CardView(1, "monster", "faceup", 25262697, 0,
                     "attack", 2000, 2000)
    switch = Action("switch", "change_position", 0,
                    {"controller": 0, "sequence": 0, "code": 71413901})
    end = Action("end", "end_phase", 0)
    assert TacticalHeuristicAgent().select_action(
        board(attacker, enemy), (switch, end)) == end
    assert TacticalHeuristicAgent(v10_guards=False).select_action(
        board(attacker, enemy), (switch, end)) == switch
    defender = replace(attacker, orientation="defense")
    assert TacticalHeuristicAgent().select_action(
        board(defender, enemy), (switch, end)) == end
    weaker_enemy = replace(enemy, attack=1200)
    assert TacticalHeuristicAgent().select_action(
        board(defender, weaker_enemy), (switch, end)) == switch


def test_v9_creature_swap_prefers_token_and_tsukuyomi_resets_equipped_restrict():
    jinzo = CardView(0, "monster", "faceup", 77585513, 0,
                     "attack", 2400, 1500)
    sheep = CardView(0, "monster", "faceup", 73915052, 1,
                     "defense", 0, 0)
    own_jinzo = Action("jinzo", "select_card", 0,
                       {"code": 77585513, "controller": 0,
                        "location": 4, "sequence": 0})
    own_sheep = Action("sheep", "select_card", 0,
                       {"code": 73915052, "controller": 0,
                        "location": 4, "sequence": 1})
    swap = board(jinzo, sheep, chain=(ChainLinkView(1, 31036355, 0, 8, 0),))
    assert TacticalHeuristicAgent().select_action(swap,
                                                  (own_jinzo, own_sheep)) == own_sheep
    restrict = CardView(0, "monster", "faceup", 504700102, 1,
                        "attack", 0, 0)
    tsukuyomi = CardView(0, "monster", "faceup", 34853266, 0,
                         "attack", 1100, 1400)
    equipped = CardView(0, "spell_trap", "facedown", 16226796, 0,
                        equipped_to=(0, 1))
    self_target = Action("self", "select_card", 0,
                         {"controller": 0, "location": 4, "sequence": 0})
    restrict_target = Action("restrict", "select_card", 0,
                             {"controller": 0, "location": 4, "sequence": 1})
    view = board(tsukuyomi, restrict, equipped,
                 chain=(ChainLinkView(1, 34853266, 0, 4, 0),))
    assert TacticalHeuristicAgent().select_action(
        view, (self_target, restrict_target)) == restrict_target


def test_tribe_uses_current_public_type_after_a_field_type_change():
    tribe_code = 33184167
    own = CardView(0, "monster", "faceup", 504700044, 0, "attack",
                   1200, 2000, race=64)
    enemy = CardView(1, "monster", "faceup", 17881964, 0, "attack",
                     1500, 1300, race=2)
    printed = {504700044: 2, 17881964: 8192}
    chain = (ChainLinkView(1, tribe_code, 0, 4, 1),)
    options = tuple(Action(str(race), "announce_race", 0, {"race": race})
                    for race in (64, 8192, 2))
    observed = board(own, enemy, chain=chain)
    assert tuple(options[i] for i in admissible_action_indices(
        observed, options, printed)) == (options[2],)


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


def test_sakuretsu_waits_while_royal_decree_is_face_up():
    sakuretsu = Action("sakuretsu", "chain", 0, {"code": 56120475})
    goat = Action("goat", "chain", 0, {"code": 504700123})
    decline = Action("pass", "pass", 0)
    own_decree = CardView(0, "spell_trap", "faceup", 51452091, 0)
    opponent_decree = replace(own_decree, controller=1)
    set_decree = replace(own_decree, position="facedown")
    actions = (sakuretsu, goat, decline)

    for decree in (own_decree, opponent_decree):
        assert kept(board(decree, phase="battle_step", turn_player=1), actions) == (
            goat, decline)
    assert kept(board(set_decree, phase="battle_step", turn_player=1), actions) == actions
    assert kept(board(phase="battle_step", turn_player=1), actions) == actions
