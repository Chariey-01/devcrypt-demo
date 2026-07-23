from datetime import datetime, timedelta

from app.extensions import db
from app.models import Challenge, EventState, Mission, Team, TeamMission, TestCase, User


def _setup_timed_mission(app, time_limit=300, grading_mode="auto", challenge_type="code"):
    with app.app_context():
        agent = User(email="agent@test.local", role="booth_agent")
        agent.set_password("pw")
        gm = User(email="gm@test.local", role="game_master")
        gm.set_password("pw")
        team = Team(name="Alpha", score=0, integrity=100)
        team.set_key("ALPHA01")
        db.session.add_all([agent, gm, team])
        db.session.add(EventState(status="running"))
        db.session.commit()

        mission = Mission(
            title="Timed Node",
            type="code",
            narrative="Race the clock.",
            cipher_word="RACE",
            booth_id=1,
            order_index=1,
            owner_agent_id=agent.id,
            time_limit=time_limit,
        )
        db.session.add(mission)
        db.session.flush()

        challenge = Challenge(
            mission_id=mission.id,
            type=challenge_type,
            prompt="Double the input.",
            grading_mode=grading_mode,
            pass_threshold=100,
        )
        db.session.add(challenge)
        db.session.flush()

        if grading_mode == "auto":
            db.session.add(
                TestCase(
                    challenge_id=challenge.id,
                    name="case",
                    input_data="3",
                    expected_output="6",
                    weight=1,
                    visibility="visible",
                    order_index=0,
                )
            )
        db.session.commit()
        return mission.id, team.id


def _login_team(client):
    return client.post("/auth/team-login", data={"name": "Alpha", "key": "ALPHA01"})


def _login_staff(client, email):
    return client.post("/auth/login", data={"email": email, "password": "pw"})


def _start_mission_and_backdate(app, team_id, mission_id, seconds_ago):
    # Forces a real TeamMission row to exist (mirrors get_or_create_team_mission), then
    # backdates started_at so elapsed time is deterministic without sleeping in tests.
    with app.app_context():
        tm = TeamMission.query.filter_by(team_id=team_id, mission_id=mission_id).first()
        if tm is None:
            tm = TeamMission(team_id=team_id, mission_id=mission_id, status="in_progress")
            db.session.add(tm)
        tm.started_at = datetime.utcnow() - timedelta(seconds=seconds_ago)
        db.session.commit()
        return tm.id


def test_on_time_submission_freezes_elapsed_and_remaining(client, app):
    mission_id, team_id = _setup_timed_mission(app, time_limit=300)
    _login_team(client)
    client.get("/missions/status")  # creates the TeamMission row
    _start_mission_and_backdate(app, team_id, mission_id, seconds_ago=60)

    res = client.post("/missions/challenge/submit", json={"code": "print(int(input()) * 2)"})
    assert res.get_json()["correct"] is True

    with app.app_context():
        tm = TeamMission.query.filter_by(team_id=team_id, mission_id=mission_id).first()
        assert tm.submitted_at is not None
        assert 59 <= tm.elapsed_seconds <= 61
        assert 239 <= tm.time_remaining <= 241
        assert tm.submission_status == "on_time"
        assert tm.grading_status == "graded"


def test_overtime_submission_is_recorded_but_still_completes(client, app):
    mission_id, team_id = _setup_timed_mission(app, time_limit=60)
    _login_team(client)
    client.get("/missions/status")
    _start_mission_and_backdate(app, team_id, mission_id, seconds_ago=90)

    res = client.post("/missions/challenge/submit", json={"code": "print(int(input()) * 2)"})
    assert res.get_json()["correct"] is True

    with app.app_context():
        tm = TeamMission.query.filter_by(team_id=team_id, mission_id=mission_id).first()
        assert tm.submission_status == "overtime"
        assert tm.time_remaining < 0
        assert tm.status == "passed"  # overtime still completes the mission; scoring just
        # withholds the on-time bonus (covered by test_scoring.py's own bonus assertions).


def test_grading_duration_does_not_inflate_recorded_elapsed_time(client, app, monkeypatch):
    mission_id, team_id = _setup_timed_mission(app, time_limit=300)
    _login_team(client)
    client.get("/missions/status")
    _start_mission_and_backdate(app, team_id, mission_id, seconds_ago=10)

    import app.blueprints.missions as missions_module

    real_run_all_tests = missions_module.grading_engine.run_all_tests

    def slow_run_all_tests(challenge, code):
        # Simulates a slow sandboxed grading pass — the recorded elapsed time must reflect
        # when the submission arrived, not when this returns.
        import time

        time.sleep(1.5)
        return real_run_all_tests(challenge, code)

    monkeypatch.setattr(missions_module.grading_engine, "run_all_tests", slow_run_all_tests)

    res = client.post("/missions/challenge/submit", json={"code": "print(int(input()) * 2)"})
    assert res.get_json()["correct"] is True

    with app.app_context():
        tm = TeamMission.query.filter_by(team_id=team_id, mission_id=mission_id).first()
        # ~10s elapsed at submission time, not ~11.5s (10s + the 1.5s grading delay).
        assert tm.elapsed_seconds < 11


def test_game_master_reset_mission_also_resets_timer(client, app):
    mission_id, team_id = _setup_timed_mission(app, time_limit=300)
    _login_team(client)
    client.get("/missions/status")
    _start_mission_and_backdate(app, team_id, mission_id, seconds_ago=45)
    client.post("/missions/challenge/submit", json={"code": "def f(): return 1"})

    team_mission_id = None
    with app.app_context():
        tm = TeamMission.query.filter_by(team_id=team_id, mission_id=mission_id).first()
        team_mission_id = tm.id

    gm_client = app.test_client()
    _login_staff(gm_client, "gm@test.local")
    gm_client.post(f"/mod/reset-mission/{team_mission_id}")

    with app.app_context():
        tm = TeamMission.query.get(team_mission_id)
        assert tm.submitted_at is None
        assert tm.grading_status is None
        assert tm.submission_text is None
        assert tm.attempts == 0
