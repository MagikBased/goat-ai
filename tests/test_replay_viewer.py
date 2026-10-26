"""The offline viewer embeds validated visible decisions and escapes replay text."""

import hashlib
import re
import sqlite3
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from goat_ai.actions import Action
from goat_ai.engine.decks import read_ydk
from goat_ai.evaluation.competitive_corpus import TOURNAMENT_MAIN_DECKS
from goat_ai.observations import (
    CardView,
    DisabledZoneView,
    Observation,
    PrivateRevealView,
    PublicRevealView,
    RevealedCardView,
)
from goat_ai.replay import DecisionRecord, Trajectory, write_trajectory
from scripts.render_replay import render_catalog_viewer, render_replay


def test_common_card_navigation_matches_sourced_main_decks():
    root = Path(__file__).resolve().parent.parent
    template = (root / "examples/replay_viewer.html").read_text(encoding="utf-8")
    match = re.search(r"const COMMON_CARD_CODES = new Set\(\[([^\]]+)\]\);", template)
    assert match is not None
    viewer_codes = {int(code) for code in re.findall(r"\d+", match.group(1))}
    deck_counts = Counter()
    for filename in TOURNAMENT_MAIN_DECKS:
        deck_counts.update(set(read_ydk(root / "examples/decks" / filename).main))
    assert viewer_codes == {code for code, count in deck_counts.items() if count >= 5}
    assert 'id="previous-common"' in template
    assert 'id="next-common"' in template


def test_render_replay_embeds_visible_cards_and_escapes_html(tmp_path):
    database = tmp_path / "native/database"
    database.mkdir(parents=True)
    with sqlite3.connect(database / "cards.cdb") as connection:
        connection.execute("CREATE TABLE texts (id INTEGER PRIMARY KEY, name TEXT)")
        connection.execute("INSERT INTO texts VALUES (10, 'Visible Monster')")
        connection.execute("INSERT INTO texts VALUES (11, 'Revealed Monster')")
        connection.execute("INSERT INTO texts VALUES (12, 'Privately Seen Monster')")
        connection.execute("INSERT INTO texts VALUES (13, 'Decklist Only Monster')")
        connection.execute("INSERT INTO texts VALUES (14, 'Known Hand Monster')")
    observation = Observation(
        viewer=0, acting_player=0, turn=1, phase="main1", life_points=(8000, 8000),
        hand=(CardView(0, "hand", "hidden", 10, 0),),
        field=(CardView(0, "monster", "faceup", 10, 0, "attack", 1900, 1000,
                        ((1, 1),)),
               CardView(1, "monster", "facedown", None, 0, "defense")),
        graveyards=((), ()), banished=((), ()), opponent_hand_count=5,
        deck_counts=(34, 35), extra_deck_counts=(0, 0),
        public_reveals=(PublicRevealView(1, 1, "deck_top", (11,)),),
        disabled_zones=(DisabledZoneView(0, "monster", 2),),
        private_reveals=(PrivateRevealView(1, 0, (RevealedCardView(12, 1, 1),)),),
        own_main_deck=(10, 10, 13),
        known_opponent_hand_cards=(14,),
    )
    action = Action("0", "normal_summon", 0, {"code": 10})
    trajectory = Trajectory(
        "goat", ("a.ydk", "b.ydk"), 42,
        (DecisionRecord(observation, (action,), action),), 0,
        skill_metadata={"comment": "</script><script>window.injected=true</script>"},
    )
    source = tmp_path / "game.json"
    output = tmp_path / "game.html"
    write_trajectory(source, trajectory)
    assert render_replay(source, output, tmp_path / "native") == (1, 5)
    html = output.read_text()
    assert '"10":"Visible Monster"' in html
    assert '"11":"Revealed Monster"' in html
    assert '"12":"Privately Seen Monster"' in html
    assert '"13":"Decklist Only Monster"' in html
    assert '"14":"Known Hand Monster"' in html
    assert '"public_reveals"' in html
    assert '"disabled_zones"' in html
    assert 'slot.disabled' in html
    assert '"private_reveals"' in html
    assert '"own_main_deck":[10,10,13]' in html
    assert '"opponent_hand_count":5' in html
    assert '"known_opponent_hand_cards":[14]' in html
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert f'<script id="embedded-sha256" type="application/json">"{digest}"</script>' in html
    assert 'id="download-labels"' in html
    assert 'id="known-hand"' in html
    assert '"attack":1900' in html
    assert '"counters":[[1,1]]' in html
    assert '"code":null' in html
    assert "window.injected=true" in html
    assert "</script><script>window.injected" not in html
    assert "\\u003c/script>" in html
    assert "Card #999" not in html


