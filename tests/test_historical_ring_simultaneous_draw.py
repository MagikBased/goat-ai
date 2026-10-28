"""Pre-errata Ring's simultaneous lethal damage ends the duel in a draw."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

RING = 511000824
WALL = 17078030
WABOKU = 12607053
ARCHFIEND_SOLDIER = 49881766


def _deck(path: Path, cards: tuple[int, ...]) -> str:
    path.write_text("#main\n" + "\n".join(map(str, cards)) + "\n#extra\n!side\n")
    return str(path)


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_waboku", [False, True])
def test_ring_simultaneous_lethal_damage_is_draw(tmp_path, chain_waboku):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"pre-errata/c{RING}.lua", f"official/c{WALL}.lua"}
    if chain_waboku:
        scripts.add(f"official/c{WABOKU}.lua")
    if any(not (root / "scripts" / name).is_file() for name in scripts):
        pytest.skip("required card scripts not installed")
    own = _deck(tmp_path / "ring_wall.ydk", (RING, WALL, *VANILLA_DECK[2:]))
    other_cards = ((WALL, *VANILLA_DECK[1:6], WABOKU, *VANILLA_DECK[7:])
                   if chain_waboku
                   else (WALL, *VANILLA_DECK[1:]))
    other = _deck(tmp_path / "wall.ydk", other_cards)

    with GoatEnvironment(own, other, seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {RING, WALL, ARCHFIEND_SOLDIER} <= {c.code for c in obs.hand}
        assert WALL in {c.code for c in env.engine.probe.observation(1).hand}
        if chain_waboku:
            assert WABOKU in {c.code for c in env.engine.probe.observation(1).hand}
        soldier = ring_set = walls_set = walls_used = targets = 0
        paid = set()
        ring_used = waboku_set = waboku_used = False
        for _ in range(3000):
            if env.is_terminal():
                break
            actions = env.legal_actions()
            action = None
            player = obs.acting_player
            if obs.turn == 1 and player == 0:
                if not soldier:
                    action = next((a for a in actions if a.kind == "normal_summon"
                                   and a.parameters.get("code") == ARCHFIEND_SOLDIER), None)
                    soldier += action is not None
                if action is None and not ring_set:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == RING), None)
                    ring_set += action is not None
            if player == 0 and obs.turn == 1 and not (walls_set & 1) and action is None:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == WALL), None)
                if action is not None:
                    walls_set |= 1
            if player == 1 and obs.turn == 2 and not (walls_set & 2):
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == WALL), None)
                if action is not None:
                    walls_set |= 2
            if chain_waboku and player == 1 and obs.turn == 2 \
                    and (walls_set & 2) and not waboku_set and action is None:
                action = next((a for a in actions if a.kind == "set_spell_trap"
                               and a.parameters.get("code") == WABOKU), None)
                waboku_set = action is not None
            if obs.turn >= 2 and player == 0 and not (walls_used & 1):
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == WALL), None)
                if option is not None:
                    action = option
                    walls_used |= 1
            if obs.turn >= 3 and player == 1 and not (walls_used & 2):
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == WALL), None)
                if option is not None:
                    action = option
                    walls_used |= 2
            if actions[0].kind == "announce_number" and player not in paid:
                action = next((a for a in actions if a.parameters.get("number") == 7000), None)
                assert action is not None
                paid.add(player)
            if walls_used == 3 and obs.life_points == (1000, 1000) \
                    and player == 0 and not ring_used:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == RING), None)
                if option is not None:
                    action = option
                    ring_used = True
            if ring_used and not targets and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == ARCHFIEND_SOLDIER and a.parameters.get("controller") == 0),
                              None)
                assert action is not None
                targets = 1
            if chain_waboku and targets and player == 1 and not waboku_used:
                option = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == WABOKU), None)
                if option is not None:
                    assert obs.chain[-1].card_code == RING
                    action = option
                    waboku_used = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "select_position", "pass", "end_phase")),
                    actions[0])
            obs = env.step(action)

        assert soldier and ring_set and walls_set == walls_used == 3
        assert paid == {0, 1} and ring_used and targets
        assert waboku_set == waboku_used == chain_waboku
        assert env.is_terminal()
        assert obs.life_points == (0, 0)
        assert env.result() is None
        if chain_waboku:
            # The native terminal snapshot stops during resolution, so the
            # activated Trap remains on the public chain rather than in GY.
            assert [link.card_code for link in obs.chain] == [WALL, RING, WABOKU]
        assert scripts <= env.engine.probe.loaded_script_sha256.keys()
        path = tmp_path / "ring_simultaneous_draw.json"
        write_trajectory(path, env.trajectory())
        replay = read_trajectory(path)
        assert replay.winner is None
        assert verify_trajectory(replay, ExperimentalOcgcoreEngine(root)) \
            == len(replay.decisions)
        assert audit_trajectory_visibility(replay)["decisions"] == len(replay.decisions)
