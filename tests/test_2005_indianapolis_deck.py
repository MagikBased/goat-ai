"""SJC Indianapolis 2005 Top 8 deck transcription and native duel smoke."""

import os
import sqlite3
from collections import Counter
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.decks import read_goat_whitelist, read_ydk, validate_goat_deck
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.historical_corpus import historical_main_decks
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

ROOT = Path(__file__).resolve().parents[1]
MATT_DECK = ROOT / "examples/decks/goat_control_matt_peddle_indianapolis_2005.ydk"
MICHAEL_DECK = ROOT / "examples/decks/goat_control_michael_fukuyama_indianapolis_2005.ydk"
DARYL_DECK = ROOT / "examples/decks/gravekeeper_daryl_gessler_indianapolis_2005.ydk"
JESSE_DECK = ROOT / "examples/decks/goat_control_jesse_twohig_indianapolis_2005.ydk"
OPPONENT = ROOT / "examples/decks/goat_control_lolmarcus_2020.ydk"
MATT_EXTRA_NAMES = Counter({
    "Thousand-Eyes Restrict": 3,
    "Flame Ghost": 1,
    "Darkfire Dragon": 1,
    "Reaper on the Nightmare": 2,
    "Dark Balter the Terrible": 2,
    "Ryu Senshi": 1,
    "Ojama King": 1,
    "Dark Blade the Dragon Knight": 2,
    "King Dragun": 1,
    "Gatling Dragon": 1,
    "The Last Warrior from Another Planet": 1,
})
MICHAEL_EXTRA_NAMES = Counter({
    "Thousand-Eyes Restrict": 3,
    "Dark Flare Knight": 2,
    "Ryu Senshi": 3,
    "Dark Balter the Terrible": 2,
    "King Dragun": 2,
    "Dark Blade the Dragon Knight": 2,
    "Darkfire Dragon": 1,
    "Charubin the Fire Knight": 1,
    "Fusionist": 1,
    "Giltia the D. Knight": 1,
    "Gatling Dragon": 1,
})
DARYL_EXTRA_NAMES = Counter({"Flame Swordsman": 1, "King Dragun": 2})
JESSE_EXTRA_NAMES = Counter({
    "Thousand-Eyes Restrict": 3,
    "Dark Balter the Terrible": 3,
    "Dragoness the Wicked Knight": 1,
    "Darkfire Dragon": 1,
    "Reaper on the Nightmare": 3,
    "Master of Oz": 3,
    "Ryu Senshi": 2,
    "Fiend Skull Dragon": 2,
    "Gatling Dragon": 1,
    "Ojama King": 1,
    "The Last Warrior from Another Planet": 1,
    "King Dragun": 1,
    "Thousand Dragon": 1,
})


def _source_name(name: str) -> str:
    return (name.removesuffix(" (GOAT)").removesuffix(" (Pre-Errata)")
            .replace("D.D.", "D. D.").casefold().replace("judgement", "judgment"))


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("player, deck_path, extra_names", [
    ("Matt Peddle", MATT_DECK, MATT_EXTRA_NAMES),
    ("Michael Fukuyama", MICHAEL_DECK, MICHAEL_EXTRA_NAMES),
    ("Daryl Gessler", DARYL_DECK, DARYL_EXTRA_NAMES),
    ("Jesse Twohig", JESSE_DECK, JESSE_EXTRA_NAMES),
])
def test_published_2005_main_and_fusions_match_pinned_legal_ids(
    player, deck_path, extra_names,
):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck = read_ydk(deck_path)
    assert (len(deck.main), len(deck.extra), len(deck.side)) == (
        sum(historical_main_decks()[player].values()), sum(extra_names.values()), 0)
    validate_goat_deck(deck, read_goat_whitelist(root / "banlist/GOAT.lflist.conf"),
                       root / "database/cards.cdb",
                       root / "database/goat-entries.cdb",
                       root / "database/cards-unofficial.cdb")
    names = {}
    for db in ("cards.cdb", "goat-entries.cdb", "cards-unofficial.cdb"):
        with sqlite3.connect(root / "database" / db) as connection:
            for code in set(deck.main + deck.extra) - names.keys():
                row = connection.execute("SELECT name FROM texts WHERE id=?", (code,)) \
                    .fetchone()
                if row is not None:
                    names[code] = _source_name(row[0])
    assert names.keys() >= set(deck.main + deck.extra)
    expected_main = Counter({_source_name(name): copies for name, copies in
                             historical_main_decks()[player].items()})
    expected_extra = Counter({_source_name(name): copies for name, copies in
                              extra_names.items()})
    assert Counter(names[code] for code in deck.main) == expected_main
    assert Counter(names[code] for code in deck.extra) == expected_extra


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("deck_a, deck_b, seed", [
    (MATT_DECK, OPPONENT, 2070),
    (MATT_DECK, MICHAEL_DECK, 2072),
    (DARYL_DECK, MATT_DECK, 2074),
    (JESSE_DECK, DARYL_DECK, 2076),
])
def test_2005_deck_completes_visible_replay_verified_native_duel(
    tmp_path, deck_a, deck_b, seed,
):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    agents = (RandomAgent(seed), RandomAgent(seed + 1))
    with GoatEnvironment(str(deck_a), str(deck_b), seed=seed,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        obs = env.reset()
        designator_prompt = False
        for _ in range(3000):
            if env.is_terminal():
                break
            legal = env.legal_actions()
            if legal[0].kind == "announce_card":
                codes = {action.parameters["code"] for action in legal}
                assert {14087893, 33423043} <= codes  # Book and Designator are names.
                assert {504700102, 63519819}.isdisjoint(codes)  # Fusion names excluded.
                designator_prompt = True
            obs = env.step(agents[obs.acting_player].select_action(obs, legal))
        assert env.is_terminal(), "2005 deck duel exceeded 3000 decisions"
        if deck_b == MICHAEL_DECK:
            assert designator_prompt
        trajectory = env.trajectory()
        path = tmp_path / "indianapolis_2005.json"
        write_trajectory(path, trajectory)
        assert verify_trajectory(read_trajectory(path),
                                 ExperimentalOcgcoreEngine(root)) == len(
                                     trajectory.decisions)
        assert audit_trajectory_visibility(trajectory)["decisions"] == len(
            trajectory.decisions)
