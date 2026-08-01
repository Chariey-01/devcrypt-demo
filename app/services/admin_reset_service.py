from ..extensions import db
from ..models import (
    ClearanceStamp,
    CodeSubmission,
    EventLog,
    Fragment,
    LeaderboardSnapshot,
    Team,
    TeamKnowledgeAnswer,
    TeamMission,
)
from .event_service import event_scope_filter


class AdminResetService:
    def _clear_team_progress(self, team):
        # CodeSubmission and TeamKnowledgeAnswer both have cascade="all, delete-orphan"
        # declared on the ORM *relationship* (the TeamMission backref) — but that only fires
        # on an ORM-level session.delete(), never on Query.delete(), which issues a raw bulk
        # DELETE that bypasses the ORM (and therefore cascades) entirely. Confirmed live: this
        # exact gap passed every local test (SQLite doesn't enforce FKs by default) and then
        # threw a real ForeignKeyViolation the first time it ran against production Postgres,
        # which does. Both must be deleted explicitly, in FK order, before their parent
        # TeamMission row.
        team_mission_ids = [tm.id for tm in team.team_missions]
        if team_mission_ids:
            CodeSubmission.query.filter(
                CodeSubmission.team_mission_id.in_(team_mission_ids)
            ).delete(synchronize_session=False)
            TeamKnowledgeAnswer.query.filter(
                TeamKnowledgeAnswer.team_mission_id.in_(team_mission_ids)
            ).delete(synchronize_session=False)
        TeamMission.query.filter_by(team_id=team.id).delete(synchronize_session=False)
        Fragment.query.filter_by(team_id=team.id).delete(synchronize_session=False)
        ClearanceStamp.query.filter_by(team_id=team.id).delete(synchronize_session=False)
        team.score = 0
        team.integrity = 100
        team.hints_used = 0
        team.booth_current = None

    def reset_team(self, team):
        """Clears one team's gameplay progress (missions, fragments, clearance stamps,
        submissions, score/integrity/hints) while keeping the Team row and its members —
        for re-testing without losing team identity/roster."""
        self._clear_team_progress(team)
        db.session.commit()
        return team

    def delete_team(self, team):
        """Permanently removes a team and everything tied to it. team_missions/fragments/
        clearance_stamps/leaderboard_snapshots/members all cascade via Team's own
        relationship config (models.py) once db.session.delete(team) runs — only
        CodeSubmission and TeamKnowledgeAnswer need the same manual pre-delete as
        reset_team, for the same reason."""
        team_mission_ids = [tm.id for tm in team.team_missions]
        if team_mission_ids:
            CodeSubmission.query.filter(
                CodeSubmission.team_mission_id.in_(team_mission_ids)
            ).delete(synchronize_session=False)
            TeamKnowledgeAnswer.query.filter(
                TeamKnowledgeAnswer.team_mission_id.in_(team_mission_ids)
            ).delete(synchronize_session=False)
        db.session.delete(team)
        db.session.commit()

    def reset_all_teams(self, event_id=None):
        """Full clean slate: resets every team's progress and clears event-wide history
        (leaderboard snapshots, activity log). Intended for the moment testing ends and the
        real event begins — not a mid-event single-team retry, which is reset_team's job.
        Scoped to one event (event_id=None resets literally everything, every event ever
        run — never what a GM resetting "this event" before it starts actually wants)."""
        teams = (
            Team.query.filter(event_scope_filter(Team, event_id)).all()
            if event_id is not None
            else Team.query.all()
        )
        for team in teams:
            self._clear_team_progress(team)
        if event_id is not None:
            team_ids = [t.id for t in teams]
            LeaderboardSnapshot.query.filter(LeaderboardSnapshot.team_id.in_(team_ids)).delete(
                synchronize_session=False
            )
            EventLog.query.filter(event_scope_filter(EventLog, event_id)).delete(
                synchronize_session=False
            )
        else:
            LeaderboardSnapshot.query.delete(synchronize_session=False)
            EventLog.query.delete(synchronize_session=False)
        db.session.commit()
