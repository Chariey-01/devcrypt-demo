"""Regression coverage for the team.score lost-update race: two requests both holding an
in-memory Team object with the same starting score must not clobber each other's award. Since
a single-threaded test can't run two HTTP requests at once, the second "concurrent" writer is
simulated with a raw connection that bypasses db.session entirely (mirroring what a second,
independent request-scoped session would do), so the Python-level `team` object under test
stays exactly as stale as it would across two real requests."""

from sqlalchemy import text

from app.extensions import db
from app.models import Mission, Team, TeamMission
from app.services.mission_service import MissionService


def _setup(app):
    with app.app_context():
        team = Team(name="Echo", score=0, integrity=100)
        team.set_key("ECHO0001")
        mission = Mission(
            title="Doubler", type="code", narrative="n", cipher_word="X", order_index=0
        )
        db.session.add_all([team, mission])
        db.session.flush()
        team_mission = TeamMission(team_id=team.id, mission_id=mission.id, status="in_progress")
        db.session.add(team_mission)
        db.session.commit()
        return team.id, mission.id, team_mission.id


def test_complete_mission_does_not_lose_a_concurrent_score_update(app):
    team_id, mission_id, team_mission_id = _setup(app)
    with app.app_context():
        # These are the same objects a request handler would already be holding by the time
        # it reaches complete_mission (e.g. loaded via current_team() earlier in the view).
        team = Team.query.get(team_id)
        team_mission = TeamMission.query.get(team_mission_id)
        mission = Mission.query.get(mission_id)
        assert team.score == 0

        # Simulate a second, concurrent request that has already awarded this team +50 points
        # and committed — via a connection entirely outside db.session, so `team`'s in-memory
        # score attribute stays stale at 0 exactly like it would across two real HTTP requests.
        with db.engine.begin() as conn:
            conn.execute(
                text("UPDATE teams SET score = score + 50 WHERE id = :id"), {"id": team_id}
            )

        MissionService().complete_mission(team, team_mission, mission, "passed")
        db.session.commit()

        # score_mission_pass awards CHALLENGE_COMPLETE(20) + NO_HINT_BONUS(5)
        # + FIRST_ATTEMPT_BONUS(20) + FINISH_BOOTH_BONUS(30) + FRAGMENT_BONUS(50) = 125 (no
        # perfect-booth bonus: this team_mission has no knowledge_answers, so _all_mcq_correct
        # is False). freeze_submission sets elapsed_seconds=0 (no started_at set here), which
        # falls in the <=300s time-bonus tier, adding +20 -> 145 total. Before the fix,
        # complete_mission used the stale in-memory team.score (0) as its base, landing on 145
        # and silently discarding the concurrent +50. With the row-locked refresh in place, it
        # re-reads the true DB score (50) first, landing on 195.
        final = Team.query.get(team_id)
        assert final.score == 195
