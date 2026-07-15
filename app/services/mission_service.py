from datetime import datetime

from flask import current_app
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Fragment, Mission, TeamMission
from ..sockets import notify_global, notify_mod, notify_team
from .audit_service import AuditService
from .cipher_service import CipherService
from .scoring_service import ScoringService


class MissionService:
    def __init__(self, scoring=None, cipher=None, audit=None):
        self.scoring = scoring or ScoringService()
        self.cipher = cipher or CipherService()
        self.audit = audit or AuditService()

    def next_mission(self, missions, current_mission_id=None):
        if current_mission_id:
            for mission in missions:
                if mission.id == current_mission_id:
                    return mission
            return None
        return missions[0] if missions else None

    def _ordered_for_team(self, team, missions):
        # Game Master-assigned starting booth (Team.starting_mission_id): rotate the
        # sequence so the team begins there instead of at order_index 0. The highest
        # order_index mission (the final vault, e.g. RESTORE) is deliberately excluded
        # from rotation and always stays last, regardless of starting booth, so its
        # clearance-stamp gate keeps meaning "after every other node is secured."
        if not getattr(team, "starting_mission_id", None) or len(missions) <= 1:
            return missions
        *rotatable, final = missions
        start_index = next((i for i, m in enumerate(rotatable) if m.id == team.starting_mission_id), None)
        if start_index is None:
            return missions
        return rotatable[start_index:] + rotatable[:start_index] + [final]

    def current_mission_for(self, team, missions):
        tm_map = {tm.mission_id: tm for tm in team.team_missions}
        for mission in self._ordered_for_team(team, missions):
            team_mission = tm_map.get(mission.id)
            if not team_mission or team_mission.status not in ("passed", "overridden"):
                return mission, team_mission
        return None, None

    def get_or_create_team_mission(self, team, mission):
        team_mission = TeamMission.query.filter_by(team_id=team.id, mission_id=mission.id).first()
        if not team_mission:
            team_mission = TeamMission(
                team_id=team.id,
                mission_id=mission.id,
                status="in_progress",
                started_at=datetime.utcnow(),
            )
            db.session.add(team_mission)
            db.session.commit()
        return team_mission

    def complete_mission(
        self, team, team_mission, mission, status, actor=None, actor_role="team", grading_result=None
    ):
        if team_mission.status in ("passed", "overridden"):
            # Already resolved — a double-click, a race between two actors, or a stale
            # reference must not re-award score or insert a second Fragment. This is a
            # fast-path check only, not a race-safe lock: see the IntegrityError handling
            # around the commit below for what actually makes concurrent duplicates safe.
            return None

        all_correct = len(team_mission.mcq_answers) == len(mission.mcqs) and all(
            answer.is_correct for answer in team_mission.mcq_answers
        )
        on_time = mission.time_limit is None or (
            team_mission.started_at is not None
            and (datetime.utcnow() - team_mission.started_at).total_seconds() <= mission.time_limit
        )

        if status == "passed":
            if grading_result is not None:
                # Auto-graded (sandboxed test suite) pass — weighted-percent scoring instead
                # of the flat manual-review score. Everything below (fragment, advance,
                # audit) is identical either way.
                self.scoring.score_auto_graded_pass(team, team_mission, mission.challenge, grading_result, on_time)
            else:
                self.scoring.score_mission_pass(team, team_mission, mission, all_correct, on_time)
        else:
            self.scoring.apply_override_penalty(team, team_mission)

        team_mission.status = status
        team_mission.completed_at = datetime.utcnow()
        team_mission.submission_text = None

        fragment_value = self.cipher.generate_fragment(
            team.id, mission.id, current_app.config["EVENT_SALT"]
        )
        db.session.add(Fragment(team_id=team.id, mission_id=mission.id, cipher_value=fragment_value))

        # Everything from here through the commit is wrapped in one try/except: SQLAlchemy's
        # autoflush means the pending Fragment insert (and its UNIQUE(team_id, mission_id)
        # constraint) can get flushed to the DB by *any* subsequent query in this block — not
        # just the explicit commit() at the end — so the IntegrityError from a concurrent
        # duplicate can surface as early as the very next `Mission.query...` line. Confirmed
        # live: with only the final commit() wrapped, 10 simultaneous identical submissions for
        # one team still crashed with a raw 500, because autoflush inside `Mission.query...`
        # threw before that commit() was ever reached.
        try:
            missions = Mission.query.order_by(Mission.order_index).all()
            next_mission, _ = self.current_mission_for(team, missions)
            team.booth_current = next_mission.id if next_mission else None

            self.audit.log(actor, actor_role, f"mission_{status}", "team_mission", team_mission.id)
            db.session.commit()
        except IntegrityError:
            # Concurrent duplicate: another request for the same team/mission committed first
            # in the window between the status check above and this commit — under gevent's
            # cooperative concurrency, two requests for the same team can both pass that check
            # before either commits. Fragment's unique (team_id, mission_id) constraint is the
            # real race-safe guard; this just turns the resulting IntegrityError into the same
            # graceful "already resolved" outcome as the fast-path check above, instead of a raw
            # 500. Discards every in-memory change this attempt made (score deltas, status,
            # booth_current) — correct, since none of it should apply if a concurrent request
            # already won.
            db.session.rollback()
            return None
        notify_team(team.id, "mission_result")
        notify_mod("mission_result")
        notify_global("leaderboard_refresh")
        return fragment_value
