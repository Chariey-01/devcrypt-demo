import csv
import io
from datetime import datetime

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..decorators import roles_required
from ..models import EventLog, Mission, Team, TeamMission
from ..services.audit_service import AuditService
from ..services.cipher_service import CipherService
from ..services.event_service import EventService
from ..services.mission_service import MissionService
from ..services.scoring_service import ScoringService

mod_bp = Blueprint("mod", __name__, url_prefix="/mod")

scoring_service = ScoringService()
cipher_service = CipherService()
audit_service = AuditService()
mission_service = MissionService(scoring=scoring_service, cipher=cipher_service, audit=audit_service)
event_service = EventService()


@mod_bp.route("/health")
def health():
    return jsonify({"status": "ok"})


@mod_bp.route("/")
@login_required
@roles_required("game_master")
def dashboard():
    return render_template("mod/dashboard.html", state=event_service.get_state())


@mod_bp.route("/data")
@login_required
@roles_required("game_master")
def data():
    teams = Team.query.order_by(Team.name).all()
    missions = Mission.query.order_by(Mission.order_index).all()
    rows = []
    for team in teams:
        missions_done = sum(1 for tm in team.team_missions if tm.status in ("passed", "overridden"))
        overridden = any(tm.status == "overridden" for tm in team.team_missions)
        current, _ = mission_service.current_mission_for(team, missions)
        rows.append(
            {
                "id": team.id,
                "name": team.name,
                "score": team.score,
                "integrity": team.integrity,
                "current_mission": current.title if current else "Finished",
                "missions_done": missions_done,
                "fragments": len(team.fragments),
                "clearance": len(team.clearance_stamps),
                "hints_used": team.hints_used,
                "status": "finished" if missions_done >= 6 else ("overridden" if overridden else "active"),
                "elapsed": (datetime.utcnow() - team.created_at).total_seconds(),
            }
        )
    state = event_service.get_state()
    return jsonify(
        {
            "teams": rows,
            "event_status": state.status,
            "broadcast": state.broadcast_message,
        }
    )


@mod_bp.route("/team/<int:team_id>")
@login_required
@roles_required("game_master")
def team_detail(team_id):
    team = Team.query.get_or_404(team_id)
    tm_ids = [tm.id for tm in team.team_missions]
    logs = EventLog.query.filter(
        (EventLog.target_type == "team_mission") & (EventLog.target_id.in_(tm_ids))
        if tm_ids
        else (EventLog.target_type == "team") & (EventLog.target_id == team.id)
    ).order_by(EventLog.logged_at.desc()).all()
    return render_template("mod/team_detail.html", team=team, logs=logs)


@mod_bp.route("/event/start", methods=["POST"])
@login_required
@roles_required("game_master")
def start_event():
    event_service.start()
    audit_service.log(current_user, "game_master", "event_start")
    return redirect(url_for("mod.dashboard"))


@mod_bp.route("/event/pause", methods=["POST"])
@login_required
@roles_required("game_master")
def pause_event():
    event_service.pause()
    audit_service.log(current_user, "game_master", "event_pause")
    return redirect(url_for("mod.dashboard"))


@mod_bp.route("/event/end", methods=["POST"])
@login_required
@roles_required("game_master")
def end_event():
    event_service.end()
    audit_service.log(current_user, "game_master", "event_end")
    return redirect(url_for("mod.dashboard"))


@mod_bp.route("/broadcast", methods=["POST"])
@login_required
@roles_required("game_master")
def broadcast():
    message = request.form.get("message", "").strip()
    if message:
        event_service.broadcast(message)
        audit_service.log(current_user, "game_master", "broadcast", metadata=message)
    return redirect(url_for("mod.dashboard"))


@mod_bp.route("/override/<int:team_mission_id>", methods=["POST"])
@login_required
@roles_required("game_master")
def override(team_mission_id):
    team_mission = TeamMission.query.get_or_404(team_mission_id)
    if team_mission.status in ("passed", "overridden"):
        abort(409)
    mission_service.complete_mission(
        team_mission.team, team_mission, team_mission.mission, "overridden",
        actor=current_user, actor_role="game_master",
    )
    return redirect(url_for("mod.team_detail", team_id=team_mission.team_id))


@mod_bp.route("/export.csv")
@login_required
@roles_required("game_master")
def export_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["team", "score", "integrity", "fragments", "clearance_stamps", "missions_passed", "hints_used"]
    )
    for team in Team.query.order_by(Team.name).all():
        writer.writerow(
            [
                team.name,
                team.score,
                team.integrity,
                len(team.fragments),
                len(team.clearance_stamps),
                sum(1 for tm in team.team_missions if tm.status in ("passed", "overridden")),
                team.hints_used,
            ]
        )
    response = Response(output.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=devcrypt_report.csv"
    return response
