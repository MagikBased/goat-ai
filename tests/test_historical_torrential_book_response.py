"""Book chained to Torrential turns a monster down but does not save it."""

import os
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.engine.probe_deck import VANILLA_DECK
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

BOOK = 14087893
TORRENTIAL = 53582587


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("chain_book", [False, True])
def test_book_chained_to_torrential_does_not_prevent_destruction(tmp_path, chain_book):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    scripts = {f"official/c{code}.lua" for code in (BOOK, TORRENTIAL)}
    if any(not (root / "scripts" / script).is_file() for script in scripts):
        pytest.skip("required official card script not installed")
    paths = []
    for name, code in (("book", BOOK), ("torrential", TORRENTIAL)):
        path = tmp_path / f"{name}.ydk"
        path.write_text("#main\n" + "\n".join(map(str, (code, *VANILLA_DECK[1:])))
                        + "\n#extra\n!side\n")
        paths.append(path)

    with GoatEnvironment(*(str(path) for path in paths), seed=52,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        assert BOOK in {card.code for card in obs.hand}
        assert TORRENTIAL in {card.code for card in env.engine.probe.observation(1).hand}
        summoned = []
        trap_set = trap_chained = book_chained = book_targeted = checked = False
        agents = (RandomAgent(52), RandomAgent(53))
        for _ in range(3000):
            if env.is_terminal():
                assert checked
                path = tmp_path / f"torrential_book_{chain_book}.json"
                write_trajectory(path, env.trajectory())
                loaded = read_trajectory(path)
                assert verify_trajectory(loaded, ExperimentalOcgcoreEngine(root)) == len(
                    loaded.decisions)
                audit_trajectory_visibility(loaded)
                return
            actions = env.legal_actions()
            action = None
            if not checked and obs.acting_player == 0 and obs.turn in (1, 3) \
                    and len(summoned) < (1 if obs.turn == 1 else 2):
                action = next((item for item in actions
                               if item.kind == "normal_summon"), None)
                if action is not None:
                    summoned.append(action.parameters["code"])
            if not checked and obs.acting_player == 1 and obs.turn == 2 \
                    and not trap_set:
                action = next((item for item in actions
                               if item.kind == "set_spell_trap"
                               and item.parameters.get("code") == TORRENTIAL), None)
                trap_set = action is not None
            if (not checked and trap_set and len(summoned) == 2
                    and obs.acting_player == 1 and not trap_chained):
                action = next((item for item in actions
                               if item.kind == "chain"
                               and item.parameters.get("code") == TORRENTIAL), action)
                trap_chained = action is not None and action.kind == "chain"
            if (trap_chained and not book_chained and obs.acting_player == 0
                    and [link.card_code for link in obs.chain] == [TORRENTIAL]):
                option = next((item for item in actions
                               if item.kind == "chain"
                               and item.parameters.get("code") == BOOK), None)
                assert option is not None
                action = option if chain_book else next(
                    item for item in actions if item.kind == "pass")
                book_chained = True
            if (chain_book and book_chained and not book_targeted
                    and actions[0].kind == "select_card"):
                assert [link.card_code for link in obs.chain] == [TORRENTIAL, BOOK]
                action = next((item for item in actions
                               if item.parameters.get("code") == summoned[-1]
                               and item.parameters.get("controller") == 0), None)
                assert action is not None
                book_targeted = True
            if action is None and not checked:
                action = next((item for item in actions if item.kind in (
                    "select_card", "place", "select_position", "pass", "end_phase")),
                    actions[0])
            if action is None:
                action = agents[obs.acting_player].select_action(obs, actions)
            obs = env.step(action)
            if (trap_chained and not checked and obs.turn == 3
                    and obs.phase == "main1" and not obs.chain
                    and TORRENTIAL in {card.code for card in obs.graveyards[1]}):
                assert len(summoned) == 2 and trap_set
                assert all(code in {card.code for card in obs.graveyards[0]}
                           for code in summoned)
                assert not any(card.zone == "monster" for card in obs.field)
                assert (BOOK in {card.code for card in obs.graveyards[0]}) == chain_book
                assert book_targeted == chain_book
                assert obs.life_points == (8000, 8000)
                assert scripts <= env.engine.probe.loaded_script_sha256.keys()
                checked = True
    pytest.fail("Torrential / Book response did not complete")
