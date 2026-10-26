"""The offline viewer embeds validated visible decisions and escapes replay text."""

import hashlib
import json
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
from scripts.render_replay import _reviewer_frame, render_catalog_viewer, render_replay
from scripts.setup_card_images import setup_card_backs, setup_card_images


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
    assert 'id="agents"' in template
    assert 'meta.demonstrator_seat' in template


def test_reviewer_frame_combines_private_views_without_changing_agent_observation():
    own = Observation(
        viewer=0, acting_player=0, turn=1, phase="main1", life_points=(8000, 8000),
        hand=(CardView(0, "hand", "hidden", 10, 0),),
        field=(CardView(0, "monster", "facedown", 12, 0, "defense"),
               CardView(1, "monster", "facedown", None, 0, "defense")),
        graveyards=((), ()), banished=((), ()), opponent_hand_count=1,
        deck_counts=(34, 34), extra_deck_counts=(0, 0),
    )
    opponent = replace(
        own, viewer=1, hand=(CardView(1, "hand", "hidden", 11, 0),),
        opponent_hand_count=1,
        field=(CardView(0, "monster", "facedown", None, 0, "defense"),
               CardView(1, "monster", "facedown", 13, 0, "defense")),
    )

    class Probe:
        def observation(self, viewer, *, terminal=False):
            return (own, opponent)[viewer]

    engine = type("Engine", (), {"probe": Probe()})()
    frame = _reviewer_frame(engine)
    assert frame["hands"] == [[10], [11]]
    assert frame["field"] == {"0:monster:0": 12, "1:monster:0": 13}
    assert own.field[1].code is None
    assert opponent.field[0].code is None


def test_reviewer_sidecar_is_separate_from_trajectory(tmp_path, monkeypatch):
    from scripts import render_replay as renderer

    observation = Observation(
        viewer=0, acting_player=0, turn=1, phase="main1", life_points=(8000, 8000),
        hand=(), field=(CardView(1, "monster", "facedown", None, 0, "defense"),),
        graveyards=((), ()), banished=((), ()), opponent_hand_count=1,
        deck_counts=(35, 35), extra_deck_counts=(0, 0),
    )
    action = Action("0", "pass", 0)
    source = tmp_path / "game.json"
    output = tmp_path / "game.html"
    write_trajectory(source, Trajectory(
        "goat", ("a.ydk", "b.ydk"), 42,
        (DecisionRecord(observation, (action,), action),), 0))
    before = source.read_bytes()
    monkeypatch.setattr(renderer, "_reviewer_data", lambda *args: {
        "schema_version": 1, "source_trajectory_sha256": hashlib.sha256(before).hexdigest(),
        "frames": [{"hands": [[], [11]], "field": {"1:monster:0": 13},
                    "banished": [[], []], "extra": [[], []], "decks": [[], []]}],
    })
    render_replay(source, output, tmp_path / "native", reviewer_reveal=True)
    assert source.read_bytes() == before
    assert b'"code":13' not in before
    assert '"1:monster:0":13' in output.read_text()
    sidecar = output.with_suffix(".review.json")
    assert sidecar.is_file()
    assert json.loads(sidecar.read_text())["source_trajectory_sha256"] == hashlib.sha256(before).hexdigest()


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
    image_folder = tmp_path / "card_images"
    image_folder.mkdir()
    (image_folder / "10.jpg").write_bytes(b"local thumbnail")
    (image_folder / "999.jpg").write_bytes(b"unrelated thumbnail")
    (image_folder / "cover.png").write_bytes(b"local card back")
    write_trajectory(source, trajectory)
    assert render_replay(source, output, tmp_path / "native") == (1, 5)
    html = output.read_text()
    assert '"10":"Visible Monster"' in html
    assert '"11":"Revealed Monster"' in html
    assert '"12":"Privately Seen Monster"' in html
    assert '"13":"Decklist Only Monster"' in html
    assert '"14":"Known Hand Monster"' in html
    assert ('<script id="embedded-images" type="application/json">'
            '{"10":"card_images/10.jpg","back":"card_images/cover.png"}</script>') in html
    assert 'card_images/999.jpg' not in html
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
    with sqlite3.connect(database / "cards.cdb") as connection:
        connection.execute("ALTER TABLE texts ADD COLUMN str1 TEXT")
        connection.execute("ALTER TABLE texts ADD COLUMN str2 TEXT")
        connection.execute("UPDATE texts SET str1='Choose effect', "
                           "str2='Change position' WHERE id=10")
    output = tmp_path / "viewer.html"
    assert render_catalog_viewer(output, native) == 2
    html = output.read_text()
    assert '<script id="embedded-replay" type="application/json">null</script>' in html
    assert '"10":"Visible Monster"' in html
    assert '"99":"GOAT Variant"' in html
    assert f'"{(10 << 20) | 1}":"Change position"' in html
    assert 'optionTexts[String(parameters.prompt_id)]' in html
    assert 'positionName(parameters.position)' in html
    assert 'raceName(parameters.race)' in html
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
        connection.execute("INSERT INTO texts (id, name) VALUES (77, 'Generated Token')")
    assert render_catalog_viewer(output, native) == 3
    assert '"77":"Generated Token"' in output.read_text()

    (database / "goat-entries.cdb").unlink()
    with pytest.raises(ValueError, match="lack 1 GOAT/Token names"):
        render_catalog_viewer(output, native)


