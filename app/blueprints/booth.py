from datetime import datetime, timedelta

from flask import Blueprint, abort, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required

from ..decorators import roles_required
from ..extensions import db
from ..models import Mission, TeamMission
from ..services.audit_service import AuditService
from ..services.cipher_service import CipherService
from ..services.mission_service import MissionService
from ..services.scoring_service import ScoringService

booth_bp = Blueprint("booth", __name__, url_prefix="/booth")

scoring_service = ScoringService()
cipher_service = CipherService()
audit_service = AuditService()
mission_service = MissionService(scoring=scoring_service, cipher=cipher_service, audit=audit_service)


@booth_bp.route("/select", methods=["GET", "POST"])
@login_required
@roles_required("booth_agent")
def select_booth():
    missions = Mission.query.filter_by(type="code").order_by(Mission.order_index).all()
    if request.method == "POST":
        session["agent_mission_id"] = int(request.form["mission_id"])
        return redirect(url_for("booth.queue"))
    return render_template("booth/select.html", missions=missions)


@booth_bp.route("/queue")
@login_required
@roles_required("booth_agent")
def queue():
    mission_id = session.get("agent_mission_id")
    if not mission_id:
        return redirect(url_for("booth.select_booth"))
    mission = Mission.query.get_or_404(mission_id)
    return render_template("booth/dashboard.html", mission=mission)


@booth_bp.route("/alerts/data")
@login_required
@roles_required("booth_agent", "security_officer")
def alerts_data():
    pending = (
        TeamMission.query.filter_by(status="in_progress")
        .filter(TeamMission.submission_text.isnot(None))
        .order_by(TeamMission.id.desc())
        .limit(20)
        .all()
    )
    return jsonify(
        {
            "alerts": [
                {
                    "id": tm.id,
                    "team": tm.team.name,
                    "mission": tm.mission.title,
                }
                for tm in pending
            ]
        }
    )


@booth_bp.route("/queue/data")
@login_required
@roles_required("booth_agent")
def queue_data():
    mission_id = session.get("agent_mission_id")
    if not mission_id:
        return jsonify({"error": "No booth selected."}), 400
    pending = (
        TeamMission.query.filter_by(mission_id=mission_id, status="in_progress")
        .filter(TeamMission.submission_text.isnot(None))
        .all()
    )
    rows = [
        {
            "team_mission_id": tm.id,
            "team": tm.team.name,
            "submission": tm.submission_text,
            "attempts": tm.attempts,
            "hints_remaining": max(0, 3 - tm.team.hints_used),
        }
        for tm in pending
    ]
    return jsonify({"queue": rows})


def _load_pending(team_mission_id):
    team_mission = TeamMission.query.get_or_404(team_mission_id)
    if team_mission.mission_id != session.get("agent_mission_id"):
        abort(403)
    if team_mission.status in ("passed", "overridden"):
        abort(409)
    return team_mission


@booth_bp.route("/submission/<int:team_mission_id>/pass", methods=["POST"])
@login_required
@roles_required("booth_agent")
def pass_submission(team_mission_id):
    team_mission = _load_pending(team_mission_id)
    mission_service.complete_mission(
        team_mission.team, team_mission, team_mission.mission, "passed",
        actor=current_user, actor_role="booth_agent",
    )
    return jsonify({"ok": True})


@booth_bp.route("/submission/<int:team_mission_id>/retry", methods=["POST"])
@login_required
@roles_required("booth_agent")
def retry_submission(team_mission_id):
    team_mission = _load_pending(team_mission_id)
    scoring_service.apply_retry_penalty(team_mission.team, team_mission)
    team_mission.penalty_until = datetime.utcnow() + timedelta(seconds=60)
    team_mission.submission_text = None
    audit_service.log(current_user, "booth_agent", "mission_retry", "team_mission", team_mission.id)
    db.session.commit()
    return jsonify({"ok": True})


@booth_bp.route("/submission/<int:team_mission_id>/hint", methods=["POST"])
@login_required
@roles_required("booth_agent")
def hint_submission(team_mission_id):
    team_mission = _load_pending(team_mission_id)
    if team_mission.team.hints_used >= 3:
        return jsonify({"error": "Team has no hints remaining."}), 403
    scoring_service.apply_hint_penalty(team_mission.team, team_mission)
    audit_service.log(current_user, "booth_agent", "mission_hint", "team_mission", team_mission.id)
    db.session.commit()
    return jsonify({"hint": team_mission.mission.challenge.hint_text})


@booth_bp.route("/submission/<int:team_mission_id>/override", methods=["POST"])
@login_required
@roles_required("booth_agent")
def override_submission(team_mission_id):
    team_mission = _load_pending(team_mission_id)
    mission_service.complete_mission(
        team_mission.team, team_mission, team_mission.mission, "overridden",
        actor=current_user, actor_role="booth_agent",
    )
    return jsonify({"ok": True})
