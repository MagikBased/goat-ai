"""Restrict targets a hidden set monster by field slot before equipping it."""

import json
import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

SCAPEGOAT = 504700123
METAMORPHOSIS = 46411259
RESTRICT = 504700102
DEKOICHI = 87621407
SHEEP_CODES = {73915052, 73915053, 73915054, 73915055}


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_restrict_targets_set_dekoichi_without_revealing_it(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    for relative in (f"goat/c{SCAPEGOAT}.lua", f"official/c{METAMORPHOSIS}.lua",
                     f"goat/c{RESTRICT}.lua", f"official/c{DEKOICHI}.lua"):
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    attacker = tmp_path / "restrict.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        *((SCAPEGOAT, METAMORPHOSIS) * 3), *VANILLA_DECK[6:])))
        + f"\n#extra\n{RESTRICT}\n!side\n")
    defender = tmp_path / "dekoichi.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        DEKOICHI, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert DEKOICHI in {c.code for c in env.engine.probe.observation(1).hand}
        goat = dekoichi_set = meta = token = fusion = restrict = target = False
        target_slot = None
        deck_count_before = None
        for _ in range(90):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not goat:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                goat |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not dekoichi_set:
                action = next((a for a in actions if a.kind == "set_monster"
                               and a.parameters.get("code") == DEKOICHI), None)
                dekoichi_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not meta:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == METAMORPHOSIS), action)
                meta |= action is not None and action.kind == "activate"
            if meta and not token and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               in SHEEP_CODES and a.parameters.get("controller") == 0),
                              action)
                token |= action is not None and action.kind == "select_card"
            if token and not fusion and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               == RESTRICT), action)
                fusion |= action is not None and action.kind == "select_card"
            if fusion and not restrict:
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == RESTRICT), action)
                restrict |= action is not None and action.kind == "chain"
            if restrict and not target and actions[0].kind == "select_card":
                assert len(actions) == 1
                assert actions[0].parameters.get("controller") == 1
                assert actions[0].parameters.get("location") == 4
                assert "code" not in actions[0].parameters
                hidden = next(c for c in obs.field if c.zone == "monster"
                              and c.controller == 1)
                assert hidden.code is None and hidden.position == "facedown"
                target_slot = hidden.sequence
                deck_count_before = obs.deck_counts[1]
                action = actions[0]
                target = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if target and obs.turn == 3 and obs.phase == "main1" \
                    and obs.acting_player == 0 and not obs.chain:
                own = env.engine.probe.observation(0)
                other = env.engine.probe.observation(1)
                assert not any(c.code == DEKOICHI and c.zone == "monster"
                               for c in own.field)
                equipped = [c for c in own.field if c.zone == "spell_trap"
                            and c.controller == 0 and c.code == DEKOICHI]
                assert len(equipped) == 1
                assert equipped[0].position == "facedown"
                restrict_card = next(c for c in own.field if c.code == RESTRICT)
                assert equipped[0].equipped_to == (0, restrict_card.sequence)
                hidden_equip = next(c for c in other.field if c.zone == "spell_trap"
                                    and c.controller == 0 and c.sequence == equipped[0].sequence)
                assert hidden_equip.code is None and hidden_equip.position == "facedown"
                assert hidden_equip.equipped_to == equipped[0].equipped_to
                assert (0, "spell_trap", hidden_equip.sequence, DEKOICHI) in {
                    (c.controller, c.zone, c.sequence, c.code)
                    for c in other.known_opponent_field_cards}
                assert any(c.code == RESTRICT and c.attack == 0 for c in own.field)
                assert own.deck_counts[1] == deck_count_before
                assert DEKOICHI not in {c.code for c in own.graveyards[1]}
                assert not other.private_reveals
                assert own.life_points == (8000, 8000)
                assert {f"goat/c{SCAPEGOAT}.lua", f"official/c{METAMORPHOSIS}.lua",
                        f"goat/c{RESTRICT}.lua"} \
                    <= env.engine.probe.loaded_script_sha256.keys()
                assert target_slot is not None
                agents = (RandomAgent(52), RandomAgent(53))
                for _ in range(3000):
                    if env.is_terminal():
                        break
                    obs = env.step(agents[obs.acting_player].select_action(
                        obs, env.legal_actions()))
                else:
                    pytest.fail("Restrict / Dekoichi duel exceeded 3000 decisions")
                trajectory = env.trajectory()
                assert trajectory.schema_version == 21
                path = tmp_path / "restrict_set_equip_v21.json"
                write_trajectory(path, trajectory)
                assert verify_trajectory(read_trajectory(path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    trajectory.decisions)
                legacy = json.loads(path.read_text())
                legacy["schema_version"] = 19
                for view in [*(row["observation"] for row in legacy["decisions"]),
                             legacy["terminal_observation"]]:
                    for card in view["field"]:
                        if card["position"] == "facedown":
                            card["equipped_to"] = None
                old_path = tmp_path / "restrict_set_equip_v19.json"
                old_path.write_text(json.dumps(legacy))
                assert verify_trajectory(read_trajectory(old_path),
                                         ExperimentalOcgcoreEngine(root)) == len(
                    trajectory.decisions)
                return
    pytest.fail("Restrict did not equip set Dekoichi within 90 decisions")
