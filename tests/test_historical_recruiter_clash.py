"""Simultaneous battle recruiters from both players after an equal-ATK clash."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

ANGEL = 504700170
TOMATO = 504700142
WARRIOR_LADY = 7572887
SANGAN = 504700178


def _deck(path, cards):
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_angel_and_tomato_both_recruit_after_equal_attack_battle(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"goat/c{code}.lua" for code in (ANGEL, TOMATO, SANGAN)}
    scripts.add(f"official/c{WARRIOR_LADY}.lua")
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required scripts not installed")
    angel_deck = _deck(tmp_path / "angel.ydk", (
        *([ANGEL] * 3), WARRIOR_LADY, *VANILLA_DECK[4:]))
    tomato_deck = _deck(tmp_path / "tomato.ydk", (
        *([TOMATO] * 3), SANGAN, *VANILLA_DECK[4:]))

    with GoatEnvironment(angel_deck, tomato_deck, seed=11,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert ANGEL in {c.code for c in obs.hand}
        assert TOMATO in {c.code for c in env.engine.probe.observation(1).hand}
        angel_summoned = tomato_summoned = battle = attacked = targeted = False
        accepted = set()
        selected = set()
        search_order = []
        before = None
        for _ in range(80):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not angel_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == ANGEL), None)
                angel_summoned |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not tomato_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == TOMATO), None)
                tomato_summoned |= action is not None
            if (obs.turn == 3 and obs.acting_player == 0 and obs.phase == "main1"
                    and not battle):
                action = next((a for a in actions if a.kind == "battle_phase"), None)
                battle |= action is not None
            if (battle and obs.turn == 3 and obs.acting_player == 0
                    and obs.phase == "battle_start" and not attacked):
                action = next((a for a in actions if a.kind == "attack"
                               and a.parameters.get("code") == ANGEL), None)
                attacked |= action is not None
            if attacked and not targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == TOMATO
                               and a.parameters.get("controller") == 1), None)
                targeted |= action is not None
            if targeted and before is None and all(
                    code in {c.code for c in obs.graveyards[player]}
                    for player, code in ((0, ANGEL), (1, TOMATO))):
                before = obs.deck_counts
                assert obs.life_points == (8000, 8000)
                assert obs.phase == "damage_step"
            if targeted and any(a.kind == "yes" for a in actions) \
                    and obs.acting_player not in accepted:
                assert obs.phase == "damage_step"
                assert obs.acting_player == obs.viewer
                action = next(a for a in actions if a.kind == "yes")
                accepted.add(obs.acting_player)
            if accepted == {0} and obs.acting_player == 1:
                tomato_chain = next((a for a in actions if a.kind == "chain"
                                     and a.parameters.get("code") == TOMATO), None)
                if tomato_chain is not None:
                    assert [link.card_code for link in obs.chain] == [ANGEL]
                    action = tomato_chain
                    accepted.add(1)
            if accepted and actions[0].kind == "select_card" \
                    and actions[0].parameters.get("location") == 1 \
                    and obs.acting_player not in selected:
                assert [link.card_code for link in obs.chain] == [ANGEL, TOMATO]
                code = WARRIOR_LADY if obs.acting_player == 0 else SANGAN
                action = next((a for a in actions if a.parameters.get("code") == code), None)
                assert action is not None
                assert "sequence" not in action.parameters
                selected.add(obs.acting_player)
                search_order.append(obs.acting_player)
            if selected == {0, 1} and obs.phase == "battle_step":
                assert search_order == [1, 0]
                assert obs.deck_counts == (before[0] - 1, before[1] - 1)
                assert {(c.controller, c.code) for c in obs.field
                        if c.zone == "monster"} == {(0, WARRIOR_LADY), (1, SANGAN)}
                assert obs.life_points == (8000, 8000)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                return
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
    pytest.fail(f"recruiter clash stalled: accepted={accepted}, selected={selected}, "
                f"turn={obs.turn}, phase={obs.phase}")
