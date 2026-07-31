from ..extensions import db
from ..models import CodeSubmission, LeaderboardSnapshot, Mission, Team, TeamMission
from .event_service import EventService, event_scope_filter
from .mission_service import MissionService


class AnalyticsService:
    def __init__(self, mission_service=None):
        self.mission_service = mission_service or MissionService()

    def _event_id(self, event_id):
        # None means "caller doesn't have a specific event in mind" -- every call site today
        # either has one already (a team's own event_id) or is a GM dashboard/export route
        # that means "the one event I'm looking at," which is the active event until Phase 1c's
        # switcher lets a GM pick a different one to view.
        return event_id if event_id is not None else EventService().get_active_event().id

    def total_submissions(self, event_id=None):
        event_id = self._event_id(event_id)
        return (
            CodeSubmission.query.join(TeamMission, CodeSubmission.team_mission_id == TeamMission.id)
            .join(Mission, TeamMission.mission_id == Mission.id)
            .filter(event_scope_filter(Mission, event_id))
            .count()
        )

    def pass_fail_counts(self, event_id=None):
        event_id = self._event_id(event_id)
        base = (
            CodeSubmission.query.join(TeamMission, CodeSubmission.team_mission_id == TeamMission.id)
            .join(Mission, TeamMission.mission_id == Mission.id)
            .filter(CodeSubmission.mode == "submit", event_scope_filter(Mission, event_id))
        )
        total = base.count()
        passed = base.filter(CodeSubmission.passed.is_(True)).count()
        return {"total": total, "passed": passed, "failed": total - passed}

    def average_completion_seconds(self, event_id=None):
        event_id = self._event_id(event_id)
        rows = (
            TeamMission.query.join(Mission, TeamMission.mission_id == Mission.id)
            .filter(
                TeamMission.completed_at.isnot(None),
                TeamMission.started_at.isnot(None),
                event_scope_filter(Mission, event_id),
            )
            .all()
        )
        if not rows:
            return None
        deltas = [(tm.completed_at - tm.started_at).total_seconds() for tm in rows]
        return sum(deltas) / len(deltas)

    def hint_usage(self, event_id=None):
        event_id = self._event_id(event_id)
        total_hints_used = (
            db.session.query(db.func.sum(Team.hints_used))
            .filter(event_scope_filter(Team, event_id))
            .scalar()
            or 0
        )
        missions_with_hint = (
            TeamMission.query.join(Mission, TeamMission.mission_id == Mission.id)
            .filter(TeamMission.hint_used.is_(True), event_scope_filter(Mission, event_id))
            .count()
        )
        return {"total_hints_used": total_hints_used, "missions_with_hint_used": missions_with_hint}

    def challenge_stats(self, event_id=None):
        """Per-challenge pass rate from real CodeSubmission attempts — separate from (and a
        useful cross-check against) a Challenge's agent-declared `difficulty` label."""
        event_id = self._event_id(event_id)
        totals = dict(
            db.session.query(Mission.id, db.func.count(CodeSubmission.id))
            .join(TeamMission, TeamMission.mission_id == Mission.id)
            .join(CodeSubmission, CodeSubmission.team_mission_id == TeamMission.id)
            .filter(CodeSubmission.mode == "submit", event_scope_filter(Mission, event_id))
            .group_by(Mission.id)
            .all()
        )
        passed = dict(
            db.session.query(Mission.id, db.func.count(CodeSubmission.id))
            .join(TeamMission, TeamMission.mission_id == Mission.id)
            .join(CodeSubmission, CodeSubmission.team_mission_id == TeamMission.id)
            .filter(
                CodeSubmission.mode == "submit",
                CodeSubmission.passed.is_(True),
                event_scope_filter(Mission, event_id),
            )
            .group_by(Mission.id)
            .all()
        )
        titles = dict(
            Mission.query.filter(event_scope_filter(Mission, event_id))
            .with_entities(Mission.id, Mission.title)
            .all()
        )

        stats = []
        for mission_id, total in totals.items():
            p = passed.get(mission_id, 0)
            stats.append(
                {
                    "mission_id": mission_id,
                    "title": titles.get(mission_id, "Unknown"),
                    "attempts": total,
                    "passed": p,
                    "pass_rate": round(100 * p / total, 1) if total else None,
                }
            )
        stats.sort(key=lambda s: s["pass_rate"] if s["pass_rate"] is not None else 999)
        return stats

    def most_failed_challenge(self, event_id=None):
        candidates = [s for s in self.challenge_stats(event_id) if s["attempts"] > 0]
        return min(candidates, key=lambda s: s["pass_rate"]) if candidates else None

    def snapshot_leaderboard(self, event_id=None):
        # Called from the existing notify_global("leaderboard_refresh") sites (mission_service,
        # security.py, mod.py's override_score) — reuses an already-existing "something
        # scoreable changed" signal instead of adding a new cron/scheduler dependency.
        event_id = self._event_id(event_id)
        teams = Team.query.filter(event_scope_filter(Team, event_id)).all()
        missions = (
            Mission.query.filter(Mission.status == "published", event_scope_filter(Mission, event_id))
            .order_by(Mission.order_index)
            .all()
        )
        ranked = sorted(teams, key=lambda t: (-t.score, -t.integrity))
        for rank, team in enumerate(ranked, start=1):
            current, _ = self.mission_service.current_mission_for(team, missions)
            db.session.add(
                LeaderboardSnapshot(
                    team_id=team.id,
                    rank=rank,
                    score=team.score,
                    integrity=team.integrity,
                    mission_current=current.title if current else "Finished",
                    fragments_count=len(team.fragments),
                )
            )
        db.session.commit()

    def leaderboard_history(self, team_id=None, limit=200):
        query = LeaderboardSnapshot.query.order_by(LeaderboardSnapshot.snapshotted_at.desc())
        if team_id is not None:
            query = query.filter_by(team_id=team_id)
        return query.limit(limit).all()
