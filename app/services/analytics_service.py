from ..extensions import db
from ..models import CodeSubmission, LeaderboardSnapshot, Mission, Team, TeamMission
from .mission_service import MissionService


class AnalyticsService:
    def __init__(self, mission_service=None):
        self.mission_service = mission_service or MissionService()

    def total_submissions(self):
        return CodeSubmission.query.count()

    def pass_fail_counts(self):
        total = CodeSubmission.query.filter_by(mode="submit").count()
        passed = CodeSubmission.query.filter_by(mode="submit", passed=True).count()
        return {"total": total, "passed": passed, "failed": total - passed}

    def average_completion_seconds(self):
        rows = TeamMission.query.filter(
            TeamMission.completed_at.isnot(None), TeamMission.started_at.isnot(None)
        ).all()
        if not rows:
            return None
        deltas = [(tm.completed_at - tm.started_at).total_seconds() for tm in rows]
        return sum(deltas) / len(deltas)

    def hint_usage(self):
        total_hints_used = db.session.query(db.func.sum(Team.hints_used)).scalar() or 0
        missions_with_hint = TeamMission.query.filter_by(hint_used=True).count()
        return {"total_hints_used": total_hints_used, "missions_with_hint_used": missions_with_hint}

    def challenge_stats(self):
        """Per-challenge pass rate from real CodeSubmission attempts — separate from (and a
        useful cross-check against) a Challenge's agent-declared `difficulty` label."""
        totals = dict(
            db.session.query(Mission.id, db.func.count(CodeSubmission.id))
            .join(TeamMission, TeamMission.mission_id == Mission.id)
            .join(CodeSubmission, CodeSubmission.team_mission_id == TeamMission.id)
            .filter(CodeSubmission.mode == "submit")
            .group_by(Mission.id)
            .all()
        )
        passed = dict(
            db.session.query(Mission.id, db.func.count(CodeSubmission.id))
            .join(TeamMission, TeamMission.mission_id == Mission.id)
            .join(CodeSubmission, CodeSubmission.team_mission_id == TeamMission.id)
            .filter(CodeSubmission.mode == "submit", CodeSubmission.passed.is_(True))
            .group_by(Mission.id)
            .all()
        )
        titles = dict(Mission.query.with_entities(Mission.id, Mission.title).all())

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

    def most_failed_challenge(self):
        candidates = [s for s in self.challenge_stats() if s["attempts"] > 0]
        return min(candidates, key=lambda s: s["pass_rate"]) if candidates else None

    def snapshot_leaderboard(self):
        # Called from the existing notify_global("leaderboard_refresh") sites (mission_service,
        # security.py, mod.py's override_score) — reuses an already-existing "something
        # scoreable changed" signal instead of adding a new cron/scheduler dependency.
        teams = Team.query.all()
        missions = Mission.query.filter_by(status="published").order_by(Mission.order_index).all()
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
