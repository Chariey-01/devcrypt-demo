from app.extensions import db
from app.models import TeamMission, User
from tests.test_auto_grading_flow import _login_team, _setup_auto_graded_mission


def _login_agent(client, email="agent@test.local"):
    return client.post("/auth/login", data={"email": email, "password": "pw"})


def test_agent_sees_graded_submission_with_visible_hidden_breakdown(client, app):
    _setup_auto_graded_mission(app)
    _login_team(client)
    client.post("/missions/challenge/submit", json={"code": "print(int(input()) * 2)"})

    agent_client = app.test_client()
    _login_agent(agent_client)
    res = agent_client.get("/agent/submissions")
    assert res.status_code == 200
    rows = res.get_json()["submissions"]
    assert len(rows) == 1
    row = rows[0]
    assert row["team"] == "Alpha"
    assert row["passed"] is True
    assert row["visible_total"] == 1
    assert row["hidden_total"] == 1
    assert row["visible_passed"] == 1
    assert row["hidden_passed"] == 1
    assert row["team_mission_status"] == "passed"
    assert "print(int(input())" in row["code"]


def test_agent_does_not_see_another_agents_submissions(client, app):
    _setup_auto_graded_mission(app)
    _login_team(client)
    client.post("/missions/challenge/submit", json={"code": "print(int(input()) * 2)"})

    with app.app_context():
        other_agent = User(email="other-agent@test.local", role="booth_agent")
        other_agent.set_password("pw")
        db.session.add(other_agent)
        db.session.commit()

    other_client = app.test_client()
    _login_agent(other_client, "other-agent@test.local")
    res = other_client.get("/agent/submissions")
    assert res.get_json()["submissions"] == []


def test_agent_has_no_override_capability(client, app):
    # Agents are grading-free monitors under the current spec — no override route exists at
    # all anymore (that capability now belongs solely to the Game Master, mod.py).
    mission_id, team_id = _setup_auto_graded_mission(app)
    with app.app_context():
        tm = TeamMission(team_id=team_id, mission_id=mission_id, status="in_progress")
        db.session.add(tm)
        db.session.commit()
        team_mission_id = tm.id

    agent_client = app.test_client()
    _login_agent(agent_client)
    res = agent_client.post(f"/agent/team-missions/{team_mission_id}/override")
    assert res.status_code == 404
