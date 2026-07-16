from app.extensions import db
from app.models import Challenge, CodeSubmission, Mission, Team, TeamMission, User


def _login_gm(client):
    res = client.post("/auth/login", data={"email": "gm@test.local", "password": "pw"})
    assert res.status_code in (302, 200)
    return res


def _setup(app):
    with app.app_context():
        gm = User(email="gm@test.local", role="game_master")
        gm.set_password("pw")
        team = Team(name="Alpha", score=10, integrity=100)
        team.set_key("A")
        db.session.add_all([gm, team])

        mission = Mission(
            title="Doubler Node", type="code", narrative="n", cipher_word="DOUBLE",
            booth_id=1, order_index=1,
        )
        db.session.add(mission)
        db.session.flush()
        challenge = Challenge(mission_id=mission.id, type="code", prompt="p", grading_mode="auto", difficulty="easy")
        db.session.add(challenge)
        db.session.flush()

        tm = TeamMission(team_id=team.id, mission_id=mission.id, status="passed")
        db.session.add(tm)
        db.session.flush()
        db.session.add(
            CodeSubmission(team_mission_id=tm.id, code="c", mode="submit", total_tests=2,
                            passed_tests=2, percent_score=100, passed=True)
        )
        db.session.commit()


def test_export_submissions_csv_contains_the_submission_row(client, app):
    _setup(app)
    _login_gm(client)
    res = client.get("/mod/export/submissions.csv")
    assert res.status_code == 200
    assert res.mimetype == "text/csv"
    body = res.get_data(as_text=True)
    assert "Alpha" in body
    assert "Doubler Node" in body
    assert "submit" in body


def test_export_challenges_csv_includes_difficulty_and_pass_rate(client, app):
    _setup(app)
    _login_gm(client)
    res = client.get("/mod/export/challenges.csv")
    assert res.status_code == 200
    body = res.get_data(as_text=True)
    assert "Doubler Node" in body
    assert "easy" in body
    assert "100.0" in body  # 1/1 submit attempts passed = 100.0% pass rate


def test_export_event_stats_csv_has_expected_metrics(client, app):
    _setup(app)
    _login_gm(client)
    res = client.get("/mod/export/event-stats.csv")
    assert res.status_code == 200
    body = res.get_data(as_text=True)
    assert "total_submissions" in body
    assert "submissions_passed" in body


def test_export_routes_require_game_master_role(client, app):
    _setup(app)
    # No login at all.
    assert client.get("/mod/export/submissions.csv").status_code in (302, 401, 403)
    assert client.get("/mod/export/challenges.csv").status_code in (302, 401, 403)
    assert client.get("/mod/export/event-stats.csv").status_code in (302, 401, 403)
