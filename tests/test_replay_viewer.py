"""The offline viewer embeds validated visible decisions and escapes replay text."""

import sqlite3

from goat_ai.actions import Action
from goat_ai.observations import CardView, Observation
from goat_ai.replay import DecisionRecord, Trajectory, write_trajectory
from scripts.render_replay import render_replay


def test_render_replay_embeds_visible_cards_and_escapes_html(tmp_path):
    database = tmp_path / "native/database"
    database.mkdir(parents=True)
    with sqlite3.connect(database / "cards.cdb") as connection:
        connection.execute("CREATE TABLE texts (id INTEGER PRIMARY KEY, name TEXT)")
        connection.execute("INSERT INTO texts VALUES (10, 'Visible Monster')")
    observation = Observation(
        viewer=0, acting_player=0, turn=1, phase="main1", life_points=(8000, 8000),
        hand=(CardView(0, "hand", "hidden", 10, 0),),
        field=(CardView(1, "monster", "facedown", None, 0, "defense"),),
        graveyards=((), ()), banished=((), ()), opponent_hand_count=5,
        deck_counts=(34, 35), extra_deck_counts=(0, 0),
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
    assert render_replay(source, output, tmp_path / "native") == (1, 1)
    html = output.read_text()
    assert '"10":"Visible Monster"' in html
    assert '"opponent_hand_count":5' in html
    assert '"code":null' in html
    assert "window.injected=true" in html
    assert "</script><script>window.injected" not in html
    assert "\\u003c/script>" in html
    assert "Card #999" not in html
