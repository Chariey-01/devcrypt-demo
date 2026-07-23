from app.extensions import db
from app.models import Challenge, EventState, Mission, Team, TeamMission, TestCase, User


def _setup(app, soft_lock_min_attempts=1):
    with app.app_context():
        gm = User(email="gm@test.local", role="game_master")
        gm.set_password("pw")
        team = Team(name="Alpha", score=0, integrity=100)
        team.set_key("ALPHA01")
        db.session.add_all([gm, team])
        db.session.add(EventState(status="running", soft_lock_min_attempts=soft_lock_min_attempts))
        db.session.commit()

        mission = Mission(
            title="Stuck Node", type="code", narrative="n", cipher_word="STUCK",
            booth_id=1, order_index=1,
        )
        db.session.add(mission)
        db.session.flush()
        challenge = Challenge(mission_id=mission.id, type="code", prompt="Double it.", grading_mode="auto")
        db.session.add(challenge)
        db.session.flush()
        db.session.add(
            TestCase(
                challenge_id=challenge.id, name="case", input_data="3", expected_output="6",
                weight=1, visibility="visible", order_index=0,
            )
        )
        db.session.add(
            Mission(
                title="Next Node", type="code", narrative="n", cipher_word="NEXT",
                booth_id=2, order_index=2,
            )
        )
        db.session.commit()
        return mission.id, team.id


def _login_team(client):
    return client.post("/auth/team-login", data={"name": "Alpha", "key": "ALPHA01"})


def _login_gm(client):
    res = client.post("/auth/login", data={"email": "gm@test.local", "password": "pw"})
    assert res.status_code in (302, 200)


def _fail_once(client, team_id, mission_id, app):
    res = client.post("/missions/challenge/submit", json={"code": "n = int(input())\nprint(0)\n"})
    assert res.get_json()["correct"] is False
    with app.app_context():
        tm = TeamMission.query.filter_by(team_id=team_id, mission_id=mission_id).first()
        tm.penalty_until = None
        db.session.commit()


def test_soft_lock_blocked_before_min_attempts_reached(client, app):
    mission_id, team_id = _setup(app, soft_lock_min_attempts=2)
    _login_team(client)
    # 0 attempts so far -> below the configured threshold of 2
    res = client.post("/missions/soft-lock")
    assert res.status_code == 403


def test_soft_lock_succeeds_after_min_attempts_awards_participation_only(client, app):
    mission_id, team_id = _setup(app, soft_lock_min_attempts=1)
    _login_team(client)
    _fail_once(client, team_id, mission_id, app)

    res = client.post("/missions/soft-lock")
    assert res.status_code == 200
    assert res.get_json()["ok"] is True

    with app.app_context():
        tm = TeamMission.query.filter_by(team_id=team_id, mission_id=mission_id).first()
        team = Team.query.filter_by(name="Alpha").first()
        assert tm.status == "soft_locked"
        assert tm.score == 5  # SOFT_LOCK_PARTICIPATION
        assert team.score == 5
        assert len(team.fragments) == 0

    status = client.get("/missions/status").get_json()
    assert status["mission"]["title"] == "Next Node"  # advanced past the soft-locked booth
    assert status["fragments"] == []
    assert any(t["status"] == "soft_locked" for t in status["timeline"])


def test_soft_lock_cannot_be_applied_twice(client, app):
    mission_id, team_id = _setup(app, soft_lock_min_attempts=1)
    _login_team(client)
    _fail_once(client, team_id, mission_id, app)
    client.post("/missions/soft-lock")

    with app.app_context():
        team = Team.query.filter_by(name="Alpha").first()
        score_after_first = team.score

    # The team has already advanced past mission_id, so a second call operates on the *new*
    # current mission ("Next Node") -- to prove the old one specifically can't be re-locked or
    # farmed, hit soft-lock repeatedly and confirm the score for the already-resolved booth
    # never moves again.
    client.post("/missions/soft-lock")  # would apply to "Next Node" now, not the old booth
    with app.app_context():
        tm = TeamMission.query.filter_by(team_id=team_id, mission_id=mission_id).first()
        assert tm.score == 5  # unchanged — soft-locking a *different* booth doesn't touch this one


def test_soft_lock_cannot_be_applied_to_an_already_passed_mission(client, app):
    mission_id, team_id = _setup(app, soft_lock_min_attempts=1)
    _login_team(client)
    client.post("/missions/challenge/submit", json={"code": "n = int(input())\nprint(n * 2)\n"})

    res = client.post("/missions/soft-lock")
    assert res.status_code == 403  # attempts is 0 for the *new* current mission ("Next Node")


def test_gm_cannot_override_score_or_reset_a_soft_locked_mission(client, app):
    mission_id, team_id = _setup(app, soft_lock_min_attempts=1)
    _login_team(client)
    _fail_once(client, team_id, mission_id, app)
    client.post("/missions/soft-lock")

    with app.app_context():
        tm_id = TeamMission.query.filter_by(team_id=team_id, mission_id=mission_id).first().id

    gm_client = app.test_client()
    _login_gm(gm_client)

    assert gm_client.post(f"/mod/override-score/{tm_id}", data={"score": "999"}).status_code == 409
    assert gm_client.post(f"/mod/reset-mission/{tm_id}").status_code == 409
    assert gm_client.post(f"/mod/override/{tm_id}").status_code == 409

    with app.app_context():
        tm = TeamMission.query.get(tm_id)
        assert tm.status == "soft_locked"
        assert tm.score == 5


def test_leaderboard_and_gm_dashboard_indicate_soft_lock(client, app):
    mission_id, team_id = _setup(app, soft_lock_min_attempts=1)
    _login_team(client)
    _fail_once(client, team_id, mission_id, app)
    client.post("/missions/soft-lock")

    board = client.get("/leaderboard/data").get_json()
    row = next(r for r in board["leaderboard"] if r["team"] == "Alpha")
    assert row["soft_locked_count"] == 1

    gm_client = app.test_client()
    _login_gm(gm_client)
    data = gm_client.get("/mod/data").get_json()
    team_row = next(t for t in data["teams"] if t["name"] == "Alpha")
    assert team_row["soft_locked_missions"] == ["Stuck Node"]
