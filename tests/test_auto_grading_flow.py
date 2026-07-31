from app.extensions import db
from app.models import Challenge, EventLog, Event, Mission, Team, TeamMission, TestCase, User


def _setup_auto_graded_mission(app):
    with app.app_context():
        agent = User(email="agent@test.local", role="booth_agent")
        agent.set_password("pw")
        team = Team(name="Alpha", score=0, integrity=100)
        team.set_key("ALPHA01")
        db.session.add_all([agent, team])
        db.session.add(Event(status="running"))
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


def _setup_five_case_mission(app, pass_threshold=None):
    # 5 equal-weight visible cases -> percent_score always lands on a clean multiple of 20
    # (0/20/40/60/80/100), which lines up exactly with the 80% pass_threshold default and the
    # spec's own "10 tests, passed 6, 60%" partial-credit example.
    with app.app_context():
        team = Team(name="Alpha", score=0, integrity=100)
        team.set_key("ALPHA01")
        db.session.add(team)
        db.session.add(Event(status="running"))
        db.session.commit()

        mission = Mission(
            title="Scaler Node", type="code", narrative="Double the input.",
            cipher_word="SCALE", booth_id=1, order_index=1,
        )
        db.session.add(mission)
        db.session.flush()

        challenge_kwargs = {}
        if pass_threshold is not None:
            challenge_kwargs["pass_threshold"] = pass_threshold
        challenge = Challenge(
            mission_id=mission.id, type="code", prompt="Double the input.",
            grading_mode="auto", **challenge_kwargs,
        )
        db.session.add(challenge)
        db.session.flush()

        db.session.add_all(
            [
                TestCase(
                    challenge_id=challenge.id, name=f"case {n}", input_data=str(n),
                    expected_output=str(n * 2), weight=1, visibility="visible", order_index=i,
                )
                for i, n in enumerate([1, 2, 3, 4, 5])
            ]
        )
        db.session.commit()
        return mission.id, team.id


# Correct for n <= threshold, wrong (identity instead of doubling) above it — lets a single
# submission's percent_score be dialed to an exact multiple of 20 against the 5-case fixture.
_PARTIAL_CODE = "n = int(input())\nprint(n * 2 if n <= {threshold} else n)\n"


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


def test_grading_start_is_logged_for_both_run_tests_and_submit(client, app, caplog):
    import logging

    _setup_auto_graded_mission(app)
    _login_team(client)

    with caplog.at_level(logging.INFO, logger="devcrypt.missions"):
        client.post("/missions/challenge/run-tests", json={"code": "print(int(input()) * 2)"})
        client.post("/missions/challenge/submit", json={"code": "print(int(input()) * 2)"})

    assert "grading started" in caplog.text and "mode=run_visible" in caplog.text
    assert "mode=submit" in caplog.text


def test_submission_produces_a_queryable_event_log_row(client, app):
    _setup_auto_graded_mission(app)
    _login_team(client)

    client.post("/missions/challenge/run-tests", json={"code": "print(int(input()) * 2)"})
    client.post("/missions/challenge/submit", json={"code": "print(int(input()) * 2)"})

    with app.app_context():
        actions = [log.action for log in EventLog.query.order_by(EventLog.id).all()]
        assert "visible_tests_run" in actions
        assert "submission_graded" in actions
        # metadata carries which team/outcome, matching the Moderator Activity Feed's Details column.
        graded = EventLog.query.filter_by(action="submission_graded").first()
        assert "Alpha" in graded.event_metadata
        assert "passed" in graded.event_metadata


def test_status_includes_mission_timeline(client, app):
    _setup_auto_graded_mission(app)
    _login_team(client)

    status = client.get("/missions/status").get_json()
    timeline = status["timeline"]
    assert [t["title"] for t in timeline] == ["Doubler Node", "Trailing Node"]
    assert timeline[0]["status"] == "current"
    assert timeline[1]["status"] == "not_started"

    client.post("/missions/challenge/submit", json={"code": "print(int(input()) * 2)"})
    status = client.get("/missions/status").get_json()
    timeline = status["timeline"]
    assert timeline[0]["status"] == "passed"
    assert timeline[1]["status"] == "current"


