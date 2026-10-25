"""Historical Skill Drain timing around Thousand-Eyes Restrict's equip effect."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

SCAPEGOAT = 504700123
METAMORPHOSIS = 46411259
RESTRICT = 504700102
SKILL_DRAIN = 82732705
SHEEP_CODES = {73915052, 73915053, 73915054, 73915055}


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("timing", ["chain_to_equip", "after_equip"])
def test_skill_drain_timing_on_restrict_equip(tmp_path, timing):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"goat/c{SCAPEGOAT}.lua", f"official/c{METAMORPHOSIS}.lua",
               f"goat/c{RESTRICT}.lua", f"official/c{SKILL_DRAIN}.lua")
    for relative in scripts:
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    own = tmp_path / "restrict.ydk"
    own.write_text("#main\n" + "\n".join(map(str, (
        *((SCAPEGOAT, METAMORPHOSIS) * 3), *VANILLA_DECK[6:])))
        + f"\n#extra\n{RESTRICT}\n!side\n")
    other = tmp_path / "skill_drain.ydk"
    other.write_text("#main\n" + "\n".join(map(str, (
        SKILL_DRAIN, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(own), str(other), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert SKILL_DRAIN in {c.code for c in env.engine.probe.observation(1).hand}
        goat = summoned = drain_set = meta = token = fusion = restrict = target = False
        drain_used = equip_seen = False
        target_code = None
        for _ in range(110):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not goat:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                goat |= action is not None
            if obs.turn == 2 and obs.acting_player == 1:
                if not summoned:
                    action = next((a for a in actions if a.kind == "normal_summon"), None)
                    if action is not None:
                        target_code = action.parameters["code"]
                        summoned = True
                if summoned and not drain_set and action is None:
                    action = next((a for a in actions if a.kind == "set_spell_trap"
                                   and a.parameters.get("code") == SKILL_DRAIN), None)
                    drain_set |= action is not None
            if obs.turn == 3 and obs.acting_player == 0 and not meta:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == METAMORPHOSIS), action)
                meta |= action is not None and action.kind == "activate"
            if meta and not token and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code")
                               in SHEEP_CODES and a.parameters.get("controller") == 0), action)
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
                action = next((a for a in actions if a.parameters.get("code")
                               == target_code and a.parameters.get("controller") == 1), action)
                target |= action is not None and action.kind == "select_card"
            if timing == "chain_to_equip" and target and obs.acting_player == 1 \
                    and not drain_used:
                assert [link.card_code for link in obs.chain] == [RESTRICT]
                action = next((a for a in actions if a.kind == "chain"
                               and a.parameters.get("code") == SKILL_DRAIN), None)
                drain_used |= action is not None
                assert drain_used
            if timing == "after_equip" and target and obs.turn == 3 \
                    and obs.phase == "main1" and not obs.chain:
                equip_seen = any(c.code == target_code and c.zone == "spell_trap"
                                 and c.controller == 0 for c in obs.field)
            if equip_seen and obs.turn == 4 and obs.acting_player == 1 \
                    and not drain_used:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SKILL_DRAIN), action)
                drain_used |= action is not None and action.kind == "activate"
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if drain_used and not obs.chain and any(c.code == SKILL_DRAIN
                                                    for c in obs.field):
                own_view = env.engine.probe.observation(0)
                restrict_card = next(c for c in own_view.field if c.code == RESTRICT)
                assert restrict_card.position == "faceup"
                assert (restrict_card.attack, restrict_card.defense) == (0, 0)
                assert own_view.life_points == (8000, 7000)
                equipped = any(c.code == target_code and c.zone == "spell_trap"
                               and c.controller == 0 for c in own_view.field)
                if timing == "chain_to_equip":
                    assert not equipped
                    assert any(c.code == target_code and c.zone == "monster"
                               and c.controller == 1 for c in own_view.field)
                else:
                    assert equip_seen and equipped
                    assert not any(c.code == target_code and c.zone == "monster"
                                   for c in own_view.field)
                assert set(scripts) <= env.engine.probe.loaded_script_sha256.keys()
                return
    pytest.fail(f"Skill Drain timing did not resolve: {timing}")
