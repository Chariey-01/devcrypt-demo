from datetime import datetime, timedelta

from app.extensions import db
from app.models import Mission, Team, TeamMission, User


def _setup(app):
    with app.app_context():
        gm = User(email="gm@test.local", role="game_master")
        gm.set_password("pw")
        team = Team(name="Alpha", score=10, integrity=100)
        team.set_key("ALPHA01")
        db.session.add_all([gm, team])
        db.session.flush()

        mission = Mission(
            title="Doubler Node",
            type="code",
            narrative="Double the input.",
            cipher_word="DOUBLE",
            booth_id=1,
            order_index=1,
        )
        db.session.add(mission)
        db.session.flush()

        team_mission = TeamMission(
            team_id=team.id,
            mission_id=mission.id,
            status="in_progress",
            attempts=3,
            score=10,
            penalty_until=datetime.utcnow() + timedelta(minutes=5),
        )
        db.session.add(team_mission)
        db.session.commit()
        return team.id, team_mission.id


def _login_gm(client):
    res = client.post("/auth/login", data={"email": "gm@test.local", "password": "pw"})
    assert res.status_code in (302, 200)
    return res


def test_reset_mission_clears_cooldown_and_attempts(app, client):
    team_id, team_mission_id = _setup(app)
    _login_gm(client)

    res = client.post(f"/mod/reset-mission/{team_mission_id}")
    assert res.status_code == 302

    with app.app_context():
        tm = TeamMission.query.get(team_mission_id)
        assert tm.attempts == 0
        assert tm.penalty_until is None
        assert tm.submission_text is None
        assert tm.status == "in_progress"  # reset does not force-pass or wipe progress state


def test_reset_mission_rejected_once_passed(app, client):
    team_id, team_mission_id = _setup(app)
    with app.app_context():
        tm = TeamMission.query.get(team_mission_id)
        tm.status = "passed"
        db.session.commit()
    _login_gm(client)

    res = client.post(f"/mod/reset-mission/{team_mission_id}")
    assert res.status_code == 409


def test_override_score_updates_team_mission_and_team_totals(app, client):
    team_id, team_mission_id = _setup(app)
    _login_gm(client)

    res = client.post(f"/mod/override-score/{team_mission_id}", data={"score": "40"})
    assert res.status_code == 302

    with app.app_context():
        tm = TeamMission.query.get(team_mission_id)
        team = Team.query.get(team_id)
        assert tm.score == 40
        assert team.score == 40  # started at 10, +30 delta applied


def test_override_score_rejects_non_integer(app, client):
    team_id, team_mission_id = _setup(app)
    _login_gm(client)

    res = client.post(f"/mod/override-score/{team_mission_id}", data={"score": "not-a-number"})
    assert res.status_code == 400


def test_override_score_rejected_once_passed(app, client):
    team_id, team_mission_id = _setup(app)
    with app.app_context():
        tm = TeamMission.query.get(team_mission_id)
        tm.status = "passed"
        db.session.commit()
    _login_gm(client)

    res = client.post(f"/mod/override-score/{team_mission_id}", data={"score": "9999"})
    assert res.status_code == 409

    with app.app_context():
        tm = TeamMission.query.get(team_mission_id)
        team = Team.query.get(team_id)
        assert tm.score == 10  # untouched — a passed score is immutable through this route
        assert team.score == 10
