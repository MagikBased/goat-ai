"""An equipped Sangan searches when Book sends it to its owner's Graveyard."""

import os
from pathlib import Path

import pytest

from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment

SCAPEGOAT = 504700123
METAMORPHOSIS = 46411259
BOOK = 14087893
RESTRICT = 504700102
SANGAN = 504700178
MYSTICAL_ELF = 15025844
SHEEP_CODES = {73915052, 73915053, 73915054, 73915055}


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
def test_restrict_equip_sangan_book_triggers_owner_search(tmp_path):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = (f"goat/c{SCAPEGOAT}.lua", f"official/c{METAMORPHOSIS}.lua",
               f"official/c{BOOK}.lua", f"goat/c{RESTRICT}.lua",
               f"goat/c{SANGAN}.lua")
    for relative in scripts:
        if not (root / "scripts" / relative).is_file():
            pytest.skip(f"script {relative} not installed")
    attacker = tmp_path / "restrict.ydk"
    attacker.write_text("#main\n" + "\n".join(map(str, (
        *((SCAPEGOAT, METAMORPHOSIS, BOOK) * 3), *VANILLA_DECK[9:])))
        + f"\n#extra\n{RESTRICT}\n!side\n")
    defender = tmp_path / "sangan.ydk"
    defender.write_text("#main\n" + "\n".join(map(str, (
        SANGAN, *VANILLA_DECK[1:]))) + "\n#extra\n!side\n")

    with GoatEnvironment(str(attacker), str(defender), seed=100,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert {SCAPEGOAT, METAMORPHOSIS, BOOK} <= {c.code for c in obs.hand}
        assert SANGAN in {c.code for c in env.engine.probe.observation(1).hand}
        goat = sangan_summoned = meta = token = fusion = restrict = target = False
        equipped = book_used = book_targeted = searched = False
        deck_before_search = None
        for _ in range(110):
            actions = env.legal_actions()
            action = None
            if obs.turn == 1 and obs.acting_player == 0 and not goat:
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == SCAPEGOAT), None)
                goat |= action is not None
            if obs.turn == 2 and obs.acting_player == 1 and not sangan_summoned:
                action = next((a for a in actions if a.kind == "normal_summon"
                               and a.parameters.get("code") == SANGAN), None)
                sangan_summoned |= action is not None
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
                action = next((a for a in actions if a.parameters.get("code") == SANGAN
                               and a.parameters.get("controller") == 1), action)
                target |= action is not None and action.kind == "select_card"
            if target and obs.turn == 3 and obs.phase == "main1" and not obs.chain:
                equipped |= any(c.code == SANGAN and c.zone == "spell_trap"
                                and c.controller == 0 for c in obs.field)
            if equipped and obs.acting_player == 0 and not book_used:
                assert not any(c.code == SANGAN for c in obs.graveyards[1])
                assert not env.engine.probe.observation(0).private_reveals
                deck_before_search = obs.deck_counts[1]
                action = next((a for a in actions if a.kind == "activate"
                               and a.parameters.get("code") == BOOK), action)
                book_used |= action is not None and action.kind == "activate"
            if book_used and not book_targeted and actions[0].kind == "select_card":
                action = next((a for a in actions if a.parameters.get("code") == RESTRICT
                               and a.parameters.get("controller") == 0), action)
                book_targeted |= action is not None and action.kind == "select_card"
            if book_targeted and obs.acting_player == 1 \
                    and actions[0].kind == "select_card" and not searched:
                assert SANGAN in {c.code for c in obs.graveyards[1]}
                assert all(a.parameters.get("location") == 1
                           and "sequence" not in a.parameters for a in actions)
                action = next((a for a in actions if a.parameters.get("code")
                               == MYSTICAL_ELF), None)
                assert action is not None
                searched = True
            if action is None:
                action = next((a for a in actions if a.kind in (
                    "select_card", "place", "pass", "end_phase")), actions[0])
            obs = env.step(action)
            if searched and MYSTICAL_ELF in {c.code for c in obs.hand} \
                    and obs.acting_player == 1:
                attacker_view = env.engine.probe.observation(0)
                assert goat and sangan_summoned and meta and token and fusion
                assert restrict and target and equipped and book_used and book_targeted
                assert attacker_view.deck_counts[1] == deck_before_search - 1
                assert any(c.code == SANGAN for c in attacker_view.graveyards[1])
                assert any(c.code == RESTRICT and c.position == "facedown"
                           for c in env.engine.probe.observation(0).field)
                assert MYSTICAL_ELF in attacker_view.known_opponent_hand_cards
                assert any(reveal.recipient == 0 and any(c.code == MYSTICAL_ELF
                           for c in reveal.cards) for reveal in attacker_view.private_reveals)
                assert not obs.private_reveals
                assert set(scripts) <= env.engine.probe.loaded_script_sha256.keys()
                return
    pytest.fail("equipped Sangan did not search after Book set Restrict")