def test_status_timeline_reflects_teams_actual_rotated_route(client, app):
    # Confirms the fix for the multi-booth physical event: a team assigned to start at the
    # *second* booth must see that booth first in its timeline (and as "current"), with the
    # first booth appearing later in its route — not the fixed booth-number order every team
    # used to see regardless of their actual starting assignment.
    doubler_id, team_id = _setup_auto_graded_mission(app)
    with app.app_context():
        trailing = Mission.query.filter_by(title="Trailing Node").first()
        team = Team.query.get(team_id)
        team.starting_mission_id = trailing.id
        db.session.commit()

    _login_team(client)
    status = client.get("/missions/status").get_json()

    assert [t["title"] for t in status["timeline"]] == ["Trailing Node", "Doubler Node"]
    assert status["timeline"][0]["status"] == "current"
    assert status["mission"]["title"] == "Trailing Node"
    assert status["next_mission"] == {"mission_id": doubler_id, "title": "Doubler Node"}
    assert status["booths_completed"] == 0
    assert status["booths_total"] == 2


def test_status_serves_wrong_submission_over_starter_code(client, app):
    # A team that submits, then reopens the editor (new device, cleared localStorage, dead
    # battery) must see their real last-submitted code, never the blank starter_code — even
    # when that submission was wrong and the mission is still in_progress.
    _setup_auto_graded_mission(app)
    _login_team(client)

    status = client.get("/missions/status").get_json()
    assert status["mission"]["challenge"]["last_submitted_code"] is None

    client.post("/missions/challenge/submit", json={"code": "print(int(input()) + 1)"})

    status = client.get("/missions/status").get_json()
    assert status["mission"]["challenge"]["last_submitted_code"] == "print(int(input()) + 1)"


def test_status_serves_most_recent_of_multiple_submissions(client, app):
    # Two wrong submissions in a row (mission stays in_progress/current both times) — the
    # editor must always reload the *latest* one, not the first.
    _setup_auto_graded_mission(app)
    _login_team(client)

    client.post("/missions/challenge/submit", json={"code": "print(int(input()) + 1)"})
    with app.app_context():
        from app.models import TeamMission

        tm = TeamMission.query.first()
        tm.penalty_until = None
        db.session.commit()
    client.post("/missions/challenge/submit", json={"code": "print(int(input()) + 2)"})

    status = client.get("/missions/status").get_json()
    assert status["mission"]["challenge"]["last_submitted_code"] == "print(int(input()) + 2)"


def _clear_cooldown(app, team_id, mission_id):
    with app.app_context():
        tm = TeamMission.query.filter_by(team_id=team_id, mission_id=mission_id).first()
        tm.penalty_until = None
        db.session.commit()


def test_default_pass_threshold_is_80_percent(client, app):
    mission_id, team_id = _setup_five_case_mission(app)  # pass_threshold unset -> model default
    _login_team(client)

    with app.app_context():
        assert Challenge.query.filter_by(mission_id=mission_id).first().pass_threshold == 80

    res = client.post(
        "/missions/challenge/submit", json={"code": _PARTIAL_CODE.format(threshold=4)}  # 4/5 = 80%
    )
    body = res.get_json()
    assert body["correct"] is True
    assert body["percent_score"] == 80


def test_below_threshold_awards_partial_score_no_fragment_no_advance(client, app):
    mission_id, team_id = _setup_five_case_mission(app)
    _login_team(client)

    res = client.post(
        "/missions/challenge/submit", json={"code": _PARTIAL_CODE.format(threshold=3)}  # 3/5 = 60%
    )
    body = res.get_json()
    assert body["correct"] is False
    assert body["percent_score"] == 60

    with app.app_context():
        team = Team.query.filter_by(name="Alpha").first()
        tm = TeamMission.query.filter_by(team_id=team_id, mission_id=mission_id).first()
        # round(20 * 0.6) = 12
        assert team.score == 12
        assert tm.score == 12
        assert tm.best_percent_score == 60
        assert tm.status == "in_progress"
    status = client.get("/missions/status").get_json()
    assert status["fragments"] == []


