from app.extensions import db
from app.models import Challenge, EventState, Mission, Team, TestCase, User


def _setup_auto_graded_mission(app):
    with app.app_context():
        agent = User(email="agent@test.local", role="booth_agent")
        agent.set_password("pw")
        team = Team(name="Alpha", score=0, integrity=100)
        team.set_key("ALPHA01")
        db.session.add_all([agent, team])
        db.session.add(EventState(status="running"))
        db.session.commit()

        mission = Mission(
            title="Doubler Node",
            type="code",
            narrative="Double the input.",
            cipher_word="DOUBLE",
            booth_id=1,
            order_index=1,
            owner_agent_id=agent.id,
        )
        db.session.add(mission)
        db.session.flush()

        challenge = Challenge(
            mission_id=mission.id,
            type="code",
            prompt="Read an integer and print double it.",
            grading_mode="auto",
            pass_threshold=100,
        )
        db.session.add(challenge)
        db.session.flush()

        db.session.add_all(
            [
                TestCase(
                    challenge_id=challenge.id,
                    name="visible case",
                    input_data="3",
                    expected_output="6",
                    weight=1,
                    visibility="visible",
                    order_index=0,
                ),
                TestCase(
                    challenge_id=challenge.id,
                    name="hidden case",
                    input_data="5",
                    expected_output="10",
                    weight=1,
                    visibility="hidden",
                    order_index=1,
                ),
            ]
        )
        db.session.add(
            Mission(
                title="Trailing Node",
                type="flag",
                narrative="unused",
                cipher_word="TRAIL",
                booth_id=2,
                order_index=2,
            )
        )
        db.session.commit()
        return mission.id, team.id


def _login_team(client):
    return client.post("/auth/team-login", data={"name": "Alpha", "key": "ALPHA01"})


def test_run_visible_tests_only_returns_visible_case(client, app):
    _setup_auto_graded_mission(app)
    _login_team(client)

    res = client.post("/missions/challenge/run-tests", json={"code": "print(int(input()) * 2)"})
    assert res.status_code == 200
    body = res.get_json()
    assert body["total_tests"] == 1
    assert body["results"][0]["name"] == "visible case"
    assert body["results"][0]["passed"] is True
    assert all(r["name"] != "hidden case" for r in body["results"])


def test_submit_solution_grades_all_tests_and_awards_fragment(client, app):
    _setup_auto_graded_mission(app)
    _login_team(client)

    res = client.post("/missions/challenge/submit", json={"code": "print(int(input()) * 2)"})
    assert res.status_code == 200
    body = res.get_json()
    assert body["correct"] is True
    assert body["percent_score"] == 100
    assert body["passed_tests"] == 2
    assert body["total_tests"] == 2

    status = client.get("/missions/status").get_json()
    assert len(status["fragments"]) == 1


def test_submit_wrong_solution_applies_cooldown_not_pass(client, app):
    _setup_auto_graded_mission(app)
    _login_team(client)

    res = client.post("/missions/challenge/submit", json={"code": "print(int(input()) + 1)"})
    assert res.status_code == 200
    body = res.get_json()
    assert body["correct"] is False
    assert body["percent_score"] == 0

    status = client.get("/missions/status").get_json()
    assert status["mission"]["status"] == "in_progress"
    assert status["fragments"] == []


def test_hidden_test_content_never_serialized_in_status(client, app):
    _setup_auto_graded_mission(app)
    _login_team(client)

    status = client.get("/missions/status").get_json()
    challenge_payload = status["mission"]["challenge"]
    assert "test_cases" not in challenge_payload
    assert "hidden case" not in str(challenge_payload)