def test_image_setup_uses_base_art_for_goat_variant_and_caches_it(tmp_path, monkeypatch):
    variant, base = 504700116, 71044499
    database = tmp_path / "native/database"
    database.mkdir(parents=True)
    with sqlite3.connect(database / "goat-entries.cdb") as connection:
        connection.execute("CREATE TABLE datas (id INTEGER PRIMARY KEY, alias INTEGER)")
        connection.execute("INSERT INTO datas VALUES (?, ?)", (variant, base))
    observation = Observation(
        viewer=0, acting_player=0, turn=1, phase="main1", life_points=(8000, 8000),
        hand=(CardView(0, "hand", "hidden", variant, 0),), field=(),
        graveyards=((), ()), banished=((), ()), opponent_hand_count=5,
        deck_counts=(35, 35), extra_deck_counts=(0, 0),
    )
    action = Action("0", "pass", 0)
    source = tmp_path / "game.json"
    write_trajectory(source, Trajectory(
        "goat", ("a.ydk", "b.ydk"), 42,
        (DecisionRecord(observation, (action,), action),), 0,
    ))
    requested = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, limit):
            return b"\xff\xd8\xfftest image"

    def fake_urlopen(request, timeout):
        requested.append(request.full_url)
        return Response()

    monkeypatch.setattr("scripts.setup_card_images.urlopen", fake_urlopen)
    output = tmp_path / "card_images"
    assert setup_card_images(source, output, tmp_path / "native", delay=0) == (1, 0, 0)
    assert requested == [f"https://images.ygoprodeck.com/images/cards_small/{base}.jpg"]
    assert (output / f"{variant}.jpg").read_bytes() == b"\xff\xd8\xfftest image"
    assert setup_card_images(source, output, tmp_path / "native", delay=0) == (0, 1, 0)
    assert len(requested) == 1


def test_card_back_setup_checks_pinned_image_and_reuses_cache(tmp_path, monkeypatch):
    data = b"\x89PNG\r\n\x1a\ncard back"
    monkeypatch.setattr("scripts.setup_card_images.COVER_FILES", {
        "cover.png": hashlib.sha256(data).hexdigest(),
        "cover2.png": hashlib.sha256(data).hexdigest(),
    })
    requested = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, limit):
            return data

    def fake_urlopen(request, timeout):
        requested.append(request.full_url)
        return Response()

    monkeypatch.setattr("scripts.setup_card_images.urlopen", fake_urlopen)
    assert setup_card_backs(tmp_path / "images") == (2, 0)
    assert all("/54a6e2395c532648ff762540e9615319fac4f51b/" in url
               for url in requested)
    assert setup_card_backs(tmp_path / "images") == (0, 2)
    assert len(requested) == 2
