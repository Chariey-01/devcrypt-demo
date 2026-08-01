"""Phase 1b: proves the event_id scoping added on top of Phase 1a's schema actually isolates
two events from each other -- not just that the existing single-event test suite still passes
unmodified (that's covered by every other test file continuing to pass as-is). Event CRUD
(Phase 1c) doesn't exist yet, so these tests create a second Event row directly via the ORM to
simulate what a GM will eventually do through the dashboard."""

from app.extensions import db
from app.models import CodeSubmission, Event, Mission, Team, TeamMission, User
from app.repositories.team_repo import TeamRepository
from app.services.analytics_service import AnalyticsService
from app.services.event_service import EventService


def _make_event_with_team_and_mission(name_suffix, status="running"):
    event = Event(status=status)
    db.session.add(event)
    db.session.flush()

    team = Team(name=f"Alpha{name_suffix}", score=10, integrity=100, event_id=event.id)
    team.set_key("KEY123")
    mission = Mission(
        title=f"Node{name_suffix}",
        type="code",
        narrative="n",
        cipher_word="X",
        booth_id=1,
        order_index=1,
        status="published",
        event_id=event.id,
    )
    db.session.add_all([team, mission])
    db.session.commit()
    return event, team, mission


def test_get_active_event_returns_the_most_recently_created_event(app):
    with app.app_context():
        event1, _, _ = _make_event_with_team_and_mission("1", status="ended")
        event2, _, _ = _make_event_with_team_and_mission("2", status="running")
        active = EventService().get_active_event()
        assert active.id == event2.id
        assert active.id != event1.id


def test_leaderboard_only_shows_the_active_events_teams(client, app):
    with app.app_context():
        event1, team1, _ = _make_event_with_team_and_mission("1")
        event2, team2, _ = _make_event_with_team_and_mission("2")

    res = client.get("/leaderboard/data")
    names = [row["team"] for row in res.get_json()["leaderboard"]]
    assert "Alpha2" in names
    assert "Alpha1" not in names


def test_mod_dashboard_only_lists_the_active_events_teams(app):
    with app.app_context():
        gm = User(email="gm@test.local", role="game_master")
        gm.set_password("pw")
        db.session.add(gm)
        db.session.commit()
        event1, team1, _ = _make_event_with_team_and_mission("1")
        event2, team2, _ = _make_event_with_team_and_mission("2")

    client = app.test_client()
    client.post("/auth/login", data={"email": "gm@test.local", "password": "pw"})
    res = client.get("/mod/data")
    names = [row["name"] for row in res.get_json()["teams"]]
    assert "Alpha2" in names
    assert "Alpha1" not in names


def test_get_team_by_name_does_not_cross_into_another_event(app):
    # Read-path scoping: a lookup scoped to one event never returns a team that belongs to
    # another, even before considering whether two events can share a literal team name.
    with app.app_context():
        event1, team1, _ = _make_event_with_team_and_mission("1")
        event2, team2, _ = _make_event_with_team_and_mission("2")

        # Both fixtures are named "Alpha<suffix>", so look each up strictly scoped to the
        # *other* event's id -- must not resolve, proving the filter is real, not a no-op.
        assert TeamRepository().get_team_by_name("Alpha1", event_id=event2.id) is None
        assert TeamRepository().get_team_by_name("Alpha2", event_id=event1.id) is None
        assert TeamRepository().get_team_by_name("Alpha1", event_id=event1.id).id == team1.id
        assert TeamRepository().get_team_by_name("Alpha2", event_id=event2.id).id == team2.id


