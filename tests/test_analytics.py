from datetime import datetime, timedelta

from app.extensions import db
from app.models import Challenge, CodeSubmission, LeaderboardSnapshot, Mission, Team, TeamMission
from app.services.analytics_service import AnalyticsService


def _setup(app):
    with app.app_context():
        team_a = Team(name="Alpha", score=50, integrity=100, hints_used=2)
        team_b = Team(name="Bravo", score=30, integrity=90, hints_used=0)
        team_a.set_key("A")
        team_b.set_key("B")
        db.session.add_all([team_a, team_b])

        mission = Mission(
            title="Doubler Node",
            type="code",
            narrative="n",
            cipher_word="DOUBLE",
            booth_id=1,
            order_index=1,
        )
        db.session.add(mission)
        db.session.flush()
        challenge = Challenge(mission_id=mission.id, type="code", prompt="p", grading_mode="auto")
        db.session.add(challenge)
        db.session.flush()

        started = datetime.utcnow() - timedelta(minutes=10)
        tm_a = TeamMission(
            team_id=team_a.id,
            mission_id=mission.id,
            status="passed",
            started_at=started,
            completed_at=started + timedelta(minutes=4),
            hint_used=True,
        )
        tm_b = TeamMission(
            team_id=team_b.id,
            mission_id=mission.id,
            status="in_progress",
            started_at=started,
            completed_at=None,
        )
        db.session.add_all([tm_a, tm_b])
        db.session.flush()

        db.session.add_all(
            [
                CodeSubmission(
                    team_mission_id=tm_a.id,
                    code="c",
                    mode="submit",
                    total_tests=2,
                    passed_tests=2,
                    percent_score=100,
                    passed=True,
                ),
                CodeSubmission(
                    team_mission_id=tm_b.id,
                    code="c",
                    mode="submit",
                    total_tests=2,
                    passed_tests=0,
                    percent_score=0,
                    passed=False,
                ),
                CodeSubmission(
                    team_mission_id=tm_b.id,
                    code="c",
                    mode="submit",
                    total_tests=2,
                    passed_tests=0,
                    percent_score=0,
                    passed=False,
                ),
                # run_visible submissions must NOT count toward pass/fail or challenge stats.
                CodeSubmission(
                    team_mission_id=tm_a.id,
                    code="c",
                    mode="run_visible",
                    total_tests=1,
                    passed_tests=1,
                    percent_score=100,
                    passed=True,
                ),
            ]
        )
        db.session.commit()
        return team_a.id, team_b.id, mission.id


def test_total_submissions_counts_every_mode(app):
    _setup(app)
    with app.app_context():
        assert AnalyticsService().total_submissions() == 4


def test_pass_fail_counts_only_consider_submit_mode(app):
    _setup(app)
    with app.app_context():
        counts = AnalyticsService().pass_fail_counts()
        assert counts == {"total": 3, "passed": 1, "failed": 2}


def test_average_completion_seconds_only_resolved_missions(app):
    _setup(app)
    with app.app_context():
        avg = AnalyticsService().average_completion_seconds()
        # Only tm_a is resolved (completed_at set) — exactly 4 minutes = 240s.
        assert avg == 240.0


def test_hint_usage(app):
    _setup(app)
    with app.app_context():
        usage = AnalyticsService().hint_usage()
        assert usage == {"total_hints_used": 2, "missions_with_hint_used": 1}


def test_challenge_stats_and_most_failed(app):
    _setup(app)
    with app.app_context():
        stats = AnalyticsService().challenge_stats()
        assert len(stats) == 1
        assert stats[0]["title"] == "Doubler Node"
        assert stats[0]["attempts"] == 3
        assert stats[0]["passed"] == 1
        assert stats[0]["pass_rate"] == round(100 / 3, 1)

        worst = AnalyticsService().most_failed_challenge()
        assert worst["title"] == "Doubler Node"


def test_snapshot_leaderboard_writes_ranked_rows(app):
    team_a_id, team_b_id, mission_id = _setup(app)
    with app.app_context():
        AnalyticsService().snapshot_leaderboard()
        rows = LeaderboardSnapshot.query.order_by(LeaderboardSnapshot.rank).all()
        assert len(rows) == 2
        # Alpha (score 50) ranks above Bravo (score 30).
        assert rows[0].team_id == team_a_id
        assert rows[0].rank == 1
        assert rows[0].score == 50
        assert rows[1].team_id == team_b_id
        assert rows[1].rank == 2
