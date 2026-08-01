from app.extensions import db
from app.models import Challenge, Event, Mission, Team, TeamMember, TeamMission, User


def _login_gm(client, app):
    with app.app_context():
        gm = User(email="gm@test.local", role="game_master")
        gm.set_password("pw")
        db.session.add(gm)
        db.session.commit()
    return client.post("/auth/login", data={"email": "gm@test.local", "password": "pw"})


def _get_status(app):
    with app.app_context():
        state = Event.query.get(1)
        return state.status if state else "draft"  # lazily created on first get_state() call


def test_event_lifecycle_transitions_drive_actual_state(client, app):
    _login_gm(client, app)
    assert _get_status(app) == "draft"

    assert client.post("/mod/event/publish").status_code == 302
    assert _get_status(app) == "not_started"

    assert client.post("/mod/event/start").status_code == 302
    assert _get_status(app) == "running"

    assert client.post("/mod/event/pause").status_code == 302
    assert _get_status(app) == "paused"

    assert client.post("/mod/event/start").status_code == 302
    assert _get_status(app) == "running"

    assert client.post("/mod/event/end").status_code == 302
    assert _get_status(app) == "ended"

    assert client.post("/mod/event/archive").status_code == 302
    assert _get_status(app) == "archived"


def test_event_lifecycle_routes_require_game_master(client, app):
    for path in (
        "/mod/event/publish",
        "/mod/event/start",
        "/mod/event/pause",
        "/mod/event/end",
        "/mod/event/archive",
    ):
        assert client.post(path).status_code in (302, 401, 403)
    with app.app_context():
        # Never actually transitioned without auth.
        assert Event.query.get(1) is None or Event.query.get(1).status == "draft"


def test_pausing_the_event_blocks_hint_requests_and_resuming_restores_them(client, app):
    # Regression test: request_hint() previously had no event.status gate at all, unlike the
    # other three scoring-affecting player actions (submit, run-tests, soft-lock, KC-answer) --
    # a team could still burn hint budget / take the score penalty while a Game Master had the
    # event explicitly paused (e.g. for an announcement or a technical hold).
    _login_gm(client, app)
    client.post("/mod/event/publish")
    client.post("/mod/event/start")

    with app.app_context():
        team = Team(name="Pause Test Squad", score=10, integrity=100)
        team.set_key("PAUSE01")
        db.session.add(team)
        mission = Mission(
            title="Pause Test Booth",
            type="code",
            narrative="x",
            cipher_word="X",
            booth_id=1,
            order_index=1,
            status="published",
        )
        db.session.add(mission)
        db.session.commit()
        db.session.add(
            Challenge(mission_id=mission.id, type="code", prompt="p", grading_mode="auto")
        )
        db.session.commit()

    player = app.test_client()
    player.post("/auth/team-login", data={"name": "Pause Test Squad", "key": "PAUSE01"})

    client.post("/mod/event/pause")
    res = player.post("/missions/hint")
    assert res.status_code == 409
    assert "not currently running" in res.get_json()["error"]

    client.post("/mod/event/start")
    res = player.post("/missions/hint")
    assert res.status_code == 200
    assert "hint" in res.get_json()


def test_broadcast_reaches_the_player_status_payload(client, app):
    _login_gm(client, app)
    client.post("/mod/event/start")

    with app.app_context():
        team = Team(name="Alpha", score=0, integrity=100)
        team.set_key("ALPHA01")
        db.session.add(team)
        db.session.commit()

    client.post("/mod/broadcast", data={"message": "Grid instability detected."})

    player_client = app.test_client()
    player_client.post("/auth/team-login", data={"name": "Alpha", "key": "ALPHA01"})
    status = player_client.get("/missions/status").get_json()
    assert status["broadcast"]["message"] == "Grid instability detected."


def test_game_master_can_add_and_remove_team_members(client, app):
    _login_gm(client, app)
    with app.app_context():
        team = Team(name="Alpha", score=0, integrity=100)
        team.set_key("ALPHA01")
        db.session.add(team)
        db.session.commit()
        team_id = team.id

    res = client.post(
        f"/mod/team/{team_id}/member", json={"name": "Ada Lovelace", "email": "ada@test.local"}
    )
    assert res.status_code == 201
    member_id = res.get_json()["id"]
    with app.app_context():
        assert TeamMember.query.get(member_id).name == "Ada Lovelace"

    res = client.delete(f"/mod/team/{team_id}/member/{member_id}")
    assert res.status_code == 200
    with app.app_context():
        assert TeamMember.query.get(member_id) is None


def test_game_master_can_set_a_teams_starting_booth(client, app):
    _login_gm(client, app)
    with app.app_context():
        team = Team(name="Alpha", score=0, integrity=100)
        team.set_key("ALPHA01")
        mission = Mission(
            title="Booth Two",
            type="code",
            narrative="n",
            cipher_word="X",
            booth_id=2,
            order_index=2,
        )
        db.session.add_all([team, mission])
        db.session.commit()
        team_id, mission_id = team.id, mission.id

    res = client.post(f"/mod/team/{team_id}/starting-booth", json={"mission_id": mission_id})
    assert res.status_code == 200
    with app.app_context():
        assert Team.query.get(team_id).starting_mission_id == mission_id

    # Clearing it back to the default (first booth) must also work.
    res = client.post(f"/mod/team/{team_id}/starting-booth", json={"mission_id": None})
    assert res.status_code == 200
    with app.app_context():
        assert Team.query.get(team_id).starting_mission_id is None


def test_game_master_override_marks_mission_overridden_and_awards_fragment(client, app):
    _login_gm(client, app)
    with app.app_context():
        team = Team(name="Alpha", score=0, integrity=100)
        team.set_key("ALPHA01")
        mission = Mission(
            title="Stuck Booth",
            type="code",
            narrative="n",
            cipher_word="X",
            booth_id=1,
            order_index=1,
        )
        db.session.add_all([team, mission])
        db.session.commit()
        tm = TeamMission(team_id=team.id, mission_id=mission.id, status="in_progress")
        db.session.add(tm)
        db.session.commit()
        team_mission_id = tm.id

    res = client.post(f"/mod/override/{team_mission_id}")
    assert res.status_code == 302
    with app.app_context():
        tm = TeamMission.query.get(team_mission_id)
        assert tm.status == "overridden"
        team = Team.query.get(tm.team_id)
        assert len(team.fragments) == 1


def test_game_master_override_rejected_once_already_resolved(client, app):
    _login_gm(client, app)
    with app.app_context():
        team = Team(name="Alpha", score=0, integrity=100)
        team.set_key("ALPHA01")
        mission = Mission(
            title="Stuck Booth",
            type="code",
            narrative="n",
            cipher_word="X",
            booth_id=1,
            order_index=1,
        )
        db.session.add_all([team, mission])
        db.session.commit()
        tm = TeamMission(team_id=team.id, mission_id=mission.id, status="passed")
        db.session.add(tm)
        db.session.commit()
        team_mission_id = tm.id

    res = client.post(f"/mod/override/{team_mission_id}")
    assert res.status_code == 409