def test_two_events_can_each_have_a_team_with_the_same_name(app):
    # The actual Phase 1d deliverable: Team.name's uniqueness is scoped per-event
    # (uq_teams_event_id_name) instead of a single global unique column, so two Career Fairs
    # can each field their own "Phantom" without colliding.
    with app.app_context():
        event1 = Event(status="ended")
        db.session.add(event1)
        db.session.flush()
        team1 = Team(name="Phantom", score=0, integrity=100, event_id=event1.id)
        team1.set_key("KEY-A")
        db.session.add(team1)

        event2 = Event(status="running")
        db.session.add(event2)
        db.session.flush()
        team2 = Team(name="Phantom", score=0, integrity=100, event_id=event2.id)
        team2.set_key("KEY-B")
        db.session.add(team2)
        db.session.commit()

        assert team1.id != team2.id
        found1 = TeamRepository().get_team_by_name("Phantom", event_id=event1.id)
        found2 = TeamRepository().get_team_by_name("Phantom", event_id=event2.id)
        assert found1.id == team1.id
        assert found2.id == team2.id
        assert found1.check_key("KEY-A")
        assert found2.check_key("KEY-B")


def test_same_name_within_one_event_is_still_rejected(app):
    from sqlalchemy.exc import IntegrityError

    with app.app_context():
        event = Event(status="running")
        db.session.add(event)
        db.session.flush()
        team_a = Team(name="Phantom", score=0, integrity=100, event_id=event.id)
        team_a.set_key("KEY-A")
        db.session.add(team_a)
        db.session.commit()

        team_b = Team(name="Phantom", score=0, integrity=100, event_id=event.id)
        team_b.set_key("KEY-B")
        db.session.add(team_b)
        try:
            db.session.commit()
            raise AssertionError("expected an IntegrityError from the composite unique constraint")
        except IntegrityError:
            db.session.rollback()


def test_team_and_mission_created_without_event_id_are_auto_stamped_to_the_active_event(app):
    with app.app_context():
        event = Event(status="running")
        db.session.add(event)
        db.session.commit()

        team = Team(name="Unscoped Team", score=0, integrity=100)  # no event_id passed
        team.set_key("KEY-C")
        mission = Mission(
            title="Unscoped Node",
            type="code",
            narrative="n",
            cipher_word="X",
            booth_id=1,
            order_index=1,
        )
        db.session.add_all([team, mission])
        db.session.commit()

        assert team.event_id == event.id
        assert mission.event_id == event.id


def test_analytics_scoped_to_one_event_does_not_count_another_events_submissions(app):
    with app.app_context():
        event1, team1, mission1 = _make_event_with_team_and_mission("1")
        event2, team2, mission2 = _make_event_with_team_and_mission("2")

        tm1 = TeamMission(team_id=team1.id, mission_id=mission1.id, status="in_progress")
        tm2 = TeamMission(team_id=team2.id, mission_id=mission2.id, status="in_progress")
        db.session.add_all([tm1, tm2])
        db.session.flush()

        db.session.add_all(
            [
                CodeSubmission(team_mission_id=tm1.id, code="x", mode="submit", passed=True),
                CodeSubmission(team_mission_id=tm1.id, code="x", mode="submit", passed=True),
                CodeSubmission(team_mission_id=tm2.id, code="x", mode="submit", passed=False),
            ]
        )
        db.session.commit()

        analytics = AnalyticsService()
        assert analytics.total_submissions(event_id=event1.id) == 2
        assert analytics.total_submissions(event_id=event2.id) == 1
        assert analytics.pass_fail_counts(event_id=event1.id) == {
            "total": 2,
            "passed": 2,
            "failed": 0,
        }
        assert analytics.pass_fail_counts(event_id=event2.id) == {
            "total": 1,
            "passed": 0,
            "failed": 1,
        }


def test_reset_all_teams_scoped_to_one_event_leaves_the_other_untouched(app):
    from app.services.admin_reset_service import AdminResetService

    with app.app_context():
        event1, team1, _ = _make_event_with_team_and_mission("1")
        event2, team2, _ = _make_event_with_team_and_mission("2")
        team1.score = 500
        team2.score = 700
        db.session.commit()
        team1_id, team2_id = team1.id, team2.id

        AdminResetService().reset_all_teams(event_id=event1.id)

        assert Team.query.get(team1_id).score == 0
        assert Team.query.get(team2_id).score == 700  # untouched
