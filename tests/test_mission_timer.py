from datetime import datetime, timedelta

from app.extensions import db
from app.models import Challenge, EventState, Mission, Team, TeamMission, TestCase, User


def _setup_timed_mission(app, time_limit=300, grading_mode="auto", challenge_type="code", event_status="running"):
    with app.app_context():
        agent = User(email="agent@test.local", role="booth_agent")
        agent.set_password("pw")
        gm = User(email="gm@test.local", role="game_master")
        gm.set_password("pw")
        team = Team(name="Alpha", score=0, integrity=100)
        team.set_key("ALPHA01")
        db.session.add_all([agent, gm, team])
        db.session.add(EventState(status=event_status))
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


def test_mission_timer_does_not_start_before_the_event_is_running(client, app):
    # The actual "overdue immediately after login" bug: a team browsing the dashboard before
    # the Game Master starts the event used to stamp started_at right away, so the clock had
    # already been running (and could already be past time_limit) the moment the event began.
    mission_id, team_id = _setup_timed_mission(app, time_limit=60, event_status="not_started")
    _login_team(client)
    res = client.get("/missions/status")
    assert res.get_json()["mission"]["started_at"] is None

    with app.app_context():
        tm = TeamMission.query.filter_by(team_id=team_id, mission_id=mission_id).first()
        assert tm is not None  # row exists (attempts/hints tracked) even though the clock hasn't started
        assert tm.started_at is None


def test_mission_timer_starts_on_the_first_poll_once_the_event_goes_running(client, app):
    mission_id, team_id = _setup_timed_mission(app, time_limit=60, event_status="not_started")
    _login_team(client)
    client.get("/missions/status")  # creates the row, event not running yet -> started_at stays None

    with app.app_context():
        state = EventState.query.get(1)
        state.status = "running"
        db.session.commit()

    res = client.get("/missions/status")
    assert res.get_json()["mission"]["started_at"] is not None
    with app.app_context():
        tm = TeamMission.query.filter_by(team_id=team_id, mission_id=mission_id).first()
        assert tm.started_at is not None


def test_pausing_and_resuming_the_event_preserves_remaining_time(client, app):
    mission_id, team_id = _setup_timed_mission(app, time_limit=300)
    _login_team(client)
    client.get("/missions/status")
    _start_mission_and_backdate(app, team_id, mission_id, seconds_ago=30)

    gm_client = app.test_client()
    _login_staff(gm_client, "gm@test.local")
    gm_client.post("/mod/event/pause")

    with app.app_context():
        state = EventState.query.get(1)
        assert state.status == "paused"
        assert state.paused_at is not None
        # Backdate the pause itself so the resume below has a deterministic, non-zero gap to
        # shift started_at by, without sleeping in the test.
        state.paused_at = datetime.utcnow() - timedelta(seconds=20)
        db.session.commit()
        started_before_resume = TeamMission.query.filter_by(
            team_id=team_id, mission_id=mission_id
        ).first().started_at

    gm_client.post("/mod/event/start")

    with app.app_context():
        state = EventState.query.get(1)
        assert state.status == "running"
        assert state.paused_at is None
        tm = TeamMission.query.filter_by(team_id=team_id, mission_id=mission_id).first()
        shift = (tm.started_at - started_before_resume).total_seconds()
        assert 18 <= shift <= 22  # shifted forward by ~the paused duration, not reset/left alone


def test_pausing_does_not_stamp_a_mission_a_team_has_not_reached_yet(client, app):
    # A team who hasn't polled /missions/status at all during the pause has no TeamMission row
    # to shift -- resuming must not retroactively create/start one for them.
    mission_id, team_id = _setup_timed_mission(app, time_limit=300, event_status="paused")
    with app.app_context():
        state = EventState.query.get(1)
        state.paused_at = datetime.utcnow() - timedelta(seconds=10)
        db.session.commit()

    gm_client = app.test_client()
    _login_staff(gm_client, "gm@test.local")
    gm_client.post("/mod/event/start")

    with app.app_context():
        tm = TeamMission.query.filter_by(team_id=team_id, mission_id=mission_id).first()
        assert tm is None


def test_extend_timer_grants_extra_time_to_a_single_team(client, app):
    mission_id, team_id = _setup_timed_mission(app, time_limit=60)
    _login_team(client)
    client.get("/missions/status")
    _start_mission_and_backdate(app, team_id, mission_id, seconds_ago=50)

    with app.app_context():
        tm = TeamMission.query.filter_by(team_id=team_id, mission_id=mission_id).first()
        team_mission_id = tm.id
        started_before = tm.started_at

    gm_client = app.test_client()
    _login_staff(gm_client, "gm@test.local")
    res = gm_client.post(f"/mod/team-mission/{team_mission_id}/extend-timer", data={"seconds": "300"})
    assert res.status_code == 302

    with app.app_context():
        tm = TeamMission.query.get(team_mission_id)
        assert (tm.started_at - started_before).total_seconds() == 300


def test_extend_timer_is_a_no_op_once_the_mission_is_submitted(client, app):
    mission_id, team_id = _setup_timed_mission(app, time_limit=60)
    _login_team(client)
    client.get("/missions/status")
    _start_mission_and_backdate(app, team_id, mission_id, seconds_ago=10)
    client.post("/missions/challenge/submit", json={"code": "print(int(input()) * 2)"})

    with app.app_context():
        tm = TeamMission.query.filter_by(team_id=team_id, mission_id=mission_id).first()
        team_mission_id = tm.id

    gm_client = app.test_client()
    _login_staff(gm_client, "gm@test.local")
    res = gm_client.post(f"/mod/team-mission/{team_mission_id}/extend-timer", data={"seconds": "300"})
    assert res.status_code == 409
