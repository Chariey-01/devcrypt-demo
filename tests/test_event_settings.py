from app.extensions import db
from app.models import Challenge, EventState, Mission, Team, TestCase, User


def _login_gm(client):
    res = client.post("/auth/login", data={"email": "gm@test.local", "password": "pw"})
    assert res.status_code in (302, 200)
    return res


def _login_team(client, name="Alpha", key="ALPHA01"):
    res = client.post("/auth/team-login", data={"name": name, "key": key})
    assert res.status_code in (302, 200)
    return res


def _setup_auto_graded_mission(app, hint_limit=3, leaderboard_public=True):
    with app.app_context():
        gm = User(email="gm@test.local", role="game_master")
        gm.set_password("pw")
        team = Team(name="Alpha", score=0, integrity=100)
        team.set_key("ALPHA01")
        db.session.add_all([gm, team])
        db.session.add(
            EventState(
                status="running",
                hint_limit=hint_limit,
                leaderboard_public=leaderboard_public,
            )
        )
        db.session.commit()

        mission = Mission(
            title="Doubler Node", type="code", narrative="n", cipher_word="DOUBLE",
            booth_id=1, order_index=1,
        )
        db.session.add(mission)
        db.session.flush()
        challenge = Challenge(mission_id=mission.id, type="code", prompt="Double it.",
                               grading_mode="auto", pass_threshold=100)
        db.session.add(challenge)
        db.session.flush()
        db.session.add(
            TestCase(challenge_id=challenge.id, name="case", input_data="3", expected_output="6",
                      weight=1, visibility="visible", order_index=0)
        )
        db.session.commit()
        return mission.id, team.id


def test_hint_limit_reflects_configured_value_in_status(client, app):
    _setup_auto_graded_mission(app, hint_limit=1)
    _login_team(client)
    status = client.get("/missions/status").get_json()
    assert status["team"]["hints_remaining"] == 1


def test_hint_limit_enforced_at_configured_value(client, app):
    _setup_auto_graded_mission(app, hint_limit=0)
    _login_team(client)
    res = client.post("/missions/hint")
    assert res.status_code == 403


def test_leaderboard_public_false_hides_team_data(client, app):
    _setup_auto_graded_mission(app, leaderboard_public=False)
    res = client.get("/leaderboard/data")
    body = res.get_json()
    assert body["hidden"] is True
    assert body["leaderboard"] == []


def test_leaderboard_public_false_does_not_affect_gm_dashboard(client, app):
    _setup_auto_graded_mission(app, leaderboard_public=False)
    _login_gm(client)
    res = client.get("/mod/data")
    body = res.get_json()
    assert len(body["teams"]) == 1
    assert body["teams"][0]["name"] == "Alpha"


def test_finished_threshold_tracks_actual_published_mission_count(client, app):
    # Only one published mission exists — passing it alone should be enough to finish.
    mission_id, team_id = _setup_auto_graded_mission(app)
    _login_team(client)
    client.post("/missions/challenge/submit", json={"code": "print(int(input()) * 2)"})

    data = client.get("/leaderboard/data").get_json()
    row = next(r for r in data["leaderboard"] if r["team"] == "Alpha")
    assert row["status"] == "finished"
    assert data["total_missions"] == 1


def test_event_settings_get_and_post(client, app):
    _setup_auto_graded_mission(app)
    _login_gm(client)

    res = client.get("/mod/event-settings")
    assert res.status_code == 200

    res = client.post(
        "/mod/event-settings",
        data={"name": "Career Fair 2026", "description": "desc", "hint_limit": "5", "leaderboard_public": "on"},
    )
    assert res.status_code == 302

    with app.app_context():
        state = EventState.query.get(1)
        assert state.name == "Career Fair 2026"
        assert state.hint_limit == 5
        assert state.leaderboard_public is True
