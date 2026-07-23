from app.extensions import db
from app.models import ClearanceStamp, EventLog, Team, User


def _login_officer(client, app):
    with app.app_context():
        officer = User(email="officer@test.local", role="security_officer")
        officer.set_password("pw")
        db.session.add(officer)
        db.session.commit()
    return client.post("/auth/login", data={"email": "officer@test.local", "password": "pw"})


def test_issuing_a_clearance_stamp_never_changes_score(client, app):
    _login_officer(client, app)
    with app.app_context():
        team = Team(name="Alpha", score=0, integrity=100)
        team.set_key("ALPHA01")
        db.session.add(team)
        db.session.commit()
        team_id = team.id

    res = client.post("/security/stamp", data={"team_id": team_id, "checkpoint_id": 1, "notes": "ok"})
    assert res.status_code == 302

    with app.app_context():
        team = Team.query.get(team_id)
        assert team.score == 0  # audit record only — must never award points
        assert ClearanceStamp.query.filter_by(team_id=team_id, checkpoint_id=1).count() == 1
        logged = EventLog.query.filter_by(action="clearance_stamp").first()
        assert logged is not None
        assert logged.actor_role == "security_officer"


def test_cannot_stamp_the_same_checkpoint_twice(client, app):
    _login_officer(client, app)
    with app.app_context():
        team = Team(name="Alpha", score=0, integrity=100)
        team.set_key("ALPHA01")
        db.session.add(team)
        db.session.commit()
        team_id = team.id

    client.post("/security/stamp", data={"team_id": team_id, "checkpoint_id": 1})
    client.post("/security/stamp", data={"team_id": team_id, "checkpoint_id": 1})

    with app.app_context():
        assert ClearanceStamp.query.filter_by(team_id=team_id, checkpoint_id=1).count() == 1


def test_security_officer_routes_require_the_role(client, app):
    assert client.get("/security/").status_code in (302, 401, 403)
    assert client.get("/security/data").status_code in (302, 401, 403)
    assert client.post("/security/stamp", data={"team_id": 1, "checkpoint_id": 1}).status_code in (302, 401, 403)
