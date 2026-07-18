from datetime import datetime, timedelta

from app.extensions import db
from app.models import Challenge, EventState, Mission, Team, TeamMission, User


def _setup_flag_mission(app, max_attempts=1):
    with app.app_context():
        team = Team(name="Alpha", score=0, integrity=100)
        team.set_key("ALPHA01")
        db.session.add(team)
        db.session.add(EventState(status="running"))
        db.session.commit()

        mission = Mission(
            title="Trailing Node", type="flag", narrative="unused",
            cipher_word="TRAIL", booth_id=1, order_index=1,
        )
        db.session.add(mission)
        db.session.flush()

        challenge = Challenge(
            mission_id=mission.id, type="flag", prompt="Find the flag.",
            grading_mode="manual_review", answer_key="FLAG{RIGHT}", max_attempts=max_attempts,
        )
        db.session.add(challenge)
        db.session.commit()
        return mission.id, team.id


def _setup_manual_code_mission(app, max_attempts=1):
    with app.app_context():
        team = Team(name="Alpha", score=0, integrity=100)
        team.set_key("ALPHA01")
        db.session.add(team)
        db.session.add(EventState(status="running"))
        db.session.commit()

        mission = Mission(
            title="Legacy Node", type="code", narrative="unused",
            cipher_word="LEGACY", booth_id=1, order_index=1,
        )
        db.session.add(mission)
        db.session.flush()

        challenge = Challenge(
            mission_id=mission.id, type="code", prompt="Fix the bug.",
            grading_mode="manual_review", max_attempts=max_attempts,
        )
        db.session.add(challenge)
        db.session.commit()
        return mission.id, team.id


def _login(client):
    return client.post("/auth/team-login", data={"name": "Alpha", "key": "ALPHA01"})


def _clear_cooldown(app, team_id, mission_id):
    with app.app_context():
        tm = TeamMission.query.filter_by(team_id=team_id, mission_id=mission_id).first()
        tm.penalty_until = None
        db.session.commit()


def test_flag_challenge_blocks_after_max_attempts(app, client):
    mission_id, team_id = _setup_flag_mission(app, max_attempts=1)
    _login(client)

    res = client.post("/missions/challenge/submit", json={"answer": "FLAG{WRONG}"})
    assert res.status_code == 200
    assert res.get_json()["correct"] is False

    _clear_cooldown(app, team_id, mission_id)

    res = client.post("/missions/challenge/submit", json={"answer": "FLAG{RIGHT}"})
    assert res.status_code == 403


def test_flag_challenge_without_max_attempts_is_unlimited(app, client):
    mission_id, team_id = _setup_flag_mission(app, max_attempts=None)
    _login(client)

    for _ in range(3):
        res = client.post("/missions/challenge/submit", json={"answer": "FLAG{WRONG}"})
        assert res.status_code == 200
        _clear_cooldown(app, team_id, mission_id)

    res = client.post("/missions/challenge/submit", json={"answer": "FLAG{RIGHT}"})
    assert res.status_code == 200
    assert res.get_json()["correct"] is True


def test_manual_review_code_challenge_blocks_after_agent_retries_exhaust_attempts(app, client):
    mission_id, team_id = _setup_manual_code_mission(app, max_attempts=1)
    with app.app_context():
        agent = User(email="agent@test.local", role="booth_agent")
        agent.set_password("pw")
        db.session.add(agent)
        db.session.commit()

    team_client = app.test_client()
    _login(team_client)
    res = team_client.post("/missions/challenge/submit", json={"code": "buggy code v1"})
    assert res.status_code == 200
    assert res.get_json()["queued"] is True

    agent_client = app.test_client()
    agent_client.post("/auth/login", data={"email": "agent@test.local", "password": "pw"})
    agent_client.post("/booth/select", data={"mission_id": mission_id})
    with app.app_context():
        tm_id = TeamMission.query.filter_by(team_id=team_id, mission_id=mission_id).first().id
    booth_res = agent_client.post(f"/booth/submission/{tm_id}/retry")
    assert booth_res.status_code == 200

    _clear_cooldown(app, team_id, mission_id)
    res = team_client.post("/missions/challenge/submit", json={"code": "buggy code v2"})
    assert res.status_code == 403
