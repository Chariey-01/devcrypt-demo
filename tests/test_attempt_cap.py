from app.extensions import db
from app.models import Challenge, Event, Mission, Team, TeamMission


def _setup_flag_mission(app, max_attempts=1):
    with app.app_context():
        team = Team(name="Alpha", score=0, integrity=100)
        team.set_key("ALPHA01")
        db.session.add(team)
        db.session.add(Event(status="running"))
        db.session.commit()

        mission = Mission(
            title="Trailing Node",
            type="flag",
            narrative="unused",
            cipher_word="TRAIL",
            booth_id=1,
            order_index=1,
        )
        db.session.add(mission)
        db.session.flush()

        challenge = Challenge(
            mission_id=mission.id,
            type="flag",
            prompt="Find the flag.",
            grading_mode="manual_review",
            answer_key="FLAG{RIGHT}",
            max_attempts=max_attempts,
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
