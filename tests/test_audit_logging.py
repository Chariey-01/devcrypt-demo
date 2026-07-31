from app.extensions import db
from app.models import Challenge, EventLog, Event, Hint, Mission, Team, User


def _login_gm(client):
    res = client.post("/auth/login", data={"email": "gm@test.local", "password": "pw"})
    assert res.status_code in (302, 200)
    return res


def _login_team(client, name="Alpha", key="ALPHA01"):
    res = client.post("/auth/team-login", data={"name": name, "key": key})
    assert res.status_code in (302, 200)
    return res


def _setup_mission_with_hints(app, hint_count=1):
    with app.app_context():
        gm = User(email="gm@test.local", role="game_master")
        gm.set_password("pw")
        team = Team(name="Alpha", score=0, integrity=100)
        team.set_key("ALPHA01")
        db.session.add_all([gm, team])
        db.session.add(Event(status="running"))
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
        for i in range(hint_count):
            db.session.add(Hint(challenge_id=challenge.id, order_index=i, text=f"hint {i}"))
        db.session.commit()
        return mission.id, team.id


def test_mission_opened_is_audit_logged_on_first_touch(client, app):
    mission_id, team_id = _setup_mission_with_hints(app)
    _login_team(client)
    client.get("/missions/status")  # first poll -- creates the TeamMission row

    with app.app_context():
        log = EventLog.query.filter_by(action="mission_opened").first()
        assert log is not None
        assert log.team_id == team_id
        assert "Alpha" in log.event_metadata


def test_hint_requested_is_audit_logged_with_team_and_score_delta(client, app):
    from app.services.scoring_service import ScoringService

    mission_id, team_id = _setup_mission_with_hints(app)
    _login_team(client)
    client.get("/missions/status")

    res = client.post("/missions/hint")
    assert res.status_code == 200

    with app.app_context():
        log = EventLog.query.filter_by(action="hint_requested").first()
        assert log is not None
        assert log.team_id == team_id
        assert log.score_delta == -ScoringService.HINT_PENALTY
        assert "Alpha" in log.event_metadata


def test_team_detail_page_picks_up_logs_via_team_id(client, app):
    mission_id, team_id = _setup_mission_with_hints(app)
    _login_team(client)
    client.get("/missions/status")
    client.post("/missions/hint")

    gm_client = app.test_client()
    _login_gm(gm_client)
    res = gm_client.get(f"/mod/team/{team_id}")
    assert res.status_code == 200
    assert b"hint_requested" in res.data
    assert b"mission_opened" in res.data


def test_activity_json_includes_team_result_and_score_delta(client, app):
    mission_id, team_id = _setup_mission_with_hints(app)
    _login_team(client)
    client.get("/missions/status")
    client.post("/missions/hint")

    gm_client = app.test_client()
    _login_gm(gm_client)
    res = gm_client.get("/mod/activity")
    assert res.status_code == 200
    logs = res.get_json()["logs"]
    hint_log = next(l for l in logs if l["action"] == "hint_requested")
    assert hint_log["team"] == "Alpha"
    assert hint_log["score_delta"] < 0


def test_reissuing_a_teams_key_is_logged_distinctly_from_creating_a_new_team(client, app):
    with app.app_context():
        gm = User(email="gm@test.local", role="game_master")
        gm.set_password("pw")
        team = Team(name="Alpha", score=0, integrity=100)
        team.set_key("ALPHA01")
        db.session.add_all([gm, team])
        db.session.commit()
        team_id = team.id

    _login_gm(client)
    # Existing team -- a key reissue (the live-event recovery scenario), not a fresh team.
    res = client.post("/mod/credentials/generate", json={"kind": "team", "name": "Alpha"})
    assert res.status_code == 200

    # Brand-new team name -- a genuine creation.
    res = client.post("/mod/credentials/generate", json={"kind": "team", "name": "Bravo"})
    assert res.status_code == 200

    with app.app_context():
        assert EventLog.query.filter_by(action="team_key_reissued", team_id=team_id).count() == 1
        bravo = Team.query.filter_by(name="Bravo").first()
        assert EventLog.query.filter_by(action="team_created_with_key", team_id=bravo.id).count() == 1