def test_resubmitting_at_a_better_percent_only_awards_the_delta(client, app):
    mission_id, team_id = _setup_five_case_mission(app)
    _login_team(client)

    client.post("/missions/challenge/submit", json={"code": _PARTIAL_CODE.format(threshold=2)})  # 40%
    with app.app_context():
        team = Team.query.filter_by(name="Alpha").first()
        assert team.score == round(20 * 0.4)  # 8

    _clear_cooldown(app, team_id, mission_id)
    client.post("/missions/challenge/submit", json={"code": _PARTIAL_CODE.format(threshold=3)})  # 60%

    with app.app_context():
        team = Team.query.filter_by(name="Alpha").first()
        tm = TeamMission.query.filter_by(team_id=team_id, mission_id=mission_id).first()
        # round(20*0.6) - round(20*0.4) = 12 - 8 = 4 more, not a fresh 12
        assert team.score == 12
        assert tm.best_percent_score == 60


def test_resubmitting_at_a_worse_percent_never_reduces_score(client, app):
    mission_id, team_id = _setup_five_case_mission(app)
    _login_team(client)

    client.post("/missions/challenge/submit", json={"code": _PARTIAL_CODE.format(threshold=3)})  # 60%
    with app.app_context():
        team = Team.query.filter_by(name="Alpha").first()
        score_after_60 = team.score

    _clear_cooldown(app, team_id, mission_id)
    client.post("/missions/challenge/submit", json={"code": _PARTIAL_CODE.format(threshold=1)})  # 20%

    with app.app_context():
        team = Team.query.filter_by(name="Alpha").first()
        tm = TeamMission.query.filter_by(team_id=team_id, mission_id=mission_id).first()
        assert team.score == score_after_60
        assert tm.best_percent_score == 60  # never regresses


def test_partial_credit_does_not_double_count_once_the_team_eventually_passes(client, app):
    mission_id, team_id = _setup_five_case_mission(app)
    _login_team(client)

    client.post("/missions/challenge/submit", json={"code": _PARTIAL_CODE.format(threshold=3)})  # 60%, fail
    _clear_cooldown(app, team_id, mission_id)
    res = client.post("/missions/challenge/submit", json={"code": "n = int(input())\nprint(n * 2)\n"})  # 100%
    assert res.get_json()["correct"] is True

    with app.app_context():
        team = Team.query.filter_by(name="Alpha").first()
        # First submit (60%, fail) pays partial credit: round(CHALLENGE_COMPLETE(20) * 0.6) = 12,
        # and increments team_mission.attempts to 1 via apply_retry_penalty (so the later pass is
        # NOT a first attempt). Second submit (100%, pass) pays:
        #   base = CODING_CHALLENGE_PASS(100) - already_paid(12) = 88
        #   + NO_HINT_BONUS(5)            (no hint requested)
        #   + FINISH_BOOTH_BONUS(30)      (no FIRST_ATTEMPT_BONUS: this wasn't attempt 1)
        #   + FRAGMENT_BONUS(50)          (own "cipher" line item, still summed into team.score)
        #   + time bonus(20)              (test runs well under the 300s tier)
        #   = 193
        # Total: 12 (partial) + 193 (pass) = 205.
        assert team.score == 205
        assert len(team.fragments) == 1


def test_draft_mission_is_invisible_to_players(client, app):
    mission_id, team_id = _setup_auto_graded_mission(app)
    with app.app_context():
        mission = Mission.query.get(mission_id)
        mission.status = "draft"
        db.session.commit()
    _login_team(client)

    status = client.get("/missions/status").get_json()
    # With the auto-graded mission drafted, the team should skip straight to the trailing
    # published mission — never see the draft one, and never see it as "finished" either.
    assert status["mission"] is not None
    assert status["mission"]["title"] == "Trailing Node"
