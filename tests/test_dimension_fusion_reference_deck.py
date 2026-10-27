"""Published Dimension Fusion list, pinned historical IDs, and native duels."""

import base64
import os
import struct
from pathlib import Path

import pytest

from goat_ai.agents import RandomAgent
from goat_ai.engine.decks import read_goat_whitelist, read_ydk, validate_goat_deck
from goat_ai.engine.experimental_adapter import ExperimentalOcgcoreEngine
from goat_ai.environments import GoatEnvironment
from goat_ai.evaluation.visibility import audit_trajectory_visibility
from goat_ai.replay import read_trajectory, verify_trajectory, write_trajectory

REPOSITORY = Path(__file__).resolve().parent.parent
SOURCE = REPOSITORY / "configs/decks/dimension_fusion_turbo_wikiformat_reference.ydke"
DECK = REPOSITORY / "examples/decks/dimension_fusion_turbo_wikiformat_reference.ydk"
CHAOS = REPOSITORY / "examples/decks/chaos_turbo_riclar_2020.ydk"

# Source YDKE uses current printed-card IDs. These are the pinned GOAT and
# pre-errata replacements used across the project's existing deck corpus.
HISTORICAL_IDS = {
    72989439: 504700118,   # Black Luster Soldier
    34124316: 504700188,   # Cyber Jar
    40737112: 511001039,  # Dark Magician of Chaos
    24317029: 504700044,   # Gravekeeper's Spy
    31786629: 504700054,   # Thunder Dragon
    87910978: 511002995,  # Brain Control
    83555666: 511000824,  # Ring of Destruction
    71044499: 504700116,  # Nobleman of Crossout
    63519819: 504700102,  # Thousand-Eyes Restrict
    83986578: 504700143,  # King Tiger Wanghu
}


def test_dimension_fusion_reference_matches_published_ydke():
    source = SOURCE.read_text().strip()
    assert source.startswith("ydke://")
    sections = source.removeprefix("ydke://").split("!")
    assert len(sections) == 4 and sections[-1] == ""
    decoded = []
    for section in sections[:-1]:
        raw = base64.b64decode(section, validate=True)
        assert len(raw) % 4 == 0
        cards = struct.unpack("<" + "I" * (len(raw) // 4), raw)
        decoded.append(tuple(HISTORICAL_IDS.get(code, code) for code in cards))
    deck = read_ydk(DECK)
    assert (deck.main, deck.extra, deck.side) == tuple(decoded)
    assert (len(deck.main), len(deck.extra), len(deck.side)) == (40, 15, 15)
    assert deck.main.count(23557835) == 2  # Dimension Fusion
    assert deck.main.count(87621407) == 3  # Dekoichi


@pytest.mark.skipif(not os.getenv("GOAT_AI_NATIVE_ROOT"), reason="native assets not installed")
@pytest.mark.parametrize("fusion_seat", [0, 1])
def test_dimension_fusion_reference_full_duel_and_replay(tmp_path, fusion_seat):
    root = Path(os.environ["GOAT_AI_NATIVE_ROOT"])
    deck = read_ydk(DECK)
    validate_goat_deck(
        deck, read_goat_whitelist(root / "banlist/GOAT.lflist.conf"),
        root / "database/cards.cdb", root / "database/goat-entries.cdb",
        root / "database/cards-unofficial.cdb")
    paths = (str(DECK), str(CHAOS)) if fusion_seat == 0 else (str(CHAOS), str(DECK))
    with GoatEnvironment(*paths, seed=1,
                         engine=ExperimentalOcgcoreEngine(root)) as env:
        observation = env.reset()
        agents = (RandomAgent(1), RandomAgent(1001))
        for _ in range(3000):
            action = agents[observation.acting_player].select_action(
                observation, env.legal_actions())
            observation = env.step(action)
            if env.is_terminal():
                break
        else:
            pytest.fail("Dimension Fusion reference duel exceeded 3000 decisions")
        trajectory = env.trajectory()
        assert trajectory.winner in (0, 1, None)
        assert len(trajectory.decisions) > 100
        assert any(23557835 in record.observation.own_main_deck
                   for record in trajectory.decisions
                   if record.observation.viewer == fusion_seat)
    path = tmp_path / "dimension_fusion_reference.json"
    write_trajectory(path, trajectory)
    loaded = read_trajectory(path)
    assert loaded == trajectory
    audit_trajectory_visibility(loaded)
    assert verify_trajectory(loaded, ExperimentalOcgcoreEngine(root)) == len(
        trajectory.decisions)