def test_render_replay_includes_terminal_frame_and_its_card_names(tmp_path):
    database = tmp_path / "native/database"
    database.mkdir(parents=True)
    with sqlite3.connect(database / "cards.cdb") as connection:
        connection.execute("CREATE TABLE texts (id INTEGER PRIMARY KEY, name TEXT)")
        connection.execute("INSERT INTO texts VALUES (99, 'Final Card')")
    observation = Observation(
        viewer=0, acting_player=0, turn=1, phase="main1", life_points=(8000, 8000),
        hand=(), field=(), graveyards=((), ()), banished=((), ()),
        opponent_hand_count=5, deck_counts=(35, 35), extra_deck_counts=(0, 0),
    )
    final = replace(observation, life_points=(0, 0),
                    graveyards=((CardView(0, "graveyard", "faceup", 99),), ()))
    action = Action("0", "pass", 0)
    trajectory = Trajectory(
        "goat", ("a.ydk", "b.ydk"), 42,
        (DecisionRecord(observation, (action,), action),), None,
        schema_version=18, terminal_observation=final,
    )
    source = tmp_path / "terminal.json"
    output = tmp_path / "terminal.html"
    write_trajectory(source, trajectory)
    assert render_replay(source, output, tmp_path / "native") == (1, 1)
    html = output.read_text()
    assert '"terminal_observation"' in html
    assert '"life_points":[0,0]' in html
    assert '"99":"Final Card"' in html
    assert 'terminal ? "Duel ended"' in html


def test_catalog_viewer_names_all_allowed_cards_without_a_replay(tmp_path):
    native = tmp_path / "native"
    database = native / "database"
    database.mkdir(parents=True)
    banlist = native / "banlist"
    banlist.mkdir()
    (banlist / "GOAT.lflist.conf").write_text(
        "$whitelist\n10 3\n99 1\n88 0\n")
    for filename, code, name in (
        ("cards.cdb", 10, "Visible Monster"),
        ("goat-entries.cdb", 99, "GOAT Variant"),
    ):
        with sqlite3.connect(database / filename) as connection:
            connection.execute("CREATE TABLE texts (id INTEGER PRIMARY KEY, name TEXT)")
            connection.execute("INSERT INTO texts VALUES (?, ?)", (code, name))
    output = tmp_path / "viewer.html"
    assert render_catalog_viewer(output, native) == 2
    html = output.read_text()
    assert '<script id="embedded-replay" type="application/json">null</script>' in html
    assert '"10":"Visible Monster"' in html
    assert '"99":"GOAT Variant"' in html
    assert '"88":' not in html
    assert '"code":99' not in html
    assert 'missingNames.size' in html

    observation = Observation(
        viewer=0, acting_player=0, turn=1, phase="main1", life_points=(8000, 8000),
        hand=(CardView(0, "hand", "hidden", 10, 0),), field=(),
        graveyards=((), ()), banished=((), ()), opponent_hand_count=5,
        deck_counts=(35, 35), extra_deck_counts=(0, 0),
    )
    action = Action("0", "pass", 0)
    source = tmp_path / "game.json"
    write_trajectory(source, Trajectory(
        "goat", ("a.ydk", "b.ydk"), 42,
        (DecisionRecord(observation, (action,), action),), 0,
    ))
    assert render_replay(source, output, native) == (1, 2)
    assert '"99":"GOAT Variant"' in output.read_text()

    with sqlite3.connect(database / "cards.cdb") as connection:
        connection.execute("CREATE TABLE datas (id INTEGER PRIMARY KEY, type INTEGER)")
        connection.execute("INSERT INTO datas VALUES (77, 16384)")
        connection.execute("INSERT INTO texts VALUES (77, 'Generated Token')")
    assert render_catalog_viewer(output, native) == 3
    assert '"77":"Generated Token"' in output.read_text()

    (database / "goat-entries.cdb").unlink()
    with pytest.raises(ValueError, match="lack 1 GOAT/Token names"):
        render_catalog_viewer(output, native)
