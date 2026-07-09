from datetime import datetime

from flask import current_app

from ..extensions import db
from ..models import Fragment, Mission, TeamMission
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

    def current_mission_for(self, team, missions):
        tm_map = {tm.mission_id: tm for tm in team.team_missions}
        for mission in missions:
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

    def complete_mission(self, team, team_mission, mission, status, actor=None, actor_role="team"):
        if team_mission.status in ("passed", "overridden"):
            # Already resolved — a double-click, a race between two actors, or a stale
            # reference must not re-award score or insert a second Fragment.
            return None

        all_correct = len(team_mission.mcq_answers) == len(mission.mcqs) and all(
            answer.is_correct for answer in team_mission.mcq_answers
        )
        on_time = mission.time_limit is None or (
            team_mission.started_at is not None
            and (datetime.utcnow() - team_mission.started_at).total_seconds() <= mission.time_limit
        )

        if status == "passed":
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

        missions = Mission.query.order_by(Mission.order_index).all()
        next_mission, _ = self.current_mission_for(team, missions)
        team.booth_current = next_mission.id if next_mission else None

        self.audit.log(actor, actor_role, f"mission_{status}", "team_mission", team_mission.id)
        db.session.commit()
        return fragment_value
